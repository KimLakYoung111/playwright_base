"""예제 Component - TodoMVC 하단 필터 바.

Component 를 어떻게 쓰는지 보여주는 샘플입니다.
새 프로젝트에서는 이 파일을 지우고 실제 화면의 공통 영역으로 바꿔 쓰세요.
"""

from __future__ import annotations

from playwright.sync_api import Locator

from components.base_component import BaseComponent


class FilterBar(BaseComponent):
    """All / Active / Completed 필터와 남은 개수 표시 영역."""

    @property
    def remaining_count(self) -> Locator:
        return self.root.get_by_test_id("todo-count")

    def filter_link(self, name: str) -> Locator:
        """name: All | Active | Completed"""
        return self.root.get_by_role("link", name=name)

    @property
    def clear_completed_button(self) -> Locator:
        return self.root.get_by_role("button", name="Clear completed")
