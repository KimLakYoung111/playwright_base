"""로그 마스킹(``SensitiveDataFilter``) 단위 테스트 — URL 에 박은 자격증명.

가리지 못하면 ``--base-url`` 로 넘긴 값이 ``run.command`` 에 남아
**고객사에 전달하는 ``result.json`` / ``report.html`` 까지 따라갑니다.**
key=value 형태가 아니라 기존 패턴에 걸리지 않던 자리입니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import pytest

from utils.logger import MASK, SensitiveDataFilter

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Logger")]


@pytest.fixture
def masker() -> SensitiveDataFilter:
    return SensitiveDataFilter()


# ---------------------------------------------------------------------------
# 가려야 하는 것
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT301")
def test_url_password_is_masked_but_username_survives(masker) -> None:
    """``https://user:pw@host`` 는 비밀번호만 가리고 사용자명은 남긴다.

    콜론이 있으면 앞은 정의상 사용자명이다. 비밀이 아니고, 남겨야 어느 계정으로
    돌렸는지 알 수 있다.
    """
    masked = masker.mask("pytest --base-url=https://admin:s3cr3tPw@stage.client.com")
    assert masked == f"pytest --base-url=https://admin:{MASK}@stage.client.com"


@pytest.mark.tc_id("UNIT302")
def test_bare_userinfo_is_masked_entirely(masker) -> None:
    """콜론이 없으면 통째로 가린다.

    ``https://ghp_xxx@github.com/...`` 은 GitHub PAT 의 표준 형태다. 사용자명과
    문법적으로 구분할 수 없으므로 가리는 쪽으로 실패해야 한다 — 토큰이 고객사
    리포트로 나가는 손해가 사용자명을 못 보는 손해보다 크다.
    """
    masked = masker.mask("pytest --base-url=https://ghp_AbC123XyZ456@github.com/org/r")
    assert "ghp_AbC123XyZ456" not in masked
    assert masked == f"pytest --base-url=https://{MASK}@github.com/org/r"


@pytest.mark.tc_id("UNIT303")
def test_empty_username_still_masks_the_password(masker) -> None:
    """``https://:pw@host`` 도 가린다. 사용자명 없이 비밀번호만 박는 형태다."""
    masked = masker.mask("pytest --base-url=https://:s3cr3tPw@stage.client.com")
    assert "s3cr3tPw" not in masked
    assert masked == f"pytest --base-url=https://:{MASK}@stage.client.com"


@pytest.mark.tc_id("UNIT304")
@pytest.mark.parametrize("url", [
    "https://admin:s3cr3tPw@stage.client.com",
    "http://admin:s3cr3tPw@stage.client.com",
    "ssh://git@github.com/org/repo.git",
    "https://ghp_AbC123XyZ456@github.com/org/r",
])
def test_no_secret_survives_any_scheme(masker, url: str) -> None:
    """scheme 이 무엇이든 ``@`` 앞의 userinfo 가 원문 그대로 남지 않는다.

    비밀값을 부분문자열로 찾으면 안 된다. ``ssh://git@github.com/org/repo.git``
    은 가린 뒤에도 경로의 ``repo.git`` 때문에 "git" 이 남아 있어, 멀쩡히 가려진
    것을 실패로 읽는다. userinfo 자리 자체가 사라졌는지를 봐야 한다.
    """
    scheme, _, rest = url.partition("://")
    userinfo = rest.split("@", 1)[0]
    assert userinfo, "테스트 데이터가 잘못됐다 — 가릴 대상이 비어 있다"
    masked = masker.mask(f"pytest --base-url={url}")
    assert f"{scheme}://{userinfo}@" not in masked
    assert f"{scheme}://" in masked and "@" in masked


# ---------------------------------------------------------------------------
# 건드리면 안 되는 것 (과잉 마스킹 방지)
#
# 마스킹은 안전한 쪽으로 실패해야 하지만, 멀쩡한 URL 까지 뭉개면 로그가
# 쓸모없어진다. 양쪽을 다 못 박아야 한쪽으로 무너지지 않는다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT305")
@pytest.mark.parametrize("text", [
    "pytest --base-url=https://stage.client.com/login",
    "pytest --base-url=http://localhost:3000/api",
    "GET https://api.client.com/users/me@example.com",
    "contact qa@client.com for access",
])
def test_plain_text_is_left_alone(masker, text: str) -> None:
    """자격증명이 없는 URL·이메일은 한 글자도 바뀌지 않는다."""
    assert masker.mask(text) == text
