"""
Инструмент браузера — Playwright через CDP-соединение к контейнеру playwright.
Исполняет шаги тест-плана и возвращает результаты.
"""

import base64
import json
import time
from pathlib import Path

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
    TimeoutError as PlaywrightTimeout,
)

from config import settings
from schemas import StepResult, StepStatus, TestStep

logger = structlog.get_logger(__name__)

OUTPUTS_DIR = Path(settings.outputs_dir)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


class BrowserTool:
    """
    Управляет браузером Playwright через CDP.
    Жизненный цикл: один экземпляр на всю сессию тестирования одной функции.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> None:
        """Подключиться к CDP-брокеру (браузер в отдельном контейнере)."""
        self._playwright = await async_playwright().start()
        # Подключаемся к уже запущенному Chromium через CDP
        cdp_ws = await self._get_cdp_ws_endpoint()
        self._browser = await self._playwright.chromium.connect_over_cdp(cdp_ws)
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        self._page = await self._context.new_page()
        logger.info("browser_connected", cdp_url=settings.playwright_cdp_url)

    async def stop(self) -> None:
        """Закрыть контекст браузера."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("browser_disconnected")

    async def _get_cdp_ws_endpoint(self) -> str:
        """Получить WebSocket-эндпоинт CDP из JSON API."""
        import httpx
        resp = httpx.get(f"{settings.playwright_cdp_url}/json/version", timeout=10)
        data = resp.json()
        ws_url = data.get("webSocketDebuggerUrl", "")
        if not ws_url:
            raise RuntimeError(f"CDP WebSocket endpoint not found: {data}")
        return ws_url

    async def execute_step(self, step: TestStep, base_url: str) -> StepResult:
        """Выполнить один шаг тест-плана и вернуть результат."""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")

        start_ms = int(time.time() * 1000)
        try:
            result = await self._dispatch_step(step, base_url)
            duration = int(time.time() * 1000) - start_ms
            return StepResult(
                step_number=step.step_number,
                status=StepStatus.PASSED,
                actual_result=result["actual_result"],
                screenshot_path=result.get("screenshot_path"),
                http_response=result.get("http_response"),
                duration_ms=duration,
            )
        except PlaywrightTimeout as e:
            screenshot = await self._take_screenshot(step.step_number, "timeout")
            return StepResult(
                step_number=step.step_number,
                status=StepStatus.FAILED,
                actual_result=f"Timeout: элемент не найден за {settings.playwright_timeout}мс",
                screenshot_path=screenshot,
                error_message=str(e),
                duration_ms=int(time.time() * 1000) - start_ms,
            )
        except Exception as e:
            logger.error("step_failed", step=step.step_number, error=str(e))
            screenshot = await self._take_screenshot(step.step_number, "error")
            return StepResult(
                step_number=step.step_number,
                status=StepStatus.FAILED,
                actual_result=f"Ошибка выполнения: {e}",
                screenshot_path=screenshot,
                error_message=str(e),
                duration_ms=int(time.time() * 1000) - start_ms,
            )

    async def _dispatch_step(self, step: TestStep, base_url: str) -> dict:
        """Маршрутизация шага по типу действия."""
        page = self._page
        timeout = settings.playwright_timeout

        match step.action:
            case "navigate":
                url = step.target or ""
                if not url.startswith("http"):
                    url = base_url.rstrip("/") + "/" + url.lstrip("/")
                await page.goto(url, wait_until="networkidle", timeout=timeout * 3)
                screenshot = await self._take_screenshot(step.step_number, "navigate")
                return {
                    "actual_result": f"Страница загружена: {page.url}",
                    "screenshot_path": screenshot,
                }

            case "click":
                selector = step.target or ""
                await page.wait_for_selector(selector, timeout=timeout)
                await page.click(selector)
                await page.wait_for_load_state("networkidle", timeout=timeout * 2)
                screenshot = await self._take_screenshot(step.step_number, "after_click")
                return {
                    "actual_result": f"Клик выполнен по '{selector}'. URL: {page.url}",
                    "screenshot_path": screenshot,
                }

            case "fill":
                selector = step.target or ""
                value = step.input_data or ""
                await page.wait_for_selector(selector, timeout=timeout)
                await page.fill(selector, value)
                return {"actual_result": f"Поле '{selector}' заполнено"}

            case "assert":
                return await self._execute_assert(step)

            case "screenshot":
                screenshot = await self._take_screenshot(step.step_number, "manual")
                return {
                    "actual_result": f"Скриншот сохранен: {screenshot}",
                    "screenshot_path": screenshot,
                }

            case "api_call":
                return await self._execute_api_call(step, base_url)

            case _:
                return {"actual_result": f"Неизвестный тип действия: {step.action}"}

    async def _execute_assert(self, step: TestStep) -> dict:
        """Выполнить проверку (assert)."""
        page = self._page
        target = step.target or ""

        if target == "url":
            current_url = page.url
            expected = step.expected_result
            passed = expected.lower() in current_url.lower()
            return {
                "actual_result": f"Текущий URL: {current_url}. "
                                 f"{'Содержит' if passed else 'НЕ содержит'} '{expected}'",
            }

        if target.startswith("localStorage."):
            key = target.removeprefix("localStorage.")
            value = await page.evaluate(f"localStorage.getItem('{key}')")
            return {
                "actual_result": f"localStorage['{key}'] = {repr(value)}",
            }

        # Проверка видимости CSS-селектора
        is_visible = await page.is_visible(target, timeout=3000)
        screenshot = await self._take_screenshot(step.step_number, "assert")
        return {
            "actual_result": f"Элемент '{target}' "
                             f"{'виден' if is_visible else 'НЕ виден'} на странице",
            "screenshot_path": screenshot,
        }

    async def _execute_api_call(self, step: TestStep, base_url: str) -> dict:
        """Выполнить HTTP-запрос и вернуть ответ."""
        url = step.target or ""
        if not url.startswith("http"):
            url = base_url.rstrip("/") + url

        # Перехватываем через Playwright request API
        response = await self._page.request.get(url)
        body: str | None = None
        try:
            body = await response.json()
        except Exception:
            body = await response.text()

        return {
            "actual_result": f"HTTP {response.status} от {url}",
            "http_response": {
                "status": response.status,
                "url": url,
                "body": body,
            },
        }

    async def _take_screenshot(self, step_number: int, label: str) -> str:
        """Сделать скриншот и сохранить в outputs/."""
        filename = OUTPUTS_DIR / f"step_{step_number:03d}_{label}.png"
        try:
            await self._page.screenshot(path=str(filename), full_page=False)
            return str(filename)
        except Exception as e:
            logger.warning("screenshot_failed", step=step_number, error=str(e))
            return ""
