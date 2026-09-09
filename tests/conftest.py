"""``tests/`` 전용 pytest 설정 (Base 의 루트 ``conftest.py`` 와 별개입니다).

여기서 하는 일은 하나입니다. **``spec_pending`` 이 붙은 테스트를 어떤 실행에서도
빼는 것.** TC 명세서에 없는 테스트가 고객사 리포트에 섞여 나가지 않게 합니다.

왜 ``pytest.ini`` 의 ``addopts`` 로 하지 않는가
-----------------------------------------------
``addopts`` 에 ``-m "not spec_pending"`` 을 적어도, 사용자가 명령줄에 ``-m`` 을
주는 순간 **그쪽이 이깁니다** (같은 옵션이라 뒤에 온 값이 덮어씁니다).
``pytest -m regression`` 은 README 와 고객사 런북에 적혀 있는 명령이라
그 한 줄로 제외가 통째로 풀립니다. 그래서 수집 단계에서 직접 뺍니다.

되돌리려면
----------
명세가 확정되면 테스트에서 ``@pytest.mark.spec_pending`` 한 줄만 지우면 됩니다.
지금 당장 돌려보고 싶으면 ``pytest -m spec_pending`` 으로 지목하세요.
"""

from __future__ import annotations

from typing import Any

import pytest

#: 이 marker 가 붙은 테스트는 기본적으로 수집에서 제외합니다.
DESELECT_MARKER = "spec_pending"


def pytest_collection_modifyitems(config: pytest.Config, items: list[Any]) -> None:
    # -m 으로 직접 지목했으면 사용자의 뜻이므로 그대로 돌립니다.
    #  ("not spec_pending" 도 여기 걸리지만, 그 표현식 자체가 같은 결과를 냅니다)
    if DESELECT_MARKER in str(config.getoption("markexpr", "") or ""):
        return

    keep, drop = [], []
    for item in items:
        (drop if item.get_closest_marker(DESELECT_MARKER) else keep).append(item)

    if drop:
        # deselected 로 알려야 "N deselected" 에 잡혀 조용히 사라지지 않습니다.
        config.hook.pytest_deselected(items=drop)
        items[:] = keep
