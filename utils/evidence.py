"""실패 원인 분석용 Evidence 저장.

저장 대상: Screenshot / 현재 URL / Page HTML / Playwright Trace / 로그

파일 이름은 TC 를 바로 알아볼 수 있게 만듭니다.

    TC023_로그인_실패.png
    TC023_로그인_실패.zip     (Trace)
    TC023_로그인_실패.html
    TC023_로그인_실패.log
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page

from utils.logger import get_logger
from utils.paths import RunPaths
from utils.testmeta import TestMeta

logger = get_logger("evidence")


def should_capture(mode: str, failed: bool) -> bool:
    """설정값(always / on-failure / never)에 따라 저장할지 결정합니다.

    값의 유효성은 utils.config._evidence_mode 에서 미리 검사하므로
    (오타는 설정 로딩 단계에서 에러가 납니다) 여기서는 판단만 합니다.
    """
    mode = (mode or "on-failure").lower()
    if mode == "always":
        return True
    if mode == "never":
        return False
    return failed


def unique_path(path: Path) -> Path:
    """같은 테스트가 재시도로 두 번 실패해도 파일이 덮이지 않게 합니다.

    Screenshot / Trace / HTML / Log 모두 이 함수를 거칩니다.
    """
    if not path.exists():
        return path
    stem, suffix, index = path.stem, path.suffix, 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def capture_screenshot(page: Page, paths: RunPaths, meta: TestMeta,
                       label: str = "") -> Path | None:
    """전체 페이지 스크린샷."""
    if page.is_closed():
        return None
    name = f"{meta.slug}_{label}" if label else meta.slug
    target = unique_path(paths.screenshots / f"{name}.png")
    try:
        page.screenshot(path=str(target), full_page=True)
        return target
    except (PlaywrightError, OSError) as exc:
        # 경로가 너무 길거나 디스크가 찼을 때 OSError 가 납니다.
        # 여기서 새어나가면 이후 Trace 저장까지 통째로 건너뛰게 됩니다.
        logger.warning("Screenshot 저장 실패: %s", exc)
        return None


def capture_page_html(page: Page, paths: RunPaths, meta: TestMeta,
                      label: str = "") -> Path | None:
    """실패 시점의 DOM 을 그대로 저장합니다."""
    if page.is_closed():
        return None
    name = f"{meta.slug}_{label}" if label else meta.slug
    target = unique_path(paths.html / f"{name}.html")
    try:
        target.write_text(page.content(), encoding="utf-8")
        return target
    except (PlaywrightError, OSError) as exc:
        logger.warning("Page HTML 저장 실패: %s", exc)
        return None


def current_url(page: Page) -> str | None:
    try:
        return None if page.is_closed() else page.url
    except PlaywrightError:
        return None


def start_tracing(context: BrowserContext) -> bool:
    """Trace 수집 시작. 실패해도 테스트는 계속 진행합니다."""
    try:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        return True
    except PlaywrightError as exc:
        logger.warning("Trace 시작 실패: %s", exc)
        return False


def stop_tracing(context: BrowserContext, paths: RunPaths | None,
                 meta: TestMeta | None, keep: bool, label: str = "") -> Path | None:
    """Trace 수집 종료. ``keep`` 이 False 면 저장하지 않고 버립니다."""
    try:
        if not keep or paths is None or meta is None:
            context.tracing.stop()
            return None
        name = f"{meta.slug}_{label}" if label else meta.slug
        target = unique_path(paths.traces / f"{name}.zip")
        context.tracing.stop(path=str(target))
        return target
    except (PlaywrightError, OSError) as exc:
        logger.warning("Trace 저장 실패: %s", exc)
        return None


# ----------------------------------------------------------------------
# 위 함수들을 묶어 쓰는 진입점
#   conftest 의 page fixture 와 fixtures/auth.py 의 역할별 Context 가
#   같은 규칙으로 Evidence 를 남기도록 여기 한 곳에 모읍니다.
# ----------------------------------------------------------------------
def capture_page_evidence(page: Page, paths: RunPaths, meta: TestMeta,
                          config, failed: bool, label: str = "") -> None:
    """실패(또는 always 설정) 시 현재 URL / Screenshot / Page HTML 을 남깁니다."""
    from utils.testmeta import record_artifact       # 순환 import 방지

    url = current_url(page)
    if url and not meta.current_url:
        meta.current_url = url

    if should_capture(config.screenshot_mode, failed):
        record_artifact(meta, "screenshot",
                        paths.relative(capture_screenshot(page, paths, meta, label)), label)

    if should_capture(config.page_html_mode, failed):
        record_artifact(meta, "page_html",
                        paths.relative(capture_page_html(page, paths, meta, label)), label)


def finish_tracing(context: BrowserContext, paths: RunPaths, meta: TestMeta,
                   config, failed: bool, label: str = "") -> None:
    """Trace 수집을 끝내고 필요하면 저장합니다."""
    from utils.testmeta import record_artifact

    keep = should_capture(config.trace_mode, failed)
    record_artifact(meta, "trace",
                    paths.relative(stop_tracing(context, paths, meta, keep, label)), label)


def tracing_enabled(config) -> bool:
    """trace_mode 가 never 가 아니면 수집을 시작해야 합니다.

    on-failure 여도 실패 순간을 담으려면 미리 켜 두었다가 통과 시 버려야 합니다.
    """
    return (config.trace_mode or "").lower() != "never"
