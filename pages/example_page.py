"""예제 Page Object - TodoMVC (https://demo.playwright.dev/todomvc/)

새 프로젝트에서는 이 파일을 지우고 실제 화면 Page Object 로 바꿔 쓰세요.
아래 두 가지를 보여주기 위한 샘플입니다.

1. Locator 는 Page Object 안에서 property 로만 정의한다.
2. Locator 우선순위 (get_by_role > get_by_label > get_by_placeholder >
   get_by_text > data-testid > CSS) 를 지킨다.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from components.filter_bar import FilterBar
from pages.base_page import BasePage


class TodoPage(BasePage):
    """할 일 목록 화면."""

    path = ""          # base_url 자체가 TodoMVC 화면

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # 이 영역은 <section> 안의 <footer> 라 contentinfo role 이 없고 testid 도 없습니다.
        # 이렇게 role/label/testid 로 잡을 수 없을 때만 CSS 를 씁니다. (Locator 정책 참고)
        self.filter_bar = FilterBar(page, page.locator("footer.footer"))

    # ------------------------------------------------------------------
    # Locator (테스트 코드에서는 여기 있는 것만 사용)
    # ------------------------------------------------------------------
    @property
    def new_todo_input(self) -> Locator:
        return self.page.get_by_placeholder("What needs to be done?")

    @property
    def todo_titles(self) -> Locator:
        return self.page.get_by_test_id("todo-title")

    @property
    def todo_items(self) -> Locator:
        return self.page.get_by_test_id("todo-item")

    @property
    def toggle_all(self) -> Locator:
        return self.page.get_by_label("Mark all as complete")

    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name="todos")

    def toggle_checkbox(self, index: int) -> Locator:
        return self.todo_items.nth(index).get_by_role("checkbox")

    def loaded_locator(self) -> Locator:
        # open() 이 이 요소가 보일 때까지 기다립니다.
        return self.new_todo_input

    # ------------------------------------------------------------------
    # 동작
    # ------------------------------------------------------------------
    # BasePage 의 fill/press/click/check/get_text 를 거치면 동작 하나하나가
    # 로그에 남습니다. 그 로그는 실패 시 Evidence 로 저장됩니다.
    # 로그가 필요 없는 곳은 Locator 를 직접 써도 됩니다 (아래 expect 검증처럼).
    def add_todo(self, text: str) -> "TodoPage":
        self.fill(self.new_todo_input, text)
        self.press(self.new_todo_input, "Enter")
        return self

    def add_todos(self, texts: list[str]) -> "TodoPage":
        for text in texts:
            self.add_todo(text)
        return self

    def complete(self, index: int) -> "TodoPage":
        self.check(self.toggle_checkbox(index))
        return self

    def remaining_text(self) -> str:
        return self.get_text(self.filter_bar.remaining_count)

    def todo_count(self) -> int:
        return self.count(self.todo_items)

    def titles(self) -> list[str]:
        return self.get_texts(self.todo_titles)

    def show_only(self, filter_name: str) -> "TodoPage":
        """filter_name: All | Active | Completed"""
        self.click(self.filter_bar.filter_link(filter_name))
        return self

    def clear_completed(self) -> "TodoPage":
        self.click(self.filter_bar.clear_completed_button)
        return self
