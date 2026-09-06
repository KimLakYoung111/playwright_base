"""Component 공통 부모.

Component 는 "화면 전체"가 아니라 "화면 안의 한 영역"입니다.
자기 영역을 가리키는 root Locator 를 받아서, 그 안에서만 요소를 찾습니다.
그래서 같은 컴포넌트가 한 화면에 여러 개 있어도 서로 헷갈리지 않습니다.

    class Header(BaseComponent):
        @property
        def logout_button(self):
            return self.root.get_by_role("button", name="로그아웃")

    header = Header(page, page.get_by_role("banner"))
    header.logout_button.click()
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


class BaseComponent:
    def __init__(self, page: Page, root: Locator | None = None) -> None:
        self.page = page
        self.root = root if root is not None else page.locator("body")

    def should_be_visible(self) -> "BaseComponent":
        expect(self.root).to_be_visible()
        return self
