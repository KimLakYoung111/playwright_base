"""Regression - 회귀 테스트 집합.

    pytest -m regression

각 테스트는 서로 독립적이어야 합니다.
앞 테스트가 만들어둔 상태에 의존하지 않습니다.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from pages.example_page import TodoPage
from utils.steps import test_step


@pytest.mark.regression
@pytest.mark.tc_id("REG001")
@pytest.mark.category("Todo")
def test_todo_order_is_kept(page: Page) -> None:
    """추가한 순서대로 목록에 쌓인다"""
    todo = TodoPage(page)
    todo.open().add_todos(["첫 번째", "두 번째", "세 번째"])
    expect(todo.todo_titles).to_have_text(["첫 번째", "두 번째", "세 번째"])


@pytest.mark.regression
@pytest.mark.tc_id("REG002")
@pytest.mark.category("Todo")
def test_toggle_all_completes(page: Page) -> None:
    """Mark all as complete 동작"""
    todo = TodoPage(page)

    with test_step("두 건 추가"):
        todo.open().add_todos(["회의록 정리", "테스트 케이스 작성"])

    with test_step("전체 완료 체크"):
        todo.toggle_all.check()

    with test_step("남은 개수 확인"):
        expect(todo.filter_bar.remaining_count).to_have_text("0 items left")


@pytest.mark.regression
@pytest.mark.tc_id("REG003")
@pytest.mark.category("Todo")
def test_clear_completed_items(page: Page) -> None:
    """Clear completed 를 누르면 완료 항목만 사라진다"""
    todo = TodoPage(page)

    with test_step("두 건 추가 후 하나만 완료"):
        todo.open().add_todos(["남길 항목", "지울 항목"])
        todo.complete(1)

    with test_step("완료 항목 일괄 삭제"):
        todo.clear_completed()

    with test_step("남은 항목 확인"):
        expect(todo.todo_titles).to_have_text(["남길 항목"])


@pytest.mark.regression
@pytest.mark.tc_id("REG004")
@pytest.mark.category("Todo")
def test_filter_changes_url(page: Page) -> None:
    """Active 필터 선택 시 URL 확인"""
    todo = TodoPage(page)
    todo.open().add_todo("필터 확인용")
    todo.show_only("Active")
    expect(page).to_have_url(re.compile(r".*#/active$"))
