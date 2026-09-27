"""테스트 Step 기록.

    from utils.steps import test_step

    with test_step("로그인 페이지 접속"):
        login_page.open()

    with test_step("로그인 버튼 클릭", expected="홈으로 이동한다"):
        login_page.login()

- Step 이름과 결과(PASS/FAIL), 소요시간이 Custom Report 에 그대로 표시됩니다.
- ``expected`` 는 **TC 명세서의 「기대결과 / 확인사항」 칸을 그대로 옮기는 자리**입니다.
  PASS 만 찍혀 있으면 "무엇이 맞았다는 것인지" 를 리포트만 보고는 알 수 없습니다.
  명세의 그 칸이 비어 있으면 여기도 비워두세요 (지어내면 TC 가 아니게 됩니다).
- 예외가 나면 그 Step 이 FAIL 로 기록되고 예외는 그대로 올라갑니다
  (테스트는 정상적으로 실패합니다).
- Step 을 안 써도 테스트는 동작합니다. 중요한 흐름에만 붙이면 충분합니다.

기대결과 옆에 **실제로 본 값**과 **쓴 데이터**를 남기면 리포트만 보고도 PASS 의 근거를 알 수 있습니다.

    with test_step("조회", expected="합계금액이 11,000 줄어든다"):
        ...
        record_actual(f"합계금액 {before} → {after}")    # 이 Step 의 '확인' 줄

    record_data("주문번호", bill_no)                      # TC 의 '사용 데이터'
    record_change("할인", f"{bill_no} 할인 상태 '임시저장'")    # TC 의 '남긴 변경'
    clear_change("할인")                                     # 되돌렸으면 지움

``record_change`` 는 테스트가 대상 사이트에 남긴 변경입니다. 되돌리는 테스트는 되돌린 뒤 지우고,
되돌리지 않는 테스트는 그대로 둡니다. 실패한 TC 에 남아 있으면 리포트가 "정리가 필요할 수 있는
변경" 으로 보여줍니다 (중간에 실패해 대상 사이트에 남은 데이터를 찾는 단서).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from utils import testmeta
from utils.logger import get_logger

logger = get_logger("step")

#: 지금 열려 있는 Step 기록. Step 밖에서 남긴 확인값이 끝난 Step 에 붙지 않게 합니다.
_open_step: ContextVar[dict | None] = ContextVar("_open_step", default=None)


@contextmanager
def test_step(name: str, expected: str = "") -> Iterator[None]:
    """Step 하나를 기록합니다.

    ``expected`` 는 명세서의 「기대결과 / 확인사항」 칸입니다. 리포트의 Step 아래에
    그대로 표시됩니다. 비워두면 그 줄은 리포트에 나오지 않습니다.
    """
    meta = testmeta.current()
    index = len(meta.steps) + 1 if meta else 1
    record: dict = {
        "index": index,
        "name": name,
        "expected": (expected or "").strip(),
        "status": "passed",
        "duration": 0.0,
        "error": None,
    }
    if meta is not None:
        meta.steps.append(record)

    logger.info("STEP %d. %s", index, name)
    token = _open_step.set(record)
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["duration"] = round(time.perf_counter() - started, 3)
        logger.error("STEP %d 실패: %s | %s", index, name, record["error"])
        _on_failure(meta)
        raise
    else:
        record["duration"] = round(time.perf_counter() - started, 3)
        logger.info("STEP %d 완료 (%.2fs)", index, record["duration"])
    finally:
        _open_step.reset(token)


# 이름이 test_ 로 시작해서 pytest 가 테스트 함수로 오해하지 않도록 표시합니다.
test_step.__test__ = False


def _on_failure(meta: testmeta.TestMeta | None) -> None:
    """실패 순간에 할 일(``TestMeta.on_step_failure``, 스크린샷)을 한 번만 부릅니다.

    테스트가 실패 뒤에 정리(되돌리기 등)를 하면 끝난 뒤의 화면은 실패 순간이 아니라서, 실패한 Step 에서
    바로 부릅니다 (2026-09-18 협의). 안쪽 Step 이 실패하면 바깥 Step 도 실패로 끝나는데, 그때는 이미
    불렀으므로 다시 부르지 않습니다. 여기서 난 오류가 원래 실패를 덮지 않게 경고만 남깁니다.
    """
    hook = meta.on_step_failure if meta is not None else None
    if hook is None:
        return
    meta.on_step_failure = None
    try:
        hook()
    except Exception as exc:
        logger.warning("실패 순간 Evidence 저장 실패: %s", exc)


def record_actual(text: str) -> None:
    """지금 Step 에서 실제로 확인한 값을 남깁니다. 리포트의 기대결과 아래 '확인' 줄로 나옵니다.

    Step 밖에서 부르면 로그에만 남깁니다. 끝난 Step 에 붙이면 그 Step 이 확인하지 않은 값이
    그 Step 의 확인값처럼 보이기 때문입니다.
    """
    record = _open_step.get()
    if record is None:
        logger.info("확인 (Step 밖): %s", text)
        return
    record.setdefault("actual", []).append(str(text))
    logger.info("STEP %d 확인: %s", record["index"], text)


def record_data(label: str, value: Any) -> None:
    """이 테스트가 쓴 데이터(대상 건 번호 등)를 남깁니다. 같은 이름은 마지막 값으로 바꿉니다."""
    meta = testmeta.current()
    if meta is None:
        return
    meta.data[label] = str(value)
    logger.info("사용 데이터: %s %s", label, value)


def record_change(key: str, text: str) -> None:
    """이 테스트가 대상 사이트에 남긴 변경을 적습니다. 같은 ``key`` 로 다시 부르면 내용을 바꿉니다."""
    meta = testmeta.current()
    if meta is None:
        return
    meta.changes[key] = text
    logger.info("남긴 변경 [%s]: %s", key, text)


def clear_change(key: str) -> None:
    """되돌린 변경을 지웁니다. 없는 ``key`` 면 아무것도 하지 않습니다."""
    meta = testmeta.current()
    if meta is None:
        return
    if meta.changes.pop(key, None) is not None:
        logger.info("남긴 변경 [%s]: 되돌림", key)
