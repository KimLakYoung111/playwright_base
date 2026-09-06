"""모든 Page Object 의 부모 클래스.

설계 원칙
---------
1. Playwright API 를 감추지 않습니다. ``self.page`` 를 그대로 쓸 수 있습니다.
2. 여기 있는 메서드는 "거의 모든 화면에서 반복되는 것"만 둡니다.
   화면 고유 동작은 각 Page Object 에 씁니다.
3. Locator 는 Page Object 안에서만 정의하고 테스트 코드에는 쓰지 않습니다.
4. ``time.sleep()`` 은 쓰지 않습니다. Auto Waiting + ``expect()`` 로 기다립니다.

사용 예
-------
    class LoginPage(BasePage):
        path = "login"

        @property
        def username(self):
            return self.page.get_by_label("아이디")

        def login(self, username, password):
            self.username.fill(username)
            self.page.get_by_role("button", name="로그인").click()
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from playwright.sync_api import Locator, Page, expect

from utils.logger import get_logger

logger = get_logger("page")

SelectorLike = str | Locator


class BasePage:
    """Page Object 공통 기능."""

    #: base_url 뒤에 붙는 경로. 예) "login", "orders/new"
    path: str = ""

    #: 화면이 떴는지 판단하는 기준 요소를 각 Page 에서 정의하면
    #: open() 이 자동으로 기다려 줍니다. (없으면 생략)
    def loaded_locator(self) -> Locator | None:
        return None

    def __init__(self, page: Page) -> None:
        self.page = page
        self.name = type(self).__name__

    # ------------------------------------------------------------------
    # 이동
    # ------------------------------------------------------------------
    def open(self, path: str | None = None, **kwargs) -> "BasePage":
        """화면을 엽니다. base_url 은 Browser Context 에 이미 설정돼 있습니다."""
        target = self.path if path is None else path
        logger.info("[%s] 화면 열기: %s", self.name, target or "(base_url)")
        self.page.goto(target or "", **kwargs)
        self.wait_until_loaded()
        return self

    def goto(self, url: str, **kwargs) -> "BasePage":
        """절대 URL 로 이동합니다."""
        logger.info("[%s] 이동: %s", self.name, url)
        self.page.goto(url, **kwargs)
        return self

    def wait_until_loaded(self) -> "BasePage":
        locator = self.loaded_locator()
        if locator is not None:
            expect(locator).to_be_visible()
        return self

    def reload(self) -> "BasePage":
        self.page.reload()
        return self.wait_until_loaded()

    # ------------------------------------------------------------------
    # 조작
    # ------------------------------------------------------------------
    def locator(self, selector: SelectorLike) -> Locator:
        """문자열이면 Locator 로 바꿔주고, Locator 면 그대로 씁니다."""
        return self.page.locator(selector) if isinstance(selector, str) else selector

    def click(self, selector: SelectorLike, **kwargs) -> None:
        logger.info("[%s] 클릭: %s", self.name, selector)
        self.locator(selector).click(**kwargs)

    def fill(self, selector: SelectorLike, value: str, **kwargs) -> None:
        logger.info("[%s] 입력: %s", self.name, selector)
        self.locator(selector).fill(value, **kwargs)

    def type_text(self, selector: SelectorLike, value: str, delay: float = 50) -> None:
        """한 글자씩 입력해야 동작하는 자동완성 같은 화면에서 사용합니다."""
        self.locator(selector).press_sequentially(value, delay=delay)

    def select_option(self, selector: SelectorLike, value: str | Sequence[str], **kwargs) -> list[str]:
        logger.info("[%s] 선택: %s = %s", self.name, selector, value)
        return self.locator(selector).select_option(value, **kwargs)

    def check(self, selector: SelectorLike, checked: bool = True) -> None:
        locator = self.locator(selector)
        locator.check() if checked else locator.uncheck()

    def hover(self, selector: SelectorLike) -> None:
        logger.info("[%s] hover: %s", self.name, selector)
        self.locator(selector).hover()

    def press(self, selector: SelectorLike, key: str) -> None:
        self.locator(selector).press(key)

    def scroll_to(self, selector: SelectorLike) -> None:
        """요소가 보이도록 스크롤합니다. click 등은 자동 스크롤되므로 보통은 불필요합니다."""
        self.locator(selector).scroll_into_view_if_needed()

    def upload_file(self, selector: SelectorLike, files: str | Path | Sequence[str | Path]) -> None:
        """file input 에 파일을 올립니다."""
        paths = [files] if isinstance(files, (str, Path)) else list(files)
        logger.info("[%s] 파일 업로드: %s", self.name, paths)
        self.locator(selector).set_input_files([str(p) for p in paths])

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------
    def get_text(self, selector: SelectorLike) -> str:
        return (self.locator(selector).inner_text() or "").strip()

    def get_texts(self, selector: SelectorLike) -> list[str]:
        return [t.strip() for t in self.locator(selector).all_inner_texts()]

    def get_value(self, selector: SelectorLike) -> str:
        return self.locator(selector).input_value()

    def count(self, selector: SelectorLike) -> int:
        return self.locator(selector).count()

    def is_visible(self, selector: SelectorLike) -> bool:
        return self.locator(selector).is_visible()

    @property
    def current_url(self) -> str:
        return self.page.url

    @property
    def title(self) -> str:
        return self.page.title()

    # ------------------------------------------------------------------
    # 대기 (expect 로 충분한 경우가 많으니 남용하지 마세요)
    # ------------------------------------------------------------------
    def wait_for_visible(self, selector: SelectorLike, timeout: float | None = None) -> Locator:
        locator = self.locator(selector)
        expect(locator).to_be_visible(timeout=timeout)
        return locator

    def wait_for_hidden(self, selector: SelectorLike, timeout: float | None = None) -> Locator:
        locator = self.locator(selector)
        expect(locator).to_be_hidden(timeout=timeout)
        return locator

    # ------------------------------------------------------------------
    # 기타
    # ------------------------------------------------------------------
    def screenshot(self, path: str | Path, full_page: bool = True) -> Path:
        """수동 스크린샷. 실패 시 Evidence 는 Base 가 자동으로 남기므로 보통 불필요합니다."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=full_page)
        return target
