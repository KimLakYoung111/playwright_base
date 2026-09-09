"""Category 가 정해지는 규칙의 회귀 테스트.

Category 는 **고객사 리포트의 집계 단위**입니다. 여기가 틀리면 통계가 통째로
엉뚱한 이름으로 잡히는데, 실행은 초록불이라 아무도 눈치채지 못합니다.

특히 ``smoke`` / ``failure_demo`` / ``spec_pending`` 같은 **메타 marker 는 절대
Category 가 되면 안 됩니다.** 새 메타 marker 를 만들 때 ``NON_CATEGORY_MARKERS``
에 넣는 것을 잊는 것이 실제로 났던 실수입니다 (``spec_pending``, 2026-09-09).

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import pytest

from utils import testmeta
from utils.testmeta import NON_CATEGORY_MARKERS

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Config")]


class _FakeMark:
    def __init__(self, name: str, args: tuple = ()) -> None:
        self.name = name
        self.args = args


class _FakeItem:
    """``build_meta`` 가 실제로 건드리는 것만 흉내 냅니다.

    진짜 pytest item 을 만들려면 인프로세스로 pytest 를 한 번 더 돌려야 합니다.
    여기서 보려는 것은 marker 이름 → Category 규칙 하나뿐이라 그럴 필요가 없습니다.
    """

    def __init__(self, name: str, marks: list[_FakeMark]) -> None:
        self.name = name
        self._marks = marks
        self.function = None
        self.callspec = None

    def iter_markers(self, name: str | None = None):
        for mark in self._marks:
            if name is None or mark.name == name:
                yield mark

    def get_closest_marker(self, name: str):
        return next(self.iter_markers(name), None)


def _category(*marker_names: str) -> str:
    marks = [_FakeMark(n) for n in marker_names]
    return testmeta.build_meta(_FakeItem("test_something", marks)).category


@pytest.mark.tc_id("UNIT501")
def test_business_marker_becomes_category() -> None:
    """업무 영역 marker 는 Category 가 된다."""
    assert _category("smoke", "login") == "Login"


@pytest.mark.tc_id("UNIT502")
def test_explicit_category_marker_wins() -> None:
    """category() 를 직접 주면 그 값이 이긴다."""
    marks = [_FakeMark("payment"), _FakeMark("category", ("결제",))]
    assert testmeta.build_meta(_FakeItem("test_x", marks)).category == "결제"


@pytest.mark.tc_id("UNIT503")
def test_no_marker_falls_back_to_uncategorized() -> None:
    """업무 marker 가 하나도 없으면 Uncategorized."""
    assert _category("smoke") == testmeta.DEFAULT_CATEGORY


#: 메타 marker — 실행 유형·특성·상태를 나타낼 뿐 업무 영역이 아닙니다.
#: 하나라도 빠지면 그 marker 만 붙은 테스트가 엉뚱한 Category 로 집계됩니다.
META_MARKERS = [
    "smoke", "regression", "e2e", "failure_demo", "base_unit", "spec_pending",
    "slow", "flaky",
]


@pytest.mark.tc_id("UNIT504")
@pytest.mark.parametrize("marker", META_MARKERS)
def test_meta_marker_never_becomes_category(marker: str) -> None:
    """메타 marker 만 붙어 있으면 Category 가 되지 않는다.

    ``spec_pending`` 을 만들 때 이 목록에 넣는 것을 잊어, 그 marker 만 붙은
    테스트의 Category 가 "Spec_Pending" 이 될 뻔했습니다.
    """
    assert marker in NON_CATEGORY_MARKERS
    assert _category(marker) == testmeta.DEFAULT_CATEGORY
