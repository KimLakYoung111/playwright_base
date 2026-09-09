"""``python -m reporting.ci_summary`` 콘솔 출력 단위 테스트.

Windows 콘솔은 기본이 cp949 라 ``✅`` 를 인코딩하지 못합니다. 그대로 두면
``print`` 가 ``UnicodeEncodeError`` 로 죽는데, 이 명령은 **HANDOFF 와 README 가
검증 절차로 안내하는 것**이라 안내대로 따라한 사람이 트레이스백을 봅니다.

Markdown 본문(``to_markdown``)은 CI·Slack·Email 로 나가는 규약이므로
**바뀌면 안 됩니다.** 바꾸는 것은 콘솔로 내보내는 마지막 단계뿐입니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import pytest

from reporting.ci_summary import ICON_FAIL, ICON_PASS, encode_safe, to_markdown

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Report")]


def make_result(failed: int = 0) -> dict:
    """``to_markdown`` 이 요구하는 최소 형태의 result.json."""
    total = 3
    return {
        "run": {"project": "예제 자동화", "environment": "staging", "browser": "chromium"},
        "summary": {
            "total": total, "passed": total - failed, "failed": failed,
            "skipped": 0, "pass_rate": 100.0, "duration": 1.0,
        },
        "tests": [],
    }


# ---------------------------------------------------------------------------
# 규약: Markdown 본문은 손대지 않는다
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT601")
@pytest.mark.parametrize("failed, icon", [(0, ICON_PASS), (1, ICON_FAIL)])
def test_markdown_keeps_the_icon(failed: int, icon: str) -> None:
    """``to_markdown`` 은 언제나 아이콘을 그대로 넣는다. CI 로 나가는 규약이다."""
    assert to_markdown(make_result(failed)).startswith(f"## {icon} ")


@pytest.mark.tc_id("UNIT602")
def test_utf8_stream_is_left_untouched() -> None:
    """UTF-8 로 쓸 수 있으면 한 글자도 바뀌지 않는다.

    CI(리눅스 러너)와 리다이렉트가 여기 해당한다. 아이콘이 살아 있어야 한다.
    """
    markdown = to_markdown(make_result())
    assert encode_safe(markdown, "utf-8") == markdown


# ---------------------------------------------------------------------------
# cp949 콘솔 — 죽지 않고, 뜻은 남는다
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT603")
@pytest.mark.parametrize("failed, icon, plain",
                         [(0, ICON_PASS, "[PASS]"), (1, ICON_FAIL, "[FAIL]")])
def test_cp949_console_gets_readable_ascii_icon(failed: int, icon: str, plain: str) -> None:
    """cp949 에서는 아이콘이 ``[PASS]`` / ``[FAIL]`` 이 된다.

    ``?`` 로 뭉개면 통과인지 실패인지가 사라진다. 그게 이 줄의 유일한 정보다.
    """
    safe = encode_safe(to_markdown(make_result(failed)), "cp949")
    assert icon not in safe
    assert plain in safe
    safe.encode("cp949")          # 실제로 인코딩 가능해야 한다 (죽지 않는 조건)


@pytest.mark.tc_id("UNIT604")
def test_korean_survives_on_cp949() -> None:
    """한글은 cp949 로 인코딩되므로 ``?`` 로 뭉개지면 안 된다.

    스트림 전체를 ``errors="replace"`` 로 밀어버리면 한글까지 잃는다.
    """
    safe = encode_safe(to_markdown(make_result()), "cp949")
    assert "예제 자동화" in safe


@pytest.mark.tc_id("UNIT605")
@pytest.mark.parametrize("encoding", ["cp949", "ascii", "cp1252", None, "없는인코딩"])
def test_never_raises_for_any_stream_encoding(encoding: str | None) -> None:
    """어떤 스트림 인코딩이 와도 예외를 올리지 않는다.

    ``None`` 은 스트림에 ``encoding`` 속성이 없는 경우(파이프·테스트 캡처),
    마지막 값은 인코딩 이름 자체가 틀린 경우(LookupError)다.
    """
    assert encode_safe(to_markdown(make_result(1)), encoding)
