"""report.html 템플릿 렌더 회귀 테스트.

Browser 도 pytest 실행도 없이, ``render_html`` 에 최소 데이터를 넣어
HTML 문자열만 확인합니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from reporting import report_generator

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Report")]


class _FakeCollector:
    """``render_html`` 은 ``to_dict()`` 만 부릅니다. 그 하나만 흉내 냅니다."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


def _test_row(**overrides: Any) -> dict[str, Any]:
    """``result.json`` 의 tests[] 한 줄. 필요한 것만 덮어씁니다."""
    row = {
        "test_id": "TC001",
        "name": "정상 로그인",
        "nodeid": "tests/login/test_login.py::test_login",
        "file": "tests/login/test_login.py",
        "function": "test_login",
        "category": "Login",
        "expected": "",
        "markers": ["smoke"],
        "status": "passed",
        "duration": 1.0,
        "started_at": "2026-09-09T10:00:00",
        "finished_at": "2026-09-09T10:00:01",
        "retries": 0,
        "error": None,
        "current_url": None,
        "browser": "chromium",
        "steps": [],
        "artifacts": {},
    }
    row.update(overrides)
    return row


def _data(**overrides: Any) -> dict[str, Any]:
    """``to_dict()`` 가 돌려주는 최소 구조."""
    data = {
        "schema_version": "1.0",
        "run": {
            "run_id": "20260909_100000",
            "project": "Example Automation",
            "environment": "staging",
            "browser": "chromium",
            "headless": True,
            "base_url": "https://example.com/",
            "started_at": "2026-09-09T10:00:00",
            "finished_at": "2026-09-09T10:00:10",
            "duration": 10.0,
            "retries_configured": 0,
            "python": "3.12.10",
            "playwright": "1.62.0",
            "platform": "Windows 10",
            "artifacts_dir": r"C:\artifacts\20260909_100000",
            "exit_status": 0,
        },
        "summary": {
            "total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0,
            "xfailed": 0, "xpassed": 0, "pass_rate": 100.0,
            "duration": 10.0, "retried": 0,
        },
        "categories": [{"name": "Login", "total": 1, "passed": 1, "failed": 0,
                        "skipped": 0, "pass_rate": 100.0}],
        "markers": [{"name": "smoke", "total": 1, "passed": 1, "failed": 0,
                     "skipped": 0, "pass_rate": 100.0}],
        "tests": [_test_row()],
    }
    data.update(overrides)
    return data


def _render(tmp_path: Path, **overrides: Any) -> str:
    target = report_generator.render_html(_FakeCollector(_data(**overrides)),
                                          tmp_path / "report.html")
    return target.read_text(encoding="utf-8")


@pytest.mark.tc_id("UNIT401")
def test_marker_section_is_rendered(tmp_path: Path) -> None:
    """markers[] 가 있으면 Marker 표가 그려진다."""
    html = _render(tmp_path, markers=[
        {"name": "smoke", "total": 3, "passed": 3, "failed": 0,
         "skipped": 0, "pass_rate": 100.0},
        {"name": "regression", "total": 2, "passed": 1, "failed": 1,
         "skipped": 0, "pass_rate": 50.0},
    ])
    assert "Marker 별 결과" in html
    assert "regression" in html


@pytest.mark.tc_id("UNIT402")
def test_marker_section_hidden_when_empty(tmp_path: Path) -> None:
    """markers[] 가 비면 섹션 자체를 그리지 않는다."""
    html = _render(tmp_path, markers=[])
    assert "Marker 별 결과" not in html


@pytest.mark.tc_id("UNIT403")
def test_flaky_section_lists_retried_tests(tmp_path: Path) -> None:
    """retries > 0 인 테스트만 Flaky 목록에 나온다."""
    html = _render(
        tmp_path,
        tests=[
            _test_row(test_id="TC001", retries=0),
            _test_row(test_id="TC002", name="흔들리는 결제", retries=2),
        ],
        summary={
            "total": 2, "passed": 2, "failed": 0, "skipped": 0, "error": 0,
            "xfailed": 0, "xpassed": 0, "pass_rate": 100.0,
            "duration": 10.0, "retried": 1,
        },
    )
    assert 'id="flaky"' in html
    assert "흔들리는 결제" in html
    # 요약의 "재시도 1건" 이 목록으로 가는 링크가 된다
    assert 'href="#flaky"' in html

    # flaky 섹션 슬라이싱: retries > 0 인 테스트만 포함, retries=0 은 제외
    flaky_start = html.find('id="flaky"')
    assert flaky_start != -1, "flaky 섹션을 찾을 수 없음"
    flaky_end = html.find("</section>", flaky_start)
    assert flaky_end != -1, "flaky 섹션 종료 태그를 찾을 수 없음"
    flaky_section = html[flaky_start:flaky_end + len("</section>")]

    # retried test (TC002) 는 flaky 섹션에 있어야 함
    assert "흔들리는 결제" in flaky_section, "TC002가 flaky 섹션에 없음"
    assert "TC002" in flaky_section, "TC002 ID가 flaky 섹션에 없음"

    # non-retried test (TC001) 는 flaky 섹션에 없어야 함
    assert "TC001" not in flaky_section, "TC001이 flaky 섹션에 포함됨 (retries=0 인데도)"


@pytest.mark.tc_id("UNIT404")
def test_flaky_section_hidden_when_no_retries(tmp_path: Path) -> None:
    """재시도가 없으면 섹션을 그리지 않는다."""
    html = _render(tmp_path)
    assert 'id="flaky"' not in html


@pytest.mark.tc_id("UNIT405")
def test_slow_tests_are_sorted_and_capped(tmp_path: Path) -> None:
    """느린 순으로 5건까지만 보여준다."""
    rows = [_test_row(test_id=f"TC{i:03d}", name=f"테스트 {i}", duration=float(i))
            for i in range(1, 8)]
    html = _render(tmp_path, tests=rows)

    assert "느린 테스트 Top 5" in html
    # 섹션 안쪽만 본다. </details> 로 끊지 않으면 뒤따르는 All Tests 표까지
    # 딸려 들어와 "잘렸는지" 를 확인할 수 없다.
    slow_block = html.split("느린 테스트 Top 5", 1)[1].split("</details>", 1)[0]
    # 가장 느린 TC007(7.0초)은 나오고, 가장 빠른 테스트 1·2 는 잘린다 (둘 다 확인)
    assert "테스트 7" in slow_block
    assert "테스트 1" not in slow_block
    assert "테스트 2" not in slow_block


@pytest.mark.tc_id("UNIT406")
def test_slow_tests_hidden_when_few(tmp_path: Path) -> None:
    """5건 이하면 순위가 의미 없으므로 섹션을 숨긴다."""
    html = _render(tmp_path)
    assert "느린 테스트 Top 5" not in html


@pytest.mark.tc_id("UNIT407")
def test_print_stylesheet_is_present(tmp_path: Path) -> None:
    """인쇄용 규칙이 들어 있고, 전체 테스트 표 섹션 자체를 숨긴다."""
    html = _render(tmp_path)
    assert "@media print" in html
    print_block = html.split("@media print", 1)[1].split("</style>", 1)[0]
    # 선택자가 어딘가에 "있기만" 한 게 아니라, display:none 규칙 중 하나에
    # 실제로 걸려 있는지 본다. re.search 로 첫 규칙만 보면, 가독성을 위해
    # 규칙을 나누거나 print 블록 앞쪽에 다른 display:none 규칙이 추가될 때
    # 이 테스트가 엉뚱하게 실패(또는 통과)한다. findall 로 전체 규칙을 모아
    # "어떤 규칙에든" 선택자가 있는지 확인한다.
    hide_rules = re.findall(r"([^{}]*)\{\s*display\s*:\s*none\b[^}]*\}", print_block)
    assert hide_rules, "display:none 규칙을 찾지 못했다"
    assert any("#slow-tests" in selectors for selectors in hide_rules)
    assert any("#all-tests" in selectors for selectors in hide_rules)
    # 실패 카드가 페이지 중간에서 잘리지 않게 한다
    assert "break-inside" in print_block


@pytest.mark.tc_id("UNIT421")
def test_failed_card_screenshots_are_not_lazy(tmp_path: Path) -> None:
    """인쇄 전용 실패 카드의 스크린샷은 lazy 로 두면 안 된다.

    ``#failed-tests`` 는 화면에서 ``display:none`` 이고 인쇄할 때만 나타난다.
    display:none 안의 lazy 이미지는 뷰포트에 들어올 일이 없어 브라우저가 영영
    받지 않을 수 있다. 그러면 종이에 남기려던 실패 스크린샷이 그 자리에서 비어
    버린다 — Evidence 를 남기려는 섹션이 정확히 그 Evidence 를 잃는다.
    """
    html = _render(tmp_path, tests=[_test_row(
        status="failed",
        error={"type": "AssertionError", "message": "boom",
               "traceback": "boom", "phase": "call"},
        artifacts={"screenshot": "screenshots/TC001.png"},
    )])
    card_start = html.find('id="failed-tests"')
    assert card_start != -1, "Failed Tests 섹션을 찾지 못했다"
    card = html[card_start:html.find("</section>", card_start)]
    assert "<img" in card, "실패 카드에 스크린샷이 없다 (테스트 전제가 깨졌다)"
    assert 'loading="lazy"' not in card


def _run_with_meta(**overrides: Any) -> dict[str, Any]:
    """schema 1.1 메타가 채워진 run 블록."""
    run = dict(_data()["run"])
    run.update({
        "app_version": "v2.14.3 (build 8821)",
        "git": {"branch": "main", "commit": "5d1ed8b", "dirty": False},
        "triggered_by": "klyhja",
        "command": "pytest -m smoke -n 4 --env=staging",
        "workers": 4,
    })
    run.update(overrides)
    return run


@pytest.mark.tc_id("UNIT408")
def test_header_shows_run_meta(tmp_path: Path) -> None:
    """앱 버전·커밋·실행자·명령줄·병렬 수가 헤더에 나온다."""
    html = _render(tmp_path, run=_run_with_meta())

    assert "v2.14.3 (build 8821)" in html
    assert "5d1ed8b" in html
    assert "klyhja" in html
    assert "pytest -m smoke -n 4 --env=staging" in html
    assert "4개 동시 실행" in html


@pytest.mark.tc_id("UNIT409")
def test_header_hides_missing_meta(tmp_path: Path) -> None:
    """값이 null 이면 그 줄 자체를 그리지 않는다 (빈 칸을 남기지 않음)."""
    html = _render(tmp_path, run=_run_with_meta(
        app_version=None, git=None, triggered_by=None))

    assert "앱 버전" not in html
    assert "실행자" not in html
    # git 이 None 이면 {% if run.git %} 가드가 걸러야 한다. 가드를 지워도
    # Jinja 가 None.branch 를 빈 문자열로 렌더해 라벨만 남을 수 있다.
    assert '<span class="k">자동화 코드</span>' not in html


@pytest.mark.tc_id("UNIT410")
def test_header_marks_dirty_worktree(tmp_path: Path) -> None:
    """커밋 안 된 변경이 있으면 표시한다. 재현이 안 될 수 있다는 신호다."""
    html = _render(tmp_path, run=_run_with_meta(
        git={"branch": "main", "commit": "5d1ed8b", "dirty": True}))
    assert "변경 있음" in html


@pytest.mark.tc_id("UNIT411")
def test_header_says_nothing_for_clean_worktree(tmp_path: Path) -> None:
    """깨끗하면 아무 표시도 하지 않는다."""
    html = _render(tmp_path, run=_run_with_meta(
        git={"branch": "main", "commit": "5d1ed8b", "dirty": False}))
    assert "변경 있음" not in html
    assert "변경 여부 확인 못 함" not in html


@pytest.mark.tc_id("UNIT412")
def test_header_distinguishes_unknown_dirty_state(tmp_path: Path) -> None:
    """dirty 가 None 이면 "모른다" 고 적는다.

    None 은 falsy 라 ``{% if run.git.dirty %}`` 하나로는 깨끗한 것과 구별되지
    않는다. 그러면 리포트가 "이 커밋과 정확히 일치" 를 거짓으로 단정한다.
    """
    html = _render(tmp_path, run=_run_with_meta(
        git={"branch": "main", "commit": "5d1ed8b", "dirty": None}))
    assert "변경 여부 확인 못 함" in html
    assert "변경 있음" not in html


# ---------------------------------------------------------------------------
# open_in_browser (실행 후 리포트 자동 열기)
#
#   실제로 창을 띄우면 테스트가 브라우저를 남기므로 webbrowser.open 을 갈아끼웁니다.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Step 별 API 응답 시간 (schema 1.3)
#
#   CSV 대신 리포트에서 바로 보도록 옮긴 값입니다. 없는 Step 에 빈 표가 남지 않는지,
#   응답이 다른 Step 에서 끝난 경우를 구분해 보여주는지를 못 박습니다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT422")
def test_step_apis_are_rendered(tmp_path: Path) -> None:
    """Step 에 apis 가 있으면 건수·최대 시간 요약과 API 표가 나온다.

    최대 시간은 그 Step 안에서 끝난 호출로만 잽니다. 뒤 Step 에서 끝난 호출(로그인 때 시작한 약 12초짜리
    대시보드 조회)까지 넣으면 4초짜리 Step 에 '최대 11.70s' 가 붙어 그 Step 이 느린 것처럼 읽힙니다
    (2026-09-18 리포트 검토). 그런 호출은 건수로 따로 알립니다.
    """
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "조회", "expected": "", "status": "passed", "duration": 2.0, "error": None,
         "apis": [
             {"tab": 2, "method": "POST", "path": "/api/v1/orders/search", "status": 200, "ttfb_ms": 80, "total_ms": 87},
             {"tab": None, "method": "POST", "path": "/api/v1/dashboard/summary", "status": 200,
              "ttfb_ms": 11690, "total_ms": 11699, "end_step": 3},
         ]},
    ])])
    assert '<li class="sapi">' in html
    assert "API 2건 · 최대 0.09s · 뒤 단계에서 끝난 호출 1건" in html
    assert "/api/v1/orders/search" in html
    assert "(3단계에서 완료)" in html
    assert "<th>탭</th>" in html
    assert "<td>2</td><td>POST</td><td class=\"path\">/api/v1/orders/search" in html
    assert "<td>-</td><td>POST</td>" in html
    assert 'class="slow"' in html


@pytest.mark.tc_id("UNIT423")
def test_step_without_apis_leaves_no_table(tmp_path: Path) -> None:
    """apis 가 없으면(schema 1.2 이전 결과 포함) 줄 자체를 만들지 않는다."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "화면 접속", "expected": "", "status": "passed", "duration": 0.5, "error": None},
    ])])
    assert '<li class="sapi">' not in html
    assert "TC001" in html


@pytest.mark.tc_id("UNIT424")
def test_step_apis_all_carried_have_no_max(tmp_path: Path) -> None:
    """Step 안에서 끝난 호출이 하나도 없으면 최대 시간을 쓰지 않는다 (0s 로 적으면 거짓)."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "로그인", "expected": "", "status": "passed", "duration": 3.0, "error": None,
         "apis": [{"tab": 1, "method": "POST", "path": "/api/v1/dashboard/summary", "status": 200,
                   "ttfb_ms": 11690, "total_ms": 11699, "end_step": 3}]},
    ])])
    assert "API 1건 · 뒤 단계에서 끝난 호출 1건" in html
    assert "최대" not in html.split('<li class="sapi">', 1)[1].split("</summary>", 1)[0]


@pytest.mark.tc_id("UNIT425")
def test_error_status_is_marked(tmp_path: Path) -> None:
    """상태 400 이상인 응답은 표에서 눈에 띄게 표시한다. 200 은 그대로."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "로그인", "expected": "", "status": "passed", "duration": 1.0, "error": None,
         "apis": [
             {"tab": 1, "method": "GET", "path": "/rest/v2/session/user",
              "status": 403, "ttfb_ms": 10, "total_ms": 12},
             {"tab": 1, "method": "POST", "path": "/api/v1/orders/search", "status": 200, "ttfb_ms": 80, "total_ms": 87},
         ]},
    ])])
    assert '<td class="bad">403</td>' in html
    assert "<td>200</td>" in html


@pytest.mark.tc_id("UNIT426")
def test_failed_step_opens_its_api_table(tmp_path: Path) -> None:
    """실패한 Step 의 API 표는 펼쳐 둔다. 서버가 받았는지(200)가 실패 원인을 가르는 첫 단서라서."""
    api = {"tab": 3, "method": "GET", "path": "/api/v1/orders/1/items", "status": 200,
           "ttfb_ms": 3342, "total_ms": 3345}
    html = _render(tmp_path, tests=[_test_row(
        status="failed",
        error={"type": "AssertionError", "message": "boom", "traceback": "boom", "phase": "call"},
        steps=[
            {"index": 1, "name": "조회", "expected": "", "status": "passed", "duration": 1.0, "error": None,
             "apis": [dict(api)]},
            {"index": 2, "name": "다시 조회", "expected": "", "status": "failed", "duration": 14.0,
             "error": "AssertionError: boom", "apis": [dict(api)]},
        ])])
    assert html.count("<details open>") == 2       # 화면용 상세 1 + 인쇄용 실패 카드 1 (2단계만)
    assert html.count('<li class="sapi"><details>') == 2   # 1단계는 두 곳 모두 접힘


# ---------------------------------------------------------------------------
# 확인값 · 사용 데이터 · 남긴 변경 (schema 1.4)
#
#   PASS 옆에 기대결과만 있으면 실제로 무엇을 봤는지 알 수 없어서 넣은 값입니다.
#   없을 때 빈 줄이 남지 않는지도 함께 못 박습니다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT427")
def test_step_actual_is_rendered(tmp_path: Path) -> None:
    """Step 확인값이 기대결과 아래 줄로 나온다. 없으면 줄을 만들지 않는다."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "조회", "expected": "11,000 줄어든다", "status": "passed", "duration": 1.0,
         "error": None, "actual": ["합계금액 50,000 → 39,000"]},
        {"index": 2, "name": "닫기", "expected": "", "status": "passed", "duration": 0.1, "error": None},
    ])])
    assert html.count('<li class="sact">') == 1
    assert "합계금액 50,000 → 39,000" in html


@pytest.mark.tc_id("UNIT428")
def test_test_data_is_rendered(tmp_path: Path) -> None:
    """사용 데이터가 TC 상세에 나온다. 없으면 줄이 없다."""
    html = _render(tmp_path, tests=[
        _test_row(data={"주문번호": "ORD-0001", "고객": "ACME"}),
        _test_row(test_id="TC002", data={}),
    ])
    assert "사용 데이터" in html
    assert "주문번호 ORD-0001 · 고객 ACME" in html
    assert html.count('<span class="k">사용 데이터</span>') == 2   # 화면 상세 + 인쇄 표 (TC001 만)


@pytest.mark.tc_id("UNIT429")
def test_changes_are_labelled_by_result(tmp_path: Path) -> None:
    """실패한 TC 의 남은 변경은 정리가 필요할 수 있다고 적고, 통과한 TC 는 남긴 변경으로 적는다."""
    failed = _render(tmp_path, tests=[_test_row(
        status="failed", changes={"할인": "주문번호 1 할인 10,000 상태 '저장'"},
        error={"type": "AssertionError", "message": "boom", "traceback": "boom", "phase": "call"})])
    # CSS 주석에도 같은 낱말이 있어서 라벨 태그로 봅니다.
    cleanup, left = '<span class="k">정리가 필요할 수 있는 변경</span>', '<span class="k">남긴 변경</span>'
    assert cleanup in failed
    assert "할인 10,000 상태 &#39;저장&#39;" in failed

    passed = _render(tmp_path, tests=[_test_row(changes={"할인": "할인 10,000 승인완료 (되돌리지 않음)"})])
    assert left in passed
    assert cleanup not in passed

    none = _render(tmp_path, tests=[_test_row(changes={})])
    assert left not in none and cleanup not in none


# ---------------------------------------------------------------------------
# 인쇄본 TC 목록
#
#   인쇄본은 전체 테스트 표를 숨깁니다. 실패 카드만 인쇄용이라 전부 통과한 실행을 PDF 로 뽑으면
#   건수만 남고 TC 이름이 하나도 없었습니다 (2026-09-18 리포트 검토).
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT430")
def test_print_lists_every_test(tmp_path: Path) -> None:
    """인쇄 전용 TC 목록이 모든 TC 를 담고, 화면에서는 숨고 인쇄에서만 보인다."""
    html = _render(tmp_path, tests=[
        _test_row(test_id="TC001", name="정상 로그인", expected="홈으로 이동한다"),
        _test_row(test_id="TC002", name="잘못된 비밀번호", status="failed",
                  error={"type": "AssertionError", "message": "boom", "traceback": "boom", "phase": "call"}),
    ])
    start = html.find('id="print-tests"')
    assert start != -1, "인쇄용 TC 목록이 없다"
    section = html[start:html.find("</section>", start)]
    assert "정상 로그인" in section and "잘못된 비밀번호" in section
    assert "홈으로 이동한다" in section

    # CSS 주석에도 '@media print' 라는 글자가 있어서 실제 규칙 블록('@media print{')으로 자릅니다.
    screen_css = html.split("@media print{", 1)[0]
    assert re.search(r"#print-tests\s*\{\s*display\s*:\s*none", screen_css)
    print_block = html.split("@media print{", 1)[1].split("</style>", 1)[0]
    shown = re.findall(r"([^{}]*)\{\s*display\s*:\s*block\b[^}]*\}", print_block)
    assert any("#print-tests" in selectors for selectors in shown)


# ---------------------------------------------------------------------------
# 실패 요약
#
#   Reason 칸에 Playwright 원문(Call log·locator 내부 표현)이 그대로 나와 고객사가 읽기 어려웠습니다.
#   몇 단계에서 무엇이 어긋났는지 한 줄로 바꾸고, 원문은 그 아래 traceback 에 그대로 둡니다.
# ---------------------------------------------------------------------------

PW_TEXT_MISMATCH = (
    "AssertionError: Locator expected to have text '상신'\n"
    "Actual value: 저장 \n"
    "Call log:\n"
    '  - Expect "to_have_text" with timeout 10000ms\n'
    '  - waiting for get_by_role("row").filter(has=get_by_role("gridcell")).first.get_by_role("gridcell").nth(13)\n'
    '    23 × locator resolved to <td role="gridcell">…</td>\n'
    '       - unexpected value "저장"\n'
    "\nAria snapshot:\n- gridcell \"저장\""
)


def _failed(message: str, failed_index: int | None = 17) -> dict[str, Any]:
    steps = [{"index": i, "name": f"단계 {i}", "expected": "", "status": "passed", "duration": 0.1, "error": None}
             for i in range(1, (failed_index or 1))]
    if failed_index:
        steps.append({"index": failed_index, "name": "조회", "expected": "", "status": "failed",
                      "duration": 14.0, "error": message})
    return _test_row(status="failed", steps=steps,
                     error={"type": "AssertionError", "message": message, "traceback": message, "phase": "call"})


@pytest.mark.tc_id("UNIT431")
def test_summary_of_value_mismatch() -> None:
    """글자 비교 실패: 몇 단계에서, 기대와 실제가 무엇이었는지, 얼마나 기다렸는지."""
    fail = report_generator.summarize_failure(_failed(PW_TEXT_MISMATCH))
    assert fail == {"kind": "값 불일치", "step": 17,
                    "text": "기대 '상신' · 실제 '저장' (10초 대기)"}


@pytest.mark.tc_id("UNIT432")
def test_summary_of_missing_element() -> None:
    """요소가 끝내 안 나타나면 무엇을 찾았는지 locator 를 보여준다 (그게 유일한 단서)."""
    message = ("AssertionError: Locator expected to be visible\nActual value: None\n"
               "Error: element(s) not found \nCall log:\n"
               '  - Expect "to_be_visible" with timeout 3000ms\n'
               '  - waiting for get_by_role("heading", name="대시보드")\n')
    fail = report_generator.summarize_failure(_failed(message, 3))
    assert fail == {"kind": "요소 없음", "step": 3,
                    "text": '요소를 찾지 못함 · get_by_role("heading", name="대시보드") (3초 대기)'}


@pytest.mark.tc_id("UNIT433")
def test_summary_keeps_custom_expect_message() -> None:
    """expect(…, "메시지") 로 쓴 문구는 사람이 적은 설명이라 그대로 쓴다."""
    message = ("AssertionError: 변경취소 결과 알림: 서버 처리(로딩)가 60초 안에 끝나지 않았습니다 "
               "(config timeouts.loading)\nActual value: None\nError: element(s) not found \nCall log:\n"
               '  - Expect "to_be_visible" with timeout 60000ms\n')
    fail = report_generator.summarize_failure(_failed(message, 11))
    assert fail == {"kind": "요소 없음", "step": 11,
                    "text": "변경취소 결과 알림: 서버 처리(로딩)가 60초 안에 끝나지 않았습니다 "
                            "(config timeouts.loading) · 요소를 찾지 못함 (60초 대기)"}


@pytest.mark.tc_id("UNIT434")
def test_summary_of_action_timeout() -> None:
    """클릭 같은 동작이 시간 안에 안 끝나면 무엇을 누르려 했는지 보여준다."""
    message = ("playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n"
               "Call log:\n"
               '  - waiting for get_by_text("B&T부문", exact=True).filter(visible=True)\n')
    fail = report_generator.summarize_failure(_failed(message, 3))
    assert fail == {"kind": "대기 시간 초과", "step": 3,
                    "text": '클릭 30초 안에 끝나지 않음 · get_by_text("B&T부문", exact=True).filter(visible=True)'}


@pytest.mark.tc_id("UNIT435")
def test_summary_of_plain_assert() -> None:
    """assert 문의 설명 문구를 그대로 쓴다 (pytest 가 덧붙인 assert 식 줄은 뺌)."""
    message = ("AssertionError: 확인창 문구가 다릅니다: [] (알림창: 이미 처리된 주문입니다.)\n"
               "assert [] == ['주문을 제출하시겠습니까?']")
    fail = report_generator.summarize_failure(_failed(message, 13))
    assert fail == {"kind": "조건 불충족", "step": 13,
                    "text": "확인창 문구가 다릅니다: [] (알림창: 이미 처리된 주문입니다.)"}


@pytest.mark.tc_id("UNIT436")
def test_summary_of_other_error_without_step() -> None:
    """그 밖의 오류는 첫 줄. Step 밖(준비 단계)에서 났으면 단계 번호가 없다."""
    fail = report_generator.summarize_failure(_failed("KeyError: '고객사'", None))
    assert fail == {"kind": "기타 오류", "step": None, "text": "KeyError: '고객사'"}


@pytest.mark.tc_id("UNIT437")
def test_summary_is_shown_instead_of_raw_reason(tmp_path: Path) -> None:
    """화면 상세와 인쇄 카드의 실패 내용에 요약이 나오고, 원문은 traceback 칸에만 남는다."""
    html = _render(tmp_path, tests=[_failed(PW_TEXT_MISMATCH)])
    assert html.count("17단계 · 기대 &#39;상신&#39; · 실제 &#39;저장&#39; (10초 대기)") == 2
    assert html.count('<span class="fkind">값 불일치</span>') == 2
    # 실패한 Step 아래 줄에도 원문 대신 요약이 나온다
    assert "↳ 기대 &#39;상신&#39; · 실제 &#39;저장&#39; (10초 대기)" in html
    assert "Call log" in html          # 원문은 traceback 칸에 그대로


@pytest.mark.tc_id("UNIT438")
def test_passed_test_has_no_summary() -> None:
    assert report_generator.summarize_failure(_test_row()) is None


@pytest.mark.tc_id("UNIT442")
def test_summary_points_at_the_innermost_failed_step() -> None:
    """Step 안에 Step 을 넣으면 바깥도 실패로 끝납니다. 실제로 깨진 건 안쪽(나중에 시작한) Step 입니다.

    처음 실패한 Step 을 고르면 바깥 Step 번호가 나오고 요약도 엉뚱한 줄에 붙습니다.
    """
    steps = [
        {"index": 1, "name": "주문", "expected": "", "status": "failed", "duration": 3.0, "error": "E"},
        {"index": 2, "name": "조회", "expected": "", "status": "failed", "duration": 1.0, "error": "E"},
    ]
    test = _test_row(status="failed", steps=steps,
                     error={"type": "AssertionError", "message": "AssertionError: 없음",
                            "traceback": "", "phase": "call"})
    assert report_generator.summarize_failure(test)["step"] == 2


# ---------------------------------------------------------------------------
# 응답 없는 API (schema 1.5)
#
#   응답이 온 호출만 싣던 때는, 대시보드 조회가 끝내 응답하지 않아 로딩 가림막이 메뉴 클릭을 막은 실패
#   (2단계)에서 결정적 단서가 리포트에 없었습니다. 응답이 없던 호출은 status 가 null 이고,
#   요청이 실패했으면 failure 에 사유가 있습니다.
# ---------------------------------------------------------------------------

PENDING = {"tab": 1, "method": "POST", "path": "/api/v1/dashboard/summary", "status": None,
           "ttfb_ms": None, "total_ms": 215300}
FAILED_CALL = {"tab": 1, "method": "GET", "path": "/rest/notifications", "status": None,
               "ttfb_ms": None, "total_ms": 31, "failure": "net::ERR_CONNECTION_RESET"}
ANSWERED = {"tab": 1, "method": "GET", "path": "/rest/v2/menu", "status": 200,
            "ttfb_ms": 245, "total_ms": 273}


@pytest.mark.tc_id("UNIT439")
def test_unanswered_calls_are_listed_in_the_step(tmp_path: Path) -> None:
    """응답 없는 호출도 표에 나오고 요약에 건수가 붙는다. 최대 시간은 응답이 온 호출로만 잰다."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "로그인", "expected": "", "status": "passed", "duration": 3.0, "error": None,
         "apis": [dict(ANSWERED), dict(PENDING), dict(FAILED_CALL)]},
    ])])
    assert "API 3건 · 최대 0.27s · 응답 없음 2건" in html
    assert '<td class="bad">응답 없음</td>' in html
    assert "215300ms (끝까지 응답 없음)" in html
    assert '<td class="bad">실패</td>' in html
    assert "31ms (net::ERR_CONNECTION_RESET)" in html


@pytest.mark.tc_id("UNIT440")
def test_failed_test_shows_unanswered_calls_from_any_step(tmp_path: Path) -> None:
    """실패한 TC 는 실패 내용 아래에 응답 없는 호출을 모아 보여준다. 요청한 Step 이 실패한 Step 보다 앞이어도."""
    message = ("playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n"
               "Call log:\n  - waiting for get_by_text(\"주문\", exact=True)\n")
    html = _render(tmp_path, tests=[_test_row(
        status="failed",
        error={"type": "TimeoutError", "message": message, "traceback": message, "phase": "call"},
        steps=[
            {"index": 1, "name": "로그인", "expected": "", "status": "passed", "duration": 3.6, "error": None,
             "apis": [dict(ANSWERED), dict(PENDING)]},
            {"index": 2, "name": "메뉴 클릭", "expected": "", "status": "failed", "duration": 215.6,
             "error": message},
        ])])
    line = '<span class="k">응답 없는 API</span><span class="warn">/api/v1/dashboard/summary (1단계 요청, 215초 기다려도 응답 없음)</span>'
    assert html.count(line) == 2          # 화면 상세 + 인쇄용 실패 카드


@pytest.mark.tc_id("UNIT441")
def test_passed_test_has_no_unanswered_block(tmp_path: Path) -> None:
    """통과한 TC 는 Step 요약의 건수로만 알린다 (실패 단서 칸은 실패한 TC 에만)."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "로그인", "expected": "", "status": "passed", "duration": 3.0, "error": None,
         "apis": [dict(PENDING)]},
    ])])
    assert "응답 없음 1건" in html
    assert '<span class="k">응답 없는 API</span>' not in html


# ---------------------------------------------------------------------------
# 기대결과 (schema 1.2)
#
#   PASS 만 찍혀 있으면 무엇이 맞았다는 것인지 알 수 없어서 넣은 값입니다.
#   비어 있을 때 "기대결과" 라는 빈 줄이 남으면 리포트가 지저분해지므로
#   "있으면 나오고 없으면 아예 안 나온다" 를 양쪽 다 못 박습니다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT416")
def test_test_level_expected_is_rendered(tmp_path: Path) -> None:
    """TC 대표 기대결과가 리포트에 그대로 나온다."""
    html = _render(tmp_path, tests=[_test_row(expected='"다음" 버튼이 비활성 상태다')])
    assert "기대결과" in html
    assert "&#34;다음&#34; 버튼이 비활성 상태다" in html or '"다음" 버튼이 비활성 상태다' in html


@pytest.mark.tc_id("UNIT417")
def test_step_expected_is_rendered(tmp_path: Path) -> None:
    """Step 마다의 기대결과가 그 Step 아래 줄로 나온다."""
    html = _render(tmp_path, tests=[_test_row(steps=[
        {"index": 1, "name": "다음 버튼 상태 확인", "expected": "다음 단계로 넘어간다",
         "status": "passed", "duration": 0.5, "error": None},
    ])])
    assert '<li class="sexp">' in html
    assert "다음 단계로 넘어간다" in html


@pytest.mark.tc_id("UNIT418")
def test_empty_expected_leaves_no_row(tmp_path: Path) -> None:
    """비어 있으면 줄 자체를 만들지 않는다.

    명세에 기대결과가 없는 단계까지 빈 줄로 채우면 리포트를 읽기 어려워진다.
    """
    html = _render(tmp_path, tests=[_test_row(expected="", steps=[
        {"index": 1, "name": "화면 접속", "expected": "",
         "status": "passed", "duration": 0.5, "error": None},
    ])])
    assert '<li class="sexp">' not in html
    assert "기대결과</span>" not in html


@pytest.mark.tc_id("UNIT419")
def test_missing_expected_key_does_not_break_render(tmp_path: Path) -> None:
    """schema 1.1 이전에 만든 result.json 에는 이 키가 없다. 그래도 렌더돼야 한다."""
    row = _test_row()
    row.pop("expected")
    html = _render(tmp_path, tests=[row, ])
    assert "TC001" in html
    assert '<li class="sexp">' not in html


@pytest.mark.tc_id("UNIT413")
def test_open_in_browser_opens_the_report(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """파일이 있으면 file:// URI 로 연다."""
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")
    called: list[str] = []
    monkeypatch.setattr(report_generator.webbrowser, "open",
                        lambda url: called.append(url) or True)

    assert report_generator.open_in_browser(report) is True
    assert called == [report.as_uri()]


@pytest.mark.tc_id("UNIT414")
def test_open_in_browser_returns_false_when_report_missing(tmp_path: Path) -> None:
    """리포트 생성이 실패했으면 열 것이 없다. 터지지 않고 False 를 준다."""
    assert report_generator.open_in_browser(tmp_path / "없는파일.html") is False


@pytest.mark.tc_id("UNIT415")
def test_open_in_browser_swallows_errors(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """띄울 브라우저가 없는 환경(서버·Docker)에서 pytest 가 죽으면 안 된다.

    부가 기능이 실행 결과를 바꾸는 것이 가장 나쁜 실패다.
    """
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")

    def _boom(url: str) -> bool:
        raise OSError("no browser")

    monkeypatch.setattr(report_generator.webbrowser, "open", _boom)
    assert report_generator.open_in_browser(report) is False


@pytest.mark.tc_id("UNIT420")
def test_open_in_browser_does_not_hang(tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """``webbrowser.open`` 이 안 돌아와도 pytest 가 멈추면 안 된다.

    ``BROWSER`` 환경변수가 있으면 Python 은 ``GenericBrowser`` 를 골라
    ``Popen(...).wait()`` 을 한다. 사용자가 브라우저를 닫을 때까지 블로킹이다.
    **멈추는 것은 예외가 아니라서 try/except 로는 못 막는다.**
    """
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")

    release = threading.Event()

    def _blocks_forever(url: str) -> bool:
        release.wait(30)          # 테스트가 끝나도 프로세스가 남지 않게 상한을 둔다
        return True

    monkeypatch.setattr(report_generator.webbrowser, "open", _blocks_forever)
    monkeypatch.setattr(report_generator, "OPEN_TIMEOUT_SEC", 0.05)

    started = time.perf_counter()
    try:
        # 브라우저는 실제로 떴다고 보므로 True. 중요한 것은 "돌아온다" 는 것이다.
        assert report_generator.open_in_browser(report) is True
        assert time.perf_counter() - started < 5, "기다리지 않고 빠져나와야 한다"
    finally:
        release.set()
