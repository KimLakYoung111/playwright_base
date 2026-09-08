"""report.html 템플릿 렌더 회귀 테스트.

Browser 도 pytest 실행도 없이, ``render_html`` 에 최소 데이터를 넣어
HTML 문자열만 확인합니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from reporting import report_generator

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit


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


def test_marker_section_hidden_when_empty(tmp_path: Path) -> None:
    """markers[] 가 비면 섹션 자체를 그리지 않는다."""
    html = _render(tmp_path, markers=[])
    assert "Marker 별 결과" not in html


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


def test_flaky_section_hidden_when_no_retries(tmp_path: Path) -> None:
    """재시도가 없으면 섹션을 그리지 않는다."""
    html = _render(tmp_path)
    assert 'id="flaky"' not in html


def test_slow_tests_are_sorted_and_capped(tmp_path: Path) -> None:
    """느린 순으로 5건까지만 보여준다."""
    rows = [_test_row(test_id=f"TC{i:03d}", name=f"테스트 {i}", duration=float(i))
            for i in range(1, 8)]
    html = _render(tmp_path, tests=rows)

    assert "느린 테스트" in html
    # 섹션 안쪽만 본다. </details> 로 끊지 않으면 뒤따르는 All Tests 표까지
    # 딸려 들어와 "잘렸는지" 를 확인할 수 없다.
    slow_block = html.split("느린 테스트", 1)[1].split("</details>", 1)[0]
    # 가장 느린 TC007(7.0초)은 나오고, 가장 빠른 테스트 1·2 는 잘린다
    assert "테스트 7" in slow_block
    assert "테스트 2" not in slow_block


def test_slow_tests_hidden_when_few(tmp_path: Path) -> None:
    """5건 이하면 순위가 의미 없으므로 섹션을 숨긴다."""
    html = _render(tmp_path)
    assert "느린 테스트" not in html
