"""Smoke - 배포 직후 가장 먼저 확인하는 최소 항목.

    pytest -m smoke
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from pages.example_page import TodoPage
from utils.steps import test_step


@pytest.mark.smoke
@pytest.mark.tc_id("SMK001")
@pytest.mark.category("Todo")
def test_home_page_opens(page: Page) -> None:
    """메인 화면 접속 및 기본 요소 노출"""
    todo = TodoPage(page)

    with test_step("메인 화면 접속"):
        todo.open()

    with test_step("제목과 입력창 확인"):
        expect(todo.heading).to_be_visible()
        expect(todo.new_todo_input).to_be_visible()


@pytest.mark.smoke
@pytest.mark.tc_id("SMK002")
@pytest.mark.category("Todo")
def test_basic_input_works(page: Page) -> None:
    """입력 후 목록 반영 여부"""
    todo = TodoPage(page)
    todo.open().add_todo("smoke check")
    expect(todo.todo_items).to_have_count(1)
