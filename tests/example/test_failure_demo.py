"""Evidence / 리포트 검증용 의도적 실패 테스트.

기본 실행(``pytest``)에서는 제외됩니다. (pytest.ini 의 -m "not failure_demo")
Evidence 가 제대로 남는지 확인할 때만 돌립니다.

    pytest -m failure_demo

실행 후 artifacts/<실행시각>/ 아래에 아래 파일들이 생기는지 확인하세요.

    screenshots/TC901_*.png
    traces/TC901_*.zip
    html/TC901_*.html
    logs/TC901_*.log
    report/report.html
    report/pytest_report.html
    report/result.json
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from pages.example_page import TodoPage
from utils.steps import test_step


@pytest.mark.failure_demo
@pytest.mark.tc_id("TC901")
@pytest.mark.category("Todo")
def test_missing_element_fails(page: Page) -> None:
    """존재하지 않는 요소를 기다리다 실패 (Evidence 확인용)"""
    todo = TodoPage(page)

    with test_step("화면 접속"):
        todo.open()

    with test_step("할 일 한 건 추가"):
        todo.add_todo("여기까지는 정상")

    with test_step("존재하지 않는 대시보드 확인 (여기서 실패)"):
        expect(page.get_by_role("heading", name="대시보드")).to_be_visible(timeout=3000)


@pytest.mark.failure_demo
@pytest.mark.tc_id("TC902")
@pytest.mark.category("Todo")
def test_wrong_expectation_fails(page: Page) -> None:
    """텍스트 비교가 어긋나 실패 (Evidence 확인용)"""
    todo = TodoPage(page)

    with test_step("화면 접속 후 한 건 추가"):
        todo.open().add_todo("회의록 정리")

    with test_step("남은 개수를 일부러 틀리게 비교 (여기서 실패)"):
        expect(todo.filter_bar.remaining_count).to_have_text("99 items left", timeout=3000)


@pytest.mark.failure_demo
@pytest.mark.tc_id("TC903")
@pytest.mark.category("Todo")
def test_skipped_example(page: Page) -> None:
    """Skip 이 리포트에 어떻게 보이는지 확인용"""
    pytest.skip("아직 개발되지 않은 기능입니다.")
