"""자주 쓰는 검증 helper.

원칙: Playwright 의 ``expect()`` 를 그대로 쓰는 것이 기본입니다.
여기 있는 함수는 "여러 곳에서 똑같이 반복되는 검증"만 모아둔 것이고,
새로운 wrapper 를 늘리는 것보다 ``expect()`` 를 직접 쓰는 쪽을 우선하세요.

    # 이게 기본
    expect(page.get_by_role("heading")).to_be_visible()

    # 검증 의도를 로그에 남기고 싶을 때만
    should_be_visible(page.get_by_role("heading"), "대시보드 제목")
"""

from __future__ import annotations

from playwright.sync_api import APIResponse, Locator, Page, Response, expect

from utils.logger import get_logger

logger = get_logger("assert")


def should_be_visible(locator: Locator, description: str = "") -> None:
    logger.info("검증: %s 표시됨", description or locator)
    expect(locator).to_be_visible()


def should_be_hidden(locator: Locator, description: str = "") -> None:
    logger.info("검증: %s 숨겨짐", description or locator)
    expect(locator).to_be_hidden()


def should_have_text(locator: Locator, expected: str, description: str = "") -> None:
    logger.info("검증: %s 텍스트 == %r", description or locator, expected)
    expect(locator).to_have_text(expected)


def should_contain_text(locator: Locator, expected: str, description: str = "") -> None:
    logger.info("검증: %s 텍스트에 %r 포함", description or locator, expected)
    expect(locator).to_contain_text(expected)


def should_have_count(locator: Locator, expected: int, description: str = "") -> None:
    logger.info("검증: %s 개수 == %d", description or locator, expected)
    expect(locator).to_have_count(expected)


def should_have_url(page: Page, expected: str | object) -> None:
    """expected 는 문자열 또는 정규식(re.compile) 모두 가능합니다."""
    logger.info("검증: URL == %r", expected)
    expect(page).to_have_url(expected)


def should_have_title(page: Page, expected: str | object) -> None:
    logger.info("검증: title == %r", expected)
    expect(page).to_have_title(expected)


def should_have_status(response: APIResponse | Response, expected: int) -> None:
    """응답 상태코드 확인. 실패 시 본문 앞부분을 함께 보여줍니다.

    ``page.request`` 의 APIResponse 와 페이지가 받은 Response 둘 다 됩니다.
    """
    logger.info("검증: 응답 상태 == %d", expected)
    if response.status != expected:
        body = response.text()[:500]
        raise AssertionError(
            f"응답 상태가 다릅니다. 기대: {expected}, 실제: {response.status}\n"
            f"URL: {response.url}\n본문(앞 500자): {body}"
        )
