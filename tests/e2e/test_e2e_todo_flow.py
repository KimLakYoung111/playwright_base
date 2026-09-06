"""E2E Scenario - 업무 흐름 단위 테스트.

일반 TC 는 서로 독립적이어야 하지만, 실제 업무 흐름을 그대로 따라가야 하는
시나리오는 여기에 따로 모읍니다. 흐름 안에서는 순서 의존을 허용하되
"한 테스트 함수 안"에서만 이어지게 하고, 테스트 함수끼리는 여전히 독립적으로 둡니다.

    pytest -m e2e
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from pages.example_page import TodoPage
from utils.steps import test_step


@pytest.mark.e2e
@pytest.mark.tc_id("E2E001")
@pytest.mark.category("Todo")
def test_todo_full_flow(page: Page) -> None:
    """등록 → 완료 → 필터 확인 → 정리까지 한 흐름"""
    todo = TodoPage(page)

    with test_step("화면 접속"):
        todo.open()

    with test_step("할 일 세 건 등록"):
        todo.add_todos(["요구사항 정리", "테스트 설계", "자동화 스크립트 작성"])
        expect(todo.todo_items).to_have_count(3)

    with test_step("두 건 완료 처리"):
        todo.complete(0)
        todo.complete(1)
        expect(todo.filter_bar.remaining_count).to_have_text("1 item left")

    with test_step("Active 필터에 남은 항목만 보이는지 확인"):
        todo.show_only("Active")
        expect(todo.todo_titles).to_have_text(["자동화 스크립트 작성"])

    with test_step("완료 항목 정리 후 상태 확인"):
        todo.show_only("All")
        todo.clear_completed()
        expect(todo.todo_titles).to_have_text(["자동화 스크립트 작성"])
        expect(todo.filter_bar.remaining_count).to_have_text("1 item left")
