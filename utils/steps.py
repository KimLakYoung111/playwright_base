"""테스트 Step 기록.

    from utils.steps import test_step

    with test_step("로그인 페이지 접속"):
        login_page.open()

    with test_step("로그인 버튼 클릭"):
        login_page.login()

- Step 이름과 결과(PASS/FAIL), 소요시간이 Custom Report 에 그대로 표시됩니다.
- 예외가 나면 그 Step 이 FAIL 로 기록되고 예외는 그대로 올라갑니다
  (테스트는 정상적으로 실패합니다).
- Step 을 안 써도 테스트는 동작합니다. 중요한 흐름에만 붙이면 충분합니다.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from utils import testmeta
from utils.logger import get_logger

logger = get_logger("step")


@contextmanager
def test_step(name: str) -> Iterator[None]:
    """Step 하나를 기록합니다."""
    meta = testmeta.current()
    index = len(meta.steps) + 1 if meta else 1
    record: dict = {
        "index": index,
        "name": name,
        "status": "passed",
        "duration": 0.0,
        "error": None,
    }
    if meta is not None:
        meta.steps.append(record)

    logger.info("STEP %d. %s", index, name)
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["duration"] = round(time.perf_counter() - started, 3)
        logger.error("STEP %d 실패: %s | %s", index, name, record["error"])
        raise
    else:
        record["duration"] = round(time.perf_counter() - started, 3)
        logger.info("STEP %d 완료 (%.2fs)", index, record["duration"])


# 이름이 test_ 로 시작해서 pytest 가 테스트 함수로 오해하지 않도록 표시합니다.
test_step.__test__ = False
