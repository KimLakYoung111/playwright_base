"""실패한 탭 고르기 (루트 conftest 의 ``_failed_page``) 단위 테스트.

실패 Screenshot 과 리포트 '마지막 URL' 은 실패한 탭 한 장입니다 (2026-09-18 협의). 고른 탭이 닫혀 있으면
찍을 수도 주소를 읽을 수도 없어 증적이 통째로 빠지므로, 닫힌 탭은 고르지 않는 것을 못 박습니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Artifacts")]


class _Tab:
    """``is_closed()`` 만 있는 가짜 탭."""

    def __init__(self, closed: bool = False) -> None:
        self._closed = closed

    def is_closed(self) -> bool:
        return self._closed


@pytest.fixture(scope="module")
def root_conftest(pytestconfig: pytest.Config) -> ModuleType:
    """이미 올라와 있는 루트 conftest 모듈 (다시 import 하지 않습니다)."""
    path = pytestconfig.rootpath / "conftest.py"
    return next(plugin for plugin in pytestconfig.pluginmanager.get_plugins()
                if getattr(plugin, "__file__", None) and Path(plugin.__file__).samefile(path))


@pytest.mark.tc_id("UNIT812")
def test_last_requesting_tab_is_the_failed_tab(root_conftest: ModuleType) -> None:
    """마지막으로 요청을 보낸 탭이 열려 있으면 그 탭을 고른다."""
    first, detail, other = _Tab(), _Tab(), _Tab()
    assert root_conftest._failed_page([first, detail, other], [detail]) is detail


@pytest.mark.tc_id("UNIT813")
def test_closed_first_tab_is_not_chosen(root_conftest: ModuleType) -> None:
    """마지막으로 요청을 보낸 첫 탭이 닫혔으면 열린 탭 중 마지막을 고른다.

    첫 탭(``page``)은 닫혀도 후보 목록에 남습니다. 그대로 고르면 Screenshot 도 '마지막 URL' 도 비게 됩니다.
    """
    first, second = _Tab(closed=True), _Tab()
    assert root_conftest._failed_page([first, second], [first]) is second
