"""기본 예제 테스트.

구조를 확인하기 위한 샘플입니다. 다음 흐름을 모두 담고 있습니다.

    1. 사이트 접속
    2. Element 확인
    3. 입력
    4. 클릭
    5. Assertion
    6. PASS

새 프로젝트에서는 이 파일을 지우고 실제 테스트로 바꿔 쓰세요.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from pages.example_page import TodoPage
from utils.assertions import should_be_hidden, should_have_title, should_have_url
from utils.data_loader import load_data, pick
from utils.steps import test_step


@pytest.mark.smoke
@pytest.mark.tc_id("TC001")
@pytest.mark.category("Todo")
def test_add_todo(page: Page) -> None:
    """할 일을 추가하면 목록에 보인다"""
    todo = TodoPage(page)

    with test_step("화면 접속"):
        todo.open()

    with test_step("입력창이 보이는지 확인"):
        expect(todo.new_todo_input).to_be_visible()

    with test_step("할 일 입력 후 Enter"):
        todo.add_todo("자동화 Base 프로젝트 만들기")

    with test_step("목록에 추가됐는지 확인"):
        expect(todo.todo_titles).to_have_text(["자동화 Base 프로젝트 만들기"])
        expect(todo.todo_items).to_have_count(1)


@pytest.mark.smoke
@pytest.mark.tc_id("TC002")
@pytest.mark.category("Todo")
def test_complete_todo(page: Page) -> None:
    """할 일을 완료하면 남은 개수가 줄어든다"""
    todo = TodoPage(page)

    with test_step("화면 접속 후 두 건 추가"):
        todo.open().add_todos(["회의록 정리", "테스트 케이스 작성"])

    with test_step("첫 번째 항목 완료 처리"):
        todo.complete(0)

    with test_step("남은 개수 확인"):
        expect(todo.filter_bar.remaining_count).to_have_text("1 item left")


@pytest.mark.tc_id("TC003")
@pytest.mark.category("Todo")
def test_filter_completed(page: Page) -> None:
    """Completed 필터를 누르면 완료한 항목만 보인다"""
    todo = TodoPage(page)

    with test_step("화면 접속 후 두 건 추가"):
        todo.open().add_todos(["회의록 정리", "테스트 케이스 작성"])

    with test_step("두 번째 항목 완료 처리"):
        todo.complete(1)

    with test_step("Completed 필터 선택"):
        todo.show_only("Completed")

    with test_step("완료 항목만 보이는지 확인"):
        expect(todo.todo_titles).to_have_text(["테스트 케이스 작성"])


@pytest.mark.tc_id("TC004")
@pytest.mark.category("Todo")
@pytest.mark.parametrize(
    "case",
    load_data("test_cases.yaml")["todo_cases"],
    ids=lambda case: case["id"],
)
def test_remaining_count_data_driven(page: Page, case: dict) -> None:
    """데이터 파일로 케이스를 늘리는 예시"""
    todo = TodoPage(page)

    with test_step(f"{case['description']}"):
        todo.open().add_todos(case["todos"])
        if case["complete_index"] is not None:
            todo.complete(case["complete_index"])
        expect(todo.filter_bar.remaining_count).to_have_text(case["expected_remaining"])


@pytest.mark.tc_id("TC006")
@pytest.mark.category("Todo")
def test_csv_data_becomes_todos(page: Page) -> None:
    """CSV 파일을 읽어 화면에 넣는 예시 (JSON/YAML 과 쓰는 방법이 같습니다)"""
    todo = TodoPage(page)

    with test_step("주문 CSV 읽기"):
        orders = load_data("orders.csv")          # list[dict]
        pending = [row for row in orders if row["status"] != "취소"]

    with test_step("취소되지 않은 주문만 할 일로 등록"):
        todo.open().add_todos([f"{row['order_id']} {row['customer']}" for row in pending])

    with test_step("등록 결과 확인"):
        assert todo.todo_count() == len(pending)
        assert todo.titles()[0] == f"{pending[0]['order_id']} {pending[0]['customer']}"
        assert pick("orders.csv", "0.order_id") == "ORD-001"


@pytest.mark.tc_id("TC005")
@pytest.mark.category("Todo")
def test_config_is_injected(page: Page, run_config) -> None:
    """테스트에서 실행 설정을 그대로 참조할 수 있다"""
    with test_step("환경 / URL 확인"):
        assert run_config.env in ("dev", "staging", "prod")
        assert run_config.base_url, "base_url 이 설정되지 않았습니다."

    with test_step("계정 정보 (비밀번호는 .env 에서만 옴)"):
        account = run_config.account("user")
        assert account.username == "standard_user"
        assert "password" not in repr(account).lower() or "***" in repr(account)

    with test_step("프로젝트별 설정값 꺼내 쓰기"):
        assert run_config.get("features.new_checkout") is True
        assert run_config.get("features.없는키", "기본값") == "기본값"

    with test_step("하드코딩 없이 설정된 URL 로 이동"):
        todo = TodoPage(page)
        todo.open()
        should_have_url(page, run_config.base_url + "#/")
        should_have_title(page, "React • TodoMVC")
        assert todo.current_url.startswith(run_config.base_url)


@pytest.mark.tc_id("TC007")
@pytest.mark.category("Todo")
def test_component_and_page_helpers(page: Page) -> None:
    """Component 와 Page Object 의 보조 메서드 사용 예시"""
    todo = TodoPage(page)

    with test_step("할 일 두 건 추가"):
        todo.open().add_todos(["회의록 정리", "테스트 케이스 작성"])

    with test_step("Component 가 화면에 있는지 확인"):
        todo.filter_bar.should_be_visible()

    with test_step("남은 개수를 문자열로 읽기"):
        assert todo.remaining_text() == "2 items left"

    with test_step("전체 완료 후 목록이 비는지 확인"):
        todo.complete(0)
        todo.complete(1)
        todo.show_only("Active")
        should_be_hidden(todo.todo_items.first, "Active 목록의 첫 항목")
