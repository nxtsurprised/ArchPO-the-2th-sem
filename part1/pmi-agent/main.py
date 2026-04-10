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
from orchestrator import run_pmi_pipeline, run_draft_pipeline
from services.catalog_client import get_project_functions, save_pmi_results

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


# ─── Document-level task storage ────────────────────────────────────────
_doc_tasks: dict[str, dict] = {}


class RunForDocumentRequest(BaseModel):
    document_id: str = Field(..., description="ID документа ПМИ из catalog-service")
    project_id: str = Field(..., description="ID проекта — для выборки функций")
    target_url: str = Field(default="", description="URL фронтенда. Пустой → TARGET_APP_URL из .env")


class RunForDocumentResponse(BaseModel):
    task_id: str
    status: str
    functions_count: int
    message: str


async def _run_all_functions(
    task_id: str,
    document_id: str,
    project_id: str,
    functions: list[dict],
    target_url: str,
) -> None:
    """Run PMI pipeline for every function, then write results back to catalog."""
    _doc_tasks[task_id]["status"] = "running"
    results: dict[str, dict] = {}
    start = time.time()

    for fn in functions:
        fn_id = fn["id"]
        try:
            result = await run_pmi_pipeline(
                function_id=fn_id,
                function_name=fn["name"],
                function_description=fn.get("description") or fn["name"],
                acceptance_criteria=fn.get("acceptance_criteria", []),
                project_id=project_id,
                target_url=target_url,
            )
            results[fn_id] = result.get("pmi_section") or {}
            logger.info("function_tested", task_id=task_id, function_id=fn_id,
                        verdict=(results[fn_id] or {}).get("verdict"))
        except Exception as exc:
            logger.error("function_test_failed", task_id=task_id, function_id=fn_id, error=str(exc))
            results[fn_id] = {"error": str(exc), "verdict": "не соответствует"}

    # Write all results back to catalog
    try:
        await save_pmi_results(document_id, results)
        _doc_tasks[task_id].update({"status": "done", "results": results})
    except Exception as exc:
        _doc_tasks[task_id].update({"status": "failed", "error": f"Ошибка записи результатов: {exc}"})

    pmi_duration.observe(time.time() - start)
    logger.info("document_task_completed", task_id=task_id, document_id=document_id,
                functions=len(results), duration=round(time.time() - start, 1))


@app.post("/api/v1/pmi/run-for-document", response_model=RunForDocumentResponse, status_code=202)
async def run_for_document(request: RunForDocumentRequest, background_tasks: BackgroundTasks):
    """
    Запустить PMI-агент для всех функций проекта и записать результаты в документ.
    Возвращает task_id для отслеживания статуса через GET /api/v1/pmi/doc-tasks/{task_id}.
    """
    # Fetch functions from catalog
    try:
        functions = await get_project_functions(request.project_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось получить функции из каталога: {exc}")

    if not functions:
        raise HTTPException(status_code=422, detail="В проекте нет функций для тестирования")

    task_id = str(uuid.uuid4())
    target_url = request.target_url or settings.target_app_url

    _doc_tasks[task_id] = {
        "status": "pending",
        "document_id": request.document_id,
        "project_id": request.project_id,
        "functions_count": len(functions),
        "results": {},
        "error": None,
    }

    background_tasks.add_task(
        _run_all_functions, task_id, request.document_id, request.project_id, functions, target_url
    )

    logger.info("doc_task_created", task_id=task_id, document_id=request.document_id,
                functions=len(functions))

    return RunForDocumentResponse(
        task_id=task_id,
        status="pending",
        functions_count=len(functions),
        message=f"Запущено тестирование {len(functions)} функций",
    )


@app.get("/api/v1/pmi/doc-tasks/{task_id}")
async def get_doc_task_status(task_id: str):
    """Статус задачи тестирования документа."""
    task = _doc_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


# ─── Draft-level task storage ────────────────────────────────────────────
_draft_tasks: dict[str, dict] = {}


class DraftForDocumentRequest(BaseModel):
    document_id: str = Field(..., description="ID документа ПМИ из catalog-service")
    project_id: str = Field(..., description="ID проекта — для выборки функций")


class DraftForDocumentResponse(BaseModel):
    task_id: str
    status: str
    functions_count: int
    message: str


async def _draft_all_functions(
    task_id: str,
    document_id: str,
    project_id: str,
    functions: list[dict],
) -> None:
    """Запускает черновой пайплайн для каждой функции и сохраняет методику в документ."""
    _draft_tasks[task_id]["status"] = "running"
    results: dict[str, dict] = {}
    start = time.time()

    for fn in functions:
        fn_id = fn["id"]
        try:
            result = await run_draft_pipeline(
                function_id=fn_id,
                function_name=fn["name"],
                function_description=fn.get("description") or fn["name"],
                acceptance_criteria=fn.get("acceptance_criteria", []),
                project_id=project_id,
            )
            results[fn_id] = result.get("pmi_section") or {}
            logger.info("function_drafted", task_id=task_id, function_id=fn_id)
        except Exception as exc:
            logger.error("function_draft_failed", task_id=task_id, function_id=fn_id, error=str(exc))
            results[fn_id] = {"error": str(exc), "verdict": "испытание не проводилось"}

    try:
        await save_pmi_results(document_id, results)
        _draft_tasks[task_id].update({"status": "done", "results": results})
    except Exception as exc:
        _draft_tasks[task_id].update({"status": "failed", "error": f"Ошибка записи методики: {exc}"})

    logger.info("draft_task_completed", task_id=task_id, document_id=document_id,
                functions=len(results), duration=round(time.time() - start, 1))


@app.post("/api/v1/pmi/draft-for-document", response_model=DraftForDocumentResponse, status_code=202)
async def draft_for_document(request: DraftForDocumentRequest, background_tasks: BackgroundTasks):
    """
    Составить методику ПМИ для всех функций проекта без запуска тестов.
    Плановщик формирует сценарии, Протоколист пишет методику.
    Результат сохраняется в документ (verdict = 'испытание не проводилось').
    """
    try:
        functions = await get_project_functions(request.project_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось получить функции из каталога: {exc}")

    if not functions:
        raise HTTPException(status_code=422, detail="В проекте нет функций для составления ПМИ")

    task_id = str(uuid.uuid4())

    _draft_tasks[task_id] = {
        "status": "pending",
        "document_id": request.document_id,
        "project_id": request.project_id,
        "functions_count": len(functions),
        "results": {},
        "error": None,
    }

    background_tasks.add_task(
        _draft_all_functions, task_id, request.document_id, request.project_id, functions
    )

    logger.info("draft_task_created", task_id=task_id, document_id=request.document_id,
                functions=len(functions))

    return DraftForDocumentResponse(
        task_id=task_id,
        status="pending",
        functions_count=len(functions),
        message=f"Составление методики ПМИ для {len(functions)} функций запущено",
    )


@app.get("/api/v1/pmi/draft-tasks/{task_id}")
async def get_draft_task_status(task_id: str):
    """Статус задачи составления методики ПМИ."""
    task = _draft_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


@app.post("/api/v1/knowledge/reload")
async def reload_knowledge():
    """Перезагрузить knowledge base в ChromaDB (force=True)."""
    try:
        loader = KnowledgeLoader()
        chunks = loader.load_all(force=True)
        return {"status": "ok", "chunks_loaded": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
