"""FastAPI entrypoint — PMI Agent Service."""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from config import settings
from memory.knowledge_loader import KnowledgeLoader
from orchestrator import run_pmi_pipeline

# ─── Настройка логирования ────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

# ─── Метрики Prometheus ───────────────────────────────────────────────────
pmi_runs_total = Counter(
    "pmi_runs_total",
    "Общее количество запусков PMI-пайплайна",
    ["status"],
)
pmi_duration = Histogram(
    "pmi_duration_seconds",
    "Продолжительность PMI-пайплайна",
    buckets=[10, 30, 60, 120, 300, 600],
)
pmi_verdicts = Counter(
    "pmi_verdicts_total",
    "Количество вердиктов по результатам испытаний",
    ["verdict"],
)


# ─── Хранилище запущенных задач (в памяти, для MVP) ──────────────────────
_tasks: dict[str, dict] = {}


# ─── Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("pmi_agent_starting", model=settings.ollama_model)

    # Загружаем knowledge base в ChromaDB
    try:
        loader = KnowledgeLoader()
        chunks = loader.load_all()
        logger.info("knowledge_loaded", chunks=chunks)
    except Exception as e:
        logger.warning("knowledge_load_failed", error=str(e))

    yield

    logger.info("pmi_agent_stopping")


# ─── Приложение ───────────────────────────────────────────────────────────
app = FastAPI(
    title="PMI Agent Service",
    description="Мультиагентная система автоматизированного тестирования по ГОСТ 34.603",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─── Схемы запросов/ответов ───────────────────────────────────────────────
class RunPMIRequest(BaseModel):
    function_id: str = Field(..., description="ID функции из системы, напр. F-AUTH-02")
    function_name: str = Field(..., description="Наименование функции")
    function_description: str = Field(..., description="Подробное описание функции")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Критерии приемки из ТЗ",
    )
    project_id: str = Field(default="test-project")
    target_url: str = Field(
        default="",
        description="URL фронтенда. Если пустой — используется TARGET_APP_URL из .env",
    )


class RunPMIResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str           # pending | running | done | failed
    function_id: str | None = None
    verdict: str | None = None
    error: str | None = None
    steps_total: int | None = None
    steps_passed: int | None = None
    pmi_section: dict | None = None


# ─── Фоновая задача ───────────────────────────────────────────────────────
async def _run_pipeline_task(task_id: str, request: RunPMIRequest) -> None:
    _tasks[task_id]["status"] = "running"
    start = time.time()

    target_url = request.target_url or settings.target_app_url

    try:
        result = await run_pmi_pipeline(
            function_id=request.function_id,
            function_name=request.function_name,
            function_description=request.function_description,
            acceptance_criteria=request.acceptance_criteria,
            project_id=request.project_id,
            target_url=target_url,
        )

        _tasks[task_id].update({
            "status": result["status"],
            "pmi_section": result.get("pmi_section"),
            "step_results": result.get("step_results", []),
            "error": result.get("error"),
        })

        duration = time.time() - start
        pmi_runs_total.labels(status=result["status"]).inc()
        pmi_duration.observe(duration)

        verdict = (result.get("pmi_section") or {}).get("verdict", "unknown")
        pmi_verdicts.labels(verdict=verdict).inc()

        logger.info(
            "task_completed",
            task_id=task_id,
            function_id=request.function_id,
            status=result["status"],
            verdict=verdict,
            duration=round(duration, 1),
        )

    except Exception as e:
        _tasks[task_id].update({"status": "failed", "error": str(e)})
        pmi_runs_total.labels(status="failed").inc()
        logger.error("task_failed", task_id=task_id, error=str(e))


# ─── Эндпоинты ────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "pmi-agent", "version": "1.0.0"}


@app.get("/metrics")
async def metrics():
    """Prometheus-метрики."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/pmi/run", response_model=RunPMIResponse, status_code=202)
async def run_pmi(request: RunPMIRequest, background_tasks: BackgroundTasks):
    """
    Запустить PMI-пайплайн для функции.
    Возвращает task_id для отслеживания статуса.
    """
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "pending",
        "function_id": request.function_id,
        "pmi_section": None,
        "step_results": [],
        "error": None,
    }

    background_tasks.add_task(_run_pipeline_task, task_id, request)

    logger.info(
        "task_created",
        task_id=task_id,
        function_id=request.function_id,
    )

    return RunPMIResponse(
        task_id=task_id,
        status="pending",
        message=f"PMI-пайплайн запущен для функции {request.function_id}",
    )


@app.get("/api/v1/pmi/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Получить статус задачи по task_id."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    section = task.get("pmi_section") or {}
    results = task.get("step_results", [])

    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        function_id=task.get("function_id"),
        verdict=section.get("verdict"),
        error=task.get("error"),
        steps_total=section.get("steps_total") or len(results),
        steps_passed=section.get("steps_passed"),
        pmi_section=section if section else None,
    )


@app.get("/api/v1/pmi/tasks")
async def list_tasks():
    """Список всех задач (для отладки)."""
    return [
        {
            "task_id": tid,
            "function_id": t.get("function_id"),
            "status": t.get("status"),
            "verdict": (t.get("pmi_section") or {}).get("verdict"),
        }
        for tid, t in _tasks.items()
    ]


@app.post("/api/v1/knowledge/reload")
async def reload_knowledge():
    """Перезагрузить knowledge base в ChromaDB (force=True)."""
    try:
        loader = KnowledgeLoader()
        chunks = loader.load_all(force=True)
        return {"status": "ok", "chunks_loaded": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
