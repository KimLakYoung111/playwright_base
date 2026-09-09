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

@pytest.mark.tc_id("UNIT701")
def test_url_password_is_masked_but_username_survives(masker) -> None:
    """``https://user:pw@host`` 는 비밀번호만 가리고 사용자명은 남긴다.

    콜론이 있으면 앞은 정의상 사용자명이다. 비밀이 아니고, 남겨야 어느 계정으로
    돌렸는지 알 수 있다.
    """
    masked = masker.mask("pytest --base-url=https://admin:s3cr3tPw@stage.client.com")
    assert masked == f"pytest --base-url=https://admin:{MASK}@stage.client.com"


@pytest.mark.tc_id("UNIT702")
def test_bare_userinfo_is_masked_entirely(masker) -> None:
    """콜론이 없으면 통째로 가린다.

    ``https://ghp_xxx@github.com/...`` 은 GitHub PAT 의 표준 형태다. 사용자명과
    문법적으로 구분할 수 없으므로 가리는 쪽으로 실패해야 한다 — 토큰이 고객사
    리포트로 나가는 손해가 사용자명을 못 보는 손해보다 크다.
    """
    masked = masker.mask("pytest --base-url=https://ghp_AbC123XyZ456@github.com/org/r")
    assert "ghp_AbC123XyZ456" not in masked
    assert masked == f"pytest --base-url=https://{MASK}@github.com/org/r"


@pytest.mark.tc_id("UNIT703")
def test_empty_username_still_masks_the_password(masker) -> None:
    """``https://:pw@host`` 도 가린다. 사용자명 없이 비밀번호만 박는 형태다."""
    masked = masker.mask("pytest --base-url=https://:s3cr3tPw@stage.client.com")
    assert "s3cr3tPw" not in masked
    assert masked == f"pytest --base-url=https://:{MASK}@stage.client.com"


@pytest.mark.tc_id("UNIT704")
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

@pytest.mark.tc_id("UNIT705")
@pytest.mark.parametrize("text", [
    "pytest --base-url=https://stage.client.com/login",
    "pytest --base-url=http://localhost:3000/api",
    "GET https://api.client.com/users/me@example.com",
    "contact qa@client.com for access",
])
def test_plain_text_is_left_alone(masker, text: str) -> None:
    """자격증명이 없는 URL·이메일은 한 글자도 바뀌지 않는다."""
    assert masker.mask(text) == text


# ---------------------------------------------------------------------------
# Authorization 헤더 — 스킴은 남기고 자격증명만 가린다
#
# key=value 패턴이 먼저 돌면 "Bearer" 라는 단어를 *** 로 바꿔버려, 스킴 패턴이
# 잡아야 할 앵커가 사라지고 정작 토큰이 살아남는다. 순서 의존이라 조용히 되살아난다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT706")
@pytest.mark.parametrize("text, secret", [
    ("authorization=Bearer abcdefgh12345", "abcdefgh12345"),
    ("Authorization: Bearer abcdefgh12345", "abcdefgh12345"),
    ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
    ("Authorization: Digest cnNwYXV0aD1hYmM=", "cnNwYXV0aD1hYmM="),
    ("Bearer abcdefgh12345", "abcdefgh12345"),
])
def test_auth_scheme_credentials_are_masked(masker, text: str, secret: str) -> None:
    """스킴(Bearer/Basic/Digest) 뒤의 값이 원문으로 남지 않는다."""
    masked = masker.mask(text)
    assert secret not in masked
    assert MASK in masked


@pytest.mark.tc_id("UNIT707")
def test_auth_scheme_name_survives(masker) -> None:
    """스킴 이름은 남긴다. 어느 인증 방식이었는지는 디버깅에 필요하고 비밀이 아니다."""
    assert masker.mask("authorization=Bearer abcdefgh12345") == f"authorization=Bearer {MASK}"


# ---------------------------------------------------------------------------
# 공백으로 값을 넘기는 명령행 플래그
#
# run.command 는 result.json / report.html 로 고객사에 전달된다.
# --password=x 는 key=value 패턴이 잡지만 --password x 는 못 잡았다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT708")
@pytest.mark.parametrize("text, secret", [
    ("pytest --password hunter2", "hunter2"),
    ("pytest --token mySecretToken123 -m smoke", "mySecretToken123"),
    ("pytest --api-key AbC123XyZ -n 4", "AbC123XyZ"),
    ("pytest -m smoke --auth-token ghp_AbC123XyZ456", "ghp_AbC123XyZ456"),
])
def test_space_separated_secret_flags_are_masked(masker, text: str, secret: str) -> None:
    """공백으로 넘긴 값도 가린다. 값인지 다른 플래그인지 구분되지 않으면 가리는 쪽으로."""
    masked = masker.mask(text)
    assert secret not in masked
    assert MASK in masked


@pytest.mark.tc_id("UNIT709")
def test_ordinary_flags_are_left_alone(masker) -> None:
    """비밀과 무관한 플래그는 건드리지 않는다. 실행 명령이 읽을 수 없게 되면 안 된다."""
    text = "pytest -m smoke -n 4 --env=dev --headed"
    assert masker.mask(text) == text


# ---------------------------------------------------------------------------
# 작은따옴표 dict — API traceback 의 표준 형태
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT710")
@pytest.mark.parametrize("text, secret", [
    ("headers={'Authorization': 'Basic dXNlcjpwdw=='}", "dXNlcjpwdw=="),
    ("{'password': 'hunter2'}", "hunter2"),
    ("{'api_key': 'AbC123XyZ'}", "AbC123XyZ"),
])
def test_single_quoted_mapping_is_masked(masker, text: str, secret: str) -> None:
    """``repr(dict)`` 는 작은따옴표를 쓴다. 실패 traceback 이 그대로 result.json 에 실린다."""
    masked = masker.mask(text)
    assert secret not in masked
    assert MASK in masked


# ---------------------------------------------------------------------------
# 회귀 방지 — 패턴끼리 물려서 생긴 구멍
#
# 아래는 전부 "마스킹을 강화했다" 는 변경이 오히려 새로 뚫은 구멍이다.
# 패턴 3개(key=value · 인증 스킴 · 명령행 플래그)가 서로 물려 있어서, 한 곳을
# 고치면 다른 곳이 조용히 샌다. 양쪽 방향을 모두 못 박아야 한다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT711")
@pytest.mark.parametrize("text", [
    "password=basic",
    "token: digest",
    "pwd=bearer",
    "secret='basic'",
])
def test_value_that_looks_like_a_scheme_is_still_masked(masker, text: str) -> None:
    """값이 우연히 인증 스킴 이름이어도 가려야 한다.

    스킴 처리를 위해 key=value 패턴을 비켜서게 만들면, 스킴 패턴은 "스킴 뒤에
    공백 + 긴 토큰" 을 요구하므로 아무도 안 잡는다. 결과가 ``***`` 하나 없이
    나가서 보는 사람이 "가려졌다" 고 오판한다.
    """
    assert MASK in masker.mask(text)


@pytest.mark.tc_id("UNIT712")
@pytest.mark.parametrize("text, secret", [
    ("Authorization: Bearer abc123", "abc123"),
    ("Authorization: Basic dXNlcg==", "dXNlcg=="),
    ("authorization=Bearer x1", "x1"),
])
def test_short_scheme_credentials_are_masked(masker, text: str, secret: str) -> None:
    """짧은 자격증명도 가려야 한다. 길이로 비밀 여부를 판정할 수 없다."""
    masked = masker.mask(text)
    assert secret not in masked
    assert MASK in masked


@pytest.mark.tc_id("UNIT713")
@pytest.mark.parametrize("text", [
    "GET /auth: 200 OK",
    "user=admin auth=none",
    "https://host/cb?auth=ok&state=xyz",
    "pytest --auth-file conf.yaml --headed",
    "pytest --secretly-fast 12",
])
def test_generic_auth_words_do_not_trigger_masking(masker, text: str) -> None:
    """``auth`` 같은 흔한 낱말은 비밀 키가 아니다.

    ``authorization`` / ``auth_token`` 만 비밀로 본다. 여기를 넓히면 평범한
    접근 로그와 실행 명령이 읽을 수 없게 뭉개진다.
    """
    assert masker.mask(text) == text


@pytest.mark.tc_id("UNIT714")
def test_flag_masking_never_crosses_a_newline(masker) -> None:
    """명령행 플래그 패턴이 줄바꿈을 넘어가면 안 된다.

    여러 줄 traceback 이나 캡처된 stdout 에서 비밀 키 이름으로 끝나는 줄이
    **다음 줄 첫 토큰**을 지운다. 값과 무관한 내용이 사라져 원인 분석이 막힌다.
    """
    text = "pytest --token\nnext-line-token value"
    assert masker.mask(text) == text


@pytest.mark.tc_id("UNIT715")
@pytest.mark.parametrize("text", [
    "pytest --token --verbose",
    "pytest --password --headed -n 2",
])
def test_flag_masking_does_not_eat_the_next_flag(masker, text: str) -> None:
    """뒤따르는 것이 값이 아니라 다른 플래그면 가리지 않는다.

    플래그를 가려도 보안 이득은 0 이고 실행 명령만 읽을 수 없게 된다.
    "가리는 쪽으로 실패" 는 **값**에 대한 원칙이지 플래그에 대한 것이 아니다.
    """
    assert masker.mask(text) == text


# ---------------------------------------------------------------------------
# 스킴 이름은 영어 낱말이기도 하다
#
# basic / digest 를 스킴 목록에 넣으면 "Basic authentication required" 같은
# 평범한 문장이 자격증명으로 잡힌다. mask_secrets() 는 실패 메시지와
# traceback 에도 걸리므로, 401 관련 단정 실패의 진단 단어가 고객사 리포트에서
# 사라진다. 가려서 얻는 것이 없고 잃기만 하는 자리다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT716")
@pytest.mark.parametrize("text", [
    "HTTP 401: Basic authentication required",
    'assert "Basic authentication failed" in body',
    "basic auth with digest fallback enabled",
    "Digest challenge received: stale=true",
])
def test_scheme_words_in_prose_are_left_alone(masker, text: str) -> None:
    """스킴 뒤에 오는 것이 평범한 영어 낱말이면 자격증명이 아니다."""
    assert masker.mask(text) == text


@pytest.mark.tc_id("UNIT717")
@pytest.mark.parametrize("text, secret", [
    ("Bearer abcdefgh12345", "abcdefgh12345"),
    ("Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
    ("Digest cnNwYXV0aD1hYmM=", "cnNwYXV0aD1hYmM="),
])
def test_real_credentials_after_a_scheme_are_still_masked(masker, text: str,
                                                          secret: str) -> None:
    """진짜 자격증명은 그대로 가린다. 위 예외가 구멍이 되면 안 된다.

    실제 토큰은 base64·hex·JWT 라 숫자나 ``= / + _ - .`` 를 포함한다.
    영어 낱말과 갈리는 지점이 거기다.
    """
    masked = masker.mask(text)
    assert secret not in masked
    assert MASK in masked


# ---------------------------------------------------------------------------
# 값이 우연히 스킴 이름일 때
#
# key=SCHEME word 는 "스킴 + 자격증명" 인지 "값 + 다음 낱말" 인지 문법으로
# 구분되지 않는다. Authorization 계열만 스킴을 남기고, 나머지 비밀 키는
# 스킴처럼 보이는 것까지 값으로 보고 가린다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT718")
@pytest.mark.parametrize("text, leaked", [
    ("password=basic auth", "basic"),
    ("token=digest mode", "digest"),
    ("pwd=bearer x", "bearer"),
])
def test_scheme_shaped_value_does_not_survive(masker, text: str, leaked: str) -> None:
    """password=basic auth 에서 진짜 값인 'basic' 이 남으면 안 된다.

    스킴 통과를 무조건 허용하면 스킴 자리로 오인된 **값**이 원문으로 남는다.
    """
    masked = masker.mask(text)
    assert MASK in masked
    assert leaked not in masked


@pytest.mark.tc_id("UNIT719")
def test_authorization_keeps_scheme_even_without_digits(masker) -> None:
    """Authorization 계열은 토큰 모양을 따지지 않고 가린다.

    "자격증명처럼 생겼을 때만 가린다" 를 여기까지 적용하면, 숫자 없는 토큰에서
    스킴이 값으로 오인돼 **진짜 토큰이 그대로 남는다**. 키가 이미 비밀임을
    말해주므로 모양을 따질 이유가 없다.
    """
    masked = masker.mask("Authorization: Bearer abcdefgh")
    assert "abcdefgh" not in masked
    assert MASK in masked


@pytest.mark.tc_id("UNIT720")
@pytest.mark.parametrize("text", [
    "token:\nnextline value",
    "password:\nsecond-line token",
])
def test_key_value_separator_never_crosses_a_newline(masker, text: str) -> None:
    """key=value 구분자도 줄바꿈을 넘으면 안 된다.

    플래그 패턴(UNIT714)만 고치고 형제 패턴을 두면 같은 버그가 그대로 남는다.
    비밀 키 이름으로 끝나는 줄이 **다음 줄 첫 토큰**을 지운다.
    """
    assert masker.mask(text) == text
