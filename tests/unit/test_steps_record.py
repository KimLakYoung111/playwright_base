"""Step 확인값 · 사용 데이터 · 남긴 변경 기록 (schema 1.4) 단위 테스트.

PASS 옆에 기대결과만 있으면 "실제로 무엇을 봤는지·어느 건을 썼는지" 가 리포트에 남지 않습니다.
그 값을 테스트가 남기는 통로(``utils.steps``)와, 그 값이 result.json 까지 가는 길(수집기)을 못 박습니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from reporting.result_collector import ResultCollector
from utils import config as config_module
from utils import testmeta
from utils.config import load_config
from utils.steps import clear_change, record_actual, record_change, record_data, test_step

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Report")]


@pytest.fixture
def meta() -> Iterator[testmeta.TestMeta]:
    """실행 중인 테스트처럼 현재 TestMeta 를 걸어 둡니다.

    이 단위 테스트 자신도 루트 conftest 가 건 TestMeta 로 돌고 있습니다. 끝나면 그것으로 되돌려야
    이 테스트의 리포트 기록이 엉뚱한 곳에 쌓이지 않습니다.
    """
    previous = testmeta.current()
    fake = testmeta.TestMeta(test_id="TC001", title="기록 확인", category="Report")
    testmeta.set_current(fake)
    try:
        yield fake
    finally:
        testmeta.set_current(previous)


@pytest.mark.tc_id("UNIT801")
def test_actual_is_attached_to_the_open_step(meta: testmeta.TestMeta) -> None:
    """Step 안에서 남긴 확인값은 그 Step 에 순서대로 붙는다."""
    with test_step("조회", expected="금액이 11,000 줄어든다"):
        record_actual("합계금액 50,000 → 39,000")
        record_actual("주문상태 '할인'")
    assert meta.steps[0]["actual"] == ["합계금액 50,000 → 39,000", "주문상태 '할인'"]


@pytest.mark.tc_id("UNIT802")
def test_actual_outside_a_step_is_ignored(meta: testmeta.TestMeta) -> None:
    """Step 밖에서 남기면 무시한다.

    끝난 Step 에 붙이면 그 Step 이 확인하지 않은 값이 그 Step 의 확인값처럼 보입니다.
    """
    with test_step("화면 이동"):
        pass
    record_actual("준비 단계의 대조 결과")
    assert "actual" not in meta.steps[0]


@pytest.mark.tc_id("UNIT803")
def test_step_without_actual_has_no_key(meta: testmeta.TestMeta) -> None:
    """확인값이 없으면 키 자체가 없다 (schema 1.3 이전 결과와 같은 모양)."""
    with test_step("화면 이동"):
        pass
    assert "actual" not in meta.steps[0]


@pytest.mark.tc_id("UNIT804")
def test_data_keeps_order_and_overwrites(meta: testmeta.TestMeta) -> None:
    """사용 데이터는 남긴 순서대로 두고, 같은 이름은 마지막 값으로 바꾼다 (다시 고른 대상 건)."""
    record_data("주문번호", "ORD-0002")
    record_data("고객", "ACME 상사")
    record_data("주문번호", 20260001)
    assert meta.data == {"주문번호": "20260001", "고객": "ACME 상사"}


@pytest.mark.tc_id("UNIT805")
def test_change_is_replaced_and_cleared(meta: testmeta.TestMeta) -> None:
    """같은 key 로 다시 남기면 내용이 바뀌고, 되돌린 뒤에는 지운다. 없는 key 를 지워도 오류가 없다."""
    record_change("할인", "상태 '임시저장'")
    record_change("할인", "상태 '제출'")
    assert meta.changes == {"할인": "상태 '제출'"}
    clear_change("할인")
    clear_change("할인")
    assert meta.changes == {}


@pytest.mark.tc_id("UNIT810")
def test_failed_step_calls_failure_hook_once(meta: testmeta.TestMeta) -> None:
    """Step 이 실패하면 실패 순간 훅(Evidence 스크린샷)을 부르고, 예외는 그대로 올린다.

    테스트가 실패 뒤에 정리(되돌리기 등)를 하면 끝난 뒤의 화면은 실패 순간이 아닙니다 (2026-09-18 협의).
    안쪽 Step 이 실패하면 바깥 Step 도 실패로 끝나지만 훅은 한 번만 부릅니다. 통과한 Step 은 부르지 않습니다.
    """
    calls: list[int] = []
    meta.on_step_failure = lambda: calls.append(len(meta.steps))
    with test_step("통과"):
        pass
    assert calls == []
    with pytest.raises(AssertionError, match="값 불일치"):
        with test_step("바깥"):
            with test_step("안쪽"):
                raise AssertionError("값 불일치")
    assert calls == [3]


@pytest.mark.tc_id("UNIT811")
def test_failure_hook_error_does_not_hide_the_failure(meta: testmeta.TestMeta) -> None:
    """훅이 터져도 원래 실패가 그대로 올라간다 (Evidence 저장 실패가 원인을 덮으면 안 됨)."""
    def broken() -> None:
        raise OSError("디스크 가득 참")
    meta.on_step_failure = broken
    with pytest.raises(AssertionError, match="값 불일치"):
        with test_step("확인"):
            raise AssertionError("값 불일치")
    assert meta.steps[0]["status"] == "failed"


@pytest.mark.tc_id("UNIT806")
def test_record_without_running_test_does_nothing() -> None:
    """테스트 밖(현재 TestMeta 없음)에서 불러도 터지지 않는다."""
    previous = testmeta.current()
    testmeta.set_current(None)
    try:
        record_data("주문번호", "1")
        record_change("할인", "저장")
        clear_change("할인")
        record_actual("값")
    finally:
        testmeta.set_current(previous)


# ---------------------------------------------------------------------------
# 수집기: user_properties → result.json
# ---------------------------------------------------------------------------

class _FakePaths:
    run_id = "20260918_100000"
    root = Path("artifacts") / "20260918_100000"


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch) -> ResultCollector:
    # 저장소 config/*.yaml 을 읽지 않게 막습니다 (test_result_meta.py 와 같은 이유).
    monkeypatch.setattr(config_module, "_read_yaml", lambda path: {})
    return ResultCollector(load_config(env="staging"), _FakePaths())


def _report(when: str, outcome: str = "passed", **meta: Any) -> SimpleNamespace:
    """pytest report 흉내. 수집기가 읽는 속성만 둡니다."""
    return SimpleNamespace(
        nodeid="tests/test_x.py::test_x", when=when, outcome=outcome, duration=0.1,
        passed=outcome == "passed", failed=outcome == "failed", skipped=outcome == "skipped",
        user_properties=[("meta", meta)] if meta else [],
    )


@pytest.mark.tc_id("UNIT807")
def test_collector_carries_data_and_changes(collector: ResultCollector) -> None:
    """conftest 가 실어 보낸 data·changes·Step 확인값이 result.json 까지 간다. 비밀값은 가린다."""
    collector.handle_report(_report("call"))
    collector.handle_report(_report(
        "teardown",
        data={"주문번호": "ORD-0001", "접속": "password=abc123"},
        changes={"할인": "상태 '임시저장'"},
        steps=[{"index": 1, "name": "조회", "expected": "", "status": "passed", "duration": 0.1,
                "error": None, "actual": ["token=xyz789 로 조회"]}],
    ))
    test = collector.to_dict()["tests"][0]
    assert test["data"]["주문번호"] == "ORD-0001"
    assert "abc123" not in test["data"]["접속"]
    assert test["changes"] == {"할인": "상태 '임시저장'"}
    assert "xyz789" not in test["steps"][0]["actual"][0]


@pytest.mark.tc_id("UNIT808")
def test_collector_defaults_are_empty(collector: ResultCollector) -> None:
    """남긴 것이 없어도 키는 있다 (소비자가 KeyError 를 만나지 않게)."""
    collector.handle_report(_report("call"))
    collector.handle_report(_report("teardown"))
    test = collector.to_dict()["tests"][0]
    assert test["data"] == {}
    assert test["changes"] == {}


@pytest.mark.tc_id("UNIT809")
def test_rerun_drops_previous_attempt_records(collector: ResultCollector) -> None:
    """재시도하면 이전 시도의 data·changes 를 버린다 (이전 시도가 남긴 변경이 최종 결과에 섞이지 않게)."""
    collector.handle_report(_report("teardown", data={"주문번호": "1"}, changes={"할인": "저장"}))
    collector.handle_report(_report("call", outcome="rerun"))
    test = collector.to_dict()["tests"][0]
    assert test["data"] == {}
    assert test["changes"] == {}
