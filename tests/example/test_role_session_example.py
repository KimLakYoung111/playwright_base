"""로그인 세션 재사용 예제 (fixtures/auth.py).

TodoMVC 에는 로그인이 없어서 ``perform_login`` 을 "세션 상태를 만들어 저장한다"는
부분만 흉내내도록 갈아끼웠습니다. 실제 프로젝트에서는 이 fixture 를 지우고
``fixtures/auth.py`` 의 ``perform_login`` 을 진짜 로그인 절차로 구현하면 됩니다.

이 파일이 확인하는 것
---------------------
1. 저장한 세션(storage_state)으로 새 Context 를 열면 이전 상태가 남아 있다
2. ``role_page`` 로 만든 Page 도 실패하면 Evidence 가 남는다 (failure_demo)
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from fixtures import auth
from utils.steps import test_step

SEEDED_TODO = "세션 준비 데이터"


@pytest.fixture(scope="session", autouse=True)
def clean_demo_session(run_config):
    """예제는 매번 세션을 새로 만들어 보여줍니다 (실행당 1회).

    테스트마다 지우면 안 됩니다. storage_state_factory 가 세션 단위로
    한 번만 만들기 때문에, 중간에 지우면 다음 테스트가 없는 파일을 참조합니다.
    """
    auth.storage_state_file("user", run_config.env).unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def fake_login(monkeypatch):
    """로그인 대신 '상태를 만들어 저장'하는 동작으로 대체합니다."""

    def _login(page, config, role):
        page.goto(config.base_url)
        new_todo = page.get_by_placeholder("What needs to be done?")
        new_todo.fill(f"{role} {SEEDED_TODO}")
        new_todo.press("Enter")
        expect(page.get_by_test_id("todo-item")).to_have_count(1)

    monkeypatch.setattr(auth, "perform_login", _login)


@pytest.mark.tc_id("AUTH001")
@pytest.mark.category("Auth")
def test_role_session_is_reused(role_page) -> None:
    """저장한 세션으로 새 Context 를 열면 이전 상태가 그대로 남아 있다"""
    with test_step("역할 세션으로 화면 열기"):
        page = role_page("user")
        page.goto("")

    with test_step("로그인 단계에서 만든 데이터가 남아 있는지 확인"):
        expect(page.get_by_test_id("todo-title")).to_have_text([f"user {SEEDED_TODO}"])


@pytest.mark.failure_demo
@pytest.mark.tc_id("AUTH901")
@pytest.mark.category("Auth")
def test_role_page_failure_leaves_evidence(role_page) -> None:
    """role_page 로 만든 Page 도 실패 시 Evidence 가 남는지 확인 (의도적 실패)"""
    with test_step("역할 세션으로 화면 열기"):
        page = role_page("user")
        page.goto("")

    with test_step("존재하지 않는 요소 확인 (여기서 실패)"):
        expect(page.get_by_role("heading", name="대시보드")).to_be_visible(timeout=2000)
