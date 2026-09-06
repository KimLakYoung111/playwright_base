"""까다로운 상호작용 helper (Popup / Download / Dialog / iframe / API 대기).

Playwright 의 Auto Waiting 이 대부분을 알아서 처리하므로 ``time.sleep()`` 은
쓰지 않습니다. 아래 helper 들은 "이벤트가 생길 때까지 기다리는" 패턴만 감싼 것이고,
전부 ``expect_*`` 컨텍스트 매니저 위에 얇게 올려져 있습니다.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Pattern

from playwright.sync_api import Dialog, Download, FrameLocator, Page, Response

from utils.logger import get_logger

logger = get_logger("interaction")


# ----------------------------------------------------------------------
# 새 창 / Popup
# ----------------------------------------------------------------------
def open_popup(page: Page, trigger: Callable[[], None], timeout: float | None = None) -> Page:
    """클릭 등으로 열리는 새 창(Popup)을 받아옵니다.

        popup = open_popup(page, lambda: page.get_by_role("link", name="약관").click())
        expect(popup.get_by_role("heading")).to_be_visible()
    """
    with page.expect_popup(timeout=timeout) as popup_info:
        trigger()
    popup = popup_info.value
    popup.wait_for_load_state()
    logger.info("Popup 열림: %s", popup.url)
    return popup


def open_new_tab(page: Page, trigger: Callable[[], None], timeout: float | None = None) -> Page:
    """target=_blank 처럼 Context 에 새 Page 가 생기는 경우."""
    with page.context.expect_page(timeout=timeout) as page_info:
        trigger()
    new_page = page_info.value
    new_page.wait_for_load_state()
    logger.info("새 탭 열림: %s", new_page.url)
    return new_page


# ----------------------------------------------------------------------
# iframe
# ----------------------------------------------------------------------
def frame(page: Page, selector: str) -> FrameLocator:
    """iframe 안의 요소를 다루는 FrameLocator 를 돌려줍니다.

        f = frame(page, "#payment")
        f.get_by_label("카드번호").fill("...")
    """
    return page.frame_locator(selector)


# ----------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------
def download_file(page: Page, trigger: Callable[[], None], save_dir: Path,
                  timeout: float | None = None) -> Path:
    """다운로드를 기다렸다가 지정 폴더에 저장하고 경로를 돌려줍니다."""
    with page.expect_download(timeout=timeout) as download_info:
        trigger()
    download: Download = download_info.value
    save_dir.mkdir(parents=True, exist_ok=True)
    target = save_dir / download.suggested_filename
    download.save_as(target)
    logger.info("다운로드 저장: %s", target)
    return target


# ----------------------------------------------------------------------
# Dialog (alert / confirm / prompt)
# ----------------------------------------------------------------------
@contextmanager
def handle_dialog(page: Page, accept: bool = True,
                  prompt_text: str | None = None) -> Iterator[list[str]]:
    """alert/confirm/prompt 를 자동 처리합니다. 메시지 목록을 돌려줍니다.

        with handle_dialog(page, accept=True) as messages:
            page.get_by_role("button", name="삭제").click()
        assert messages == ["정말 삭제할까요?"]

    Playwright 는 핸들러가 없으면 dialog 를 자동으로 dismiss 하므로
    "확인을 눌러야 진행되는" 흐름에서만 쓰면 됩니다.
    """
    messages: list[str] = []

    def _on_dialog(dialog: Dialog) -> None:
        messages.append(dialog.message)
        logger.info("Dialog(%s): %s", dialog.type, dialog.message)
        if accept:
            dialog.accept(prompt_text) if prompt_text is not None else dialog.accept()
        else:
            dialog.dismiss()

    page.on("dialog", _on_dialog)
    try:
        yield messages
    finally:
        page.remove_listener("dialog", _on_dialog)


# ----------------------------------------------------------------------
# API 응답 대기
# ----------------------------------------------------------------------
def wait_for_response(page: Page, url_pattern: str | Pattern[str],
                      trigger: Callable[[], None],
                      timeout: float | None = None) -> Response:
    """버튼을 눌렀을 때 특정 API 응답이 올 때까지 기다립니다.

        res = wait_for_response(page, "**/api/orders", lambda: page.get_by_role(
            "button", name="주문").click())
        assert res.status == 200
    """
    with page.expect_response(url_pattern, timeout=timeout) as response_info:
        trigger()
    response = response_info.value
    logger.info("응답 수신: %s %s", response.status, response.url)
    return response


def wait_for_network_idle(page: Page, timeout: float | None = None) -> None:
    """꼭 필요한 경우에만 사용하세요. 보통은 expect() 로 요소를 기다리는 편이 안정적입니다."""
    page.wait_for_load_state("networkidle", timeout=timeout)
