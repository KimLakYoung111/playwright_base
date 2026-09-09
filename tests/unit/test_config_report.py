"""리포트용 설정값(``app_version``, ``show_triggered_by``, ``artifacts``) 단위 테스트.

**저장소의 ``config/*.yaml`` 을 읽지 않습니다.** 읽으면 고객사가 그 파일을
고치는 순간(``show_triggered_by: false`` 는 default.yaml 이 스스로 권하는
설정입니다) 커밋 게이트인 ``pytest -m base_unit`` 이 엉뚱한 이유로 깨집니다.
그래서 ``_read_yaml`` 을 갈아끼워 설정 내용을 테스트가 직접 정합니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from utils import config as config_module
from utils.config import load_config

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Config")]


@pytest.fixture
def yaml_config(monkeypatch: pytest.MonkeyPatch):
    """``config/*.yaml`` 대신 테스트가 준 dict 를 읽게 만듭니다.

    환경변수도 함께 비웁니다. ``load_config`` 는 ``.env`` 를
    ``override=False`` 로 읽어들이므로, ``delenv`` 로 지워도 ``.env`` 에 값이
    있으면 다시 채워집니다. 빈 문자열로 덮어써야 yaml 경로를 확실히 탑니다
    (``_env_str`` / ``_env_int`` 는 빈 값을 "안 준 것" 으로 봅니다).
    """
    def _apply(default_yaml: dict[str, Any], **env: str) -> None:
        def _fake_read(path: Path) -> dict[str, Any]:
            # env 별 yaml(staging.yaml 등)은 비워 둡니다. 병합 결과가
            # default_yaml 그대로여야 테스트가 읽기 쉽습니다.
            return dict(default_yaml) if path.name == "default.yaml" else {}

        monkeypatch.setattr(config_module, "_read_yaml", _fake_read)
        # CI 판별 변수도 비웁니다. GitHub Actions 에서 이 파일을 돌리면 CI=true 가
        # 이미 들어 있어 open_report 기본값 테스트가 통째로 뒤집힙니다.
        #  delenv 가 아니라 빈 문자열로 덮어씁니다 — 위 docstring 과 같은 이유입니다.
        #  지우기만 하면 load_config 가 .env 를 다시 읽어(override=False) 되살립니다.
        for key in config_module.CI_ENV_KEYS:
            monkeypatch.setenv(key, env.get(key, ""))
        for key in ("APP_VERSION", "SHOW_TRIGGERED_BY", "OPEN_REPORT",
                    "ARTIFACTS_KEEP_DAYS", "ARTIFACTS_KEEP_MIN_RUNS",
                    # 아래는 yaml 빈 값 회귀 테스트용. 하나라도 빠뜨리면 .env 나
                    # 셸의 값이 yaml 을 덮어써 테스트가 조용히 통과합니다.
                    "SLOW_MO", "RETRIES", "HEADLESS", "IGNORE_HTTPS_ERRORS",
                    "DEFAULT_TIMEOUT", "NAVIGATION_TIMEOUT", "EXPECT_TIMEOUT",
                    "VIEWPORT_WIDTH", "VIEWPORT_HEIGHT",
                    # 문자열 설정. 여기 빠지면 .env 의 값이 yaml 경로를 덮어
                    # "빈 값이면 기본값" 테스트가 아무것도 검증하지 못한다.
                    "PROJECT_NAME", "BASE_URL", "API_BASE_URL", "LOCALE", "TIMEZONE",
                    "TEST_ID_ATTRIBUTE", "BROWSER",
                    "SCREENSHOT_MODE", "TRACE_MODE", "PAGE_HTML_MODE", "LOG_MODE"):
            monkeypatch.setenv(key, env.get(key, ""))

    return _apply


# ---------------------------------------------------------------------------
# app_version
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT201")
def test_app_version_defaults_to_empty(yaml_config) -> None:
    """기본값은 빈 문자열이다. 고객사마다 버전 체계가 달라 강제하지 않는다."""
    yaml_config({})
    assert load_config(env="staging").app_version == ""


@pytest.mark.tc_id("UNIT202")
def test_app_version_from_environment(yaml_config) -> None:
    """CI 는 APP_VERSION 환경변수로 준다. yaml 값보다 세다."""
    yaml_config({"app_version": "yaml-값"}, APP_VERSION="v2.14.3 (build 8821)")
    assert load_config(env="staging").app_version == "v2.14.3 (build 8821)"


@pytest.mark.tc_id("UNIT203")
def test_app_version_keeps_numeric_looking_version_as_text(yaml_config) -> None:
    """``app_version: 2.10`` 은 yaml 이 float 로 읽는다. 문자열 타입은 지켜야 한다.

    지키는 것은 **타입뿐이다.** yaml 이 이미 2.1 로 만들어 넘기므로 잃은 0 은
    되살릴 수 없다 — 자릿수를 지키려면 yaml 에서 따옴표를 쳐야 한다
    (``app_version: "2.10"``). 여기서 막는 것은 result.json 에 숫자가 들어가
    ``result_schema.md`` 의 "문자열" 약속이 깨지는 것까지다.
    """
    yaml_config({"app_version": 2.10})
    version = load_config(env="staging").app_version
    assert isinstance(version, str)
    assert version == "2.1"


@pytest.mark.tc_id("UNIT211")
def test_quoted_app_version_keeps_every_digit(yaml_config) -> None:
    """따옴표를 치면 yaml 이 문자열로 읽어 자릿수가 그대로 남는다."""
    yaml_config({"app_version": "2.10"})
    assert load_config(env="staging").app_version == "2.10"


# ---------------------------------------------------------------------------
# report.show_triggered_by
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT204")
def test_show_triggered_by_defaults_to_true(yaml_config) -> None:
    """설정을 아예 안 주면 켜져 있다."""
    yaml_config({})
    assert load_config(env="staging").show_triggered_by is True


@pytest.mark.tc_id("UNIT205")
def test_show_triggered_by_can_be_disabled_in_yaml(yaml_config) -> None:
    """개인정보가 걸리는 고객사는 yaml 에서 끈다 (default.yaml 이 권하는 방법)."""
    yaml_config({"report": {"show_triggered_by": False}})
    assert load_config(env="staging").show_triggered_by is False


@pytest.mark.tc_id("UNIT206")
def test_show_triggered_by_can_be_disabled_by_env(yaml_config) -> None:
    """환경변수로도 끌 수 있다."""
    yaml_config({}, SHOW_TRIGGERED_BY="false")
    assert load_config(env="staging").show_triggered_by is False


@pytest.mark.tc_id("UNIT207")
def test_empty_show_triggered_by_falls_back_to_default(yaml_config) -> None:
    """``show_triggered_by:`` 처럼 값을 비우면 yaml 은 None 을 준다.

    ``bool(None)`` 은 False 라, 값을 안 준 것이 "끔" 으로 조용히 뒤집힌다.
    """
    yaml_config({"report": {"show_triggered_by": None}})
    assert load_config(env="staging").show_triggered_by is True


# ---------------------------------------------------------------------------
# report.auto_open (실행 후 리포트 자동 열기)
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT216")
def test_open_report_defaults_to_true(yaml_config) -> None:
    """설정을 안 주면 켜져 있다 (로컬에서 실행하면 리포트가 뜬다)."""
    yaml_config({})
    assert load_config(env="staging").open_report is True


@pytest.mark.tc_id("UNIT217")
def test_open_report_can_be_disabled_in_yaml(yaml_config) -> None:
    """yaml 로 끌 수 있다."""
    yaml_config({"report": {"auto_open": False}})
    assert load_config(env="staging").open_report is False


@pytest.mark.tc_id("UNIT218")
def test_open_report_is_off_in_ci(yaml_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 에서는 기본값이 꺼진다.

    아무도 못 보는 브라우저 창이 떠서 실행이 끝나지 않는 것을 막는다.
    """
    yaml_config({})
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert load_config(env="staging").open_report is False


@pytest.mark.tc_id("UNIT219")
def test_explicit_env_wins_over_ci_detection(yaml_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 자동 제외는 '기본값' 만 바꾼다. 직접 켜면 켜져야 한다."""
    yaml_config({}, OPEN_REPORT="true")
    monkeypatch.setenv("CI", "true")
    assert load_config(env="staging").open_report is True


@pytest.mark.tc_id("UNIT220")
def test_ci_set_to_false_is_not_ci(yaml_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """``CI=false`` 는 CI 가 아니다.

    "값이 있으면 CI" 로 보면 이 흔한 설정에서 리포트가 조용히 안 뜬다.
    """
    yaml_config({})
    monkeypatch.setenv("CI", "false")
    assert load_config(env="staging").open_report is True


# ---------------------------------------------------------------------------
# artifacts 정리 설정
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT208")
def test_artifacts_retention_defaults(yaml_config) -> None:
    """설정을 안 주면 14일 / 최근 5개다."""
    yaml_config({})
    run_config = load_config(env="staging")
    assert (run_config.artifacts_keep_days, run_config.artifacts_keep_min_runs) == (14, 5)


@pytest.mark.tc_id("UNIT209")
def test_empty_keep_days_falls_back_to_default(yaml_config) -> None:
    """``keep_days:`` 로 값을 비워두면 기본값이다.

    ``int(None)`` 은 TypeError 인데 conftest 는 ValueError 만 UsageError 로
    바꾼다. 그대로 두면 사용자가 설정 오타 하나에 INTERNALERROR 트레이스백을 본다.
    """
    yaml_config({"artifacts": {"keep_days": None, "keep_min_runs": None}})
    run_config = load_config(env="staging")
    assert (run_config.artifacts_keep_days, run_config.artifacts_keep_min_runs) == (14, 5)


@pytest.mark.tc_id("UNIT210")
def test_non_numeric_keep_days_raises_value_error(yaml_config) -> None:
    """숫자가 아니면 ValueError. conftest 가 이걸 UsageError 로 바꿔 보여준다."""
    yaml_config({"artifacts": {"keep_days": "이주일"}})
    with pytest.raises(ValueError, match="keep_days"):
        load_config(env="staging")


# ---------------------------------------------------------------------------
# yaml 빈 값 — 설정 전반
#
# 위의 keep_days / show_triggered_by 만 고쳐두면 같은 버그가 나머지 설정에
# 그대로 남는다. "고치려던 것을 절반만 고친" 자리라 전수로 못 박는다.
# ---------------------------------------------------------------------------

#: (표시용 이름, 빈 값을 넣은 yaml, RunConfig 속성, 기대 기본값)
EMPTY_VALUE_CASES = [
    ("slow_mo", {"slow_mo": None}, "slow_mo", 0),
    ("retries", {"retries": None}, "retries", 0),
    ("timeouts.default", {"timeouts": {"default": None}}, "default_timeout", 30000),
    ("timeouts.navigation", {"timeouts": {"navigation": None}}, "navigation_timeout", 45000),
    ("timeouts.expect", {"timeouts": {"expect": None}}, "expect_timeout", 10000),
    ("viewport.width", {"viewport": {"width": None}}, "viewport_width", 1920),
    ("viewport.height", {"viewport": {"height": None}}, "viewport_height", 1080),
]


@pytest.mark.tc_id("UNIT212")
@pytest.mark.parametrize("name, yaml_body, attribute, expected", EMPTY_VALUE_CASES,
                         ids=[case[0] for case in EMPTY_VALUE_CASES])
def test_empty_numeric_settings_fall_back_to_default(
    yaml_config, name: str, yaml_body: dict, attribute: str, expected: int
) -> None:
    """숫자 설정에 값을 안 주면 기본값이다. TypeError 로 터지지 않는다.

    ``int(None)`` 은 TypeError 인데 conftest 는 ValueError 만 UsageError 로
    바꾼다. 하나라도 빠뜨리면 사용자가 설정 오타에 INTERNALERROR 를 본다.
    """
    yaml_config(yaml_body)
    assert getattr(load_config(env="staging"), attribute) == expected


@pytest.mark.tc_id("UNIT213")
def test_empty_headless_stays_true(yaml_config) -> None:
    """``headless:`` 로 값을 비워도 headless 는 유지된다.

    ``bool(None)`` 은 False 라 값을 안 준 것이 "브라우저 띄우기" 로 조용히
    뒤집힌다. CI 는 디스플레이가 없어 브라우저 실행에서 죽는데, 설정 어디에도
    단서가 없어 원인을 찾기 어렵다. **터지지 않고 조용히 틀리는 쪽**이라
    숫자 설정보다 위험하다.
    """
    yaml_config({"headless": None})
    assert load_config(env="staging").headless is True


@pytest.mark.tc_id("UNIT214")
@pytest.mark.parametrize("written", ["false", "False", "0", "no", "off"])
def test_quoted_false_actually_disables_triggered_by(yaml_config, written: str) -> None:
    """``show_triggered_by: "false"`` 처럼 따옴표를 쳐도 꺼져야 한다.

    yaml 에서 따옴표를 치면 문자열로 온다. ``bool("false")`` 는 True 라
    개인정보 옵트아웃이 조용히 무시되고 실행자 이름이 고객사 리포트에 실린다.
    """
    yaml_config({"report": {"show_triggered_by": written}})
    assert load_config(env="staging").show_triggered_by is False


@pytest.mark.tc_id("UNIT215")
@pytest.mark.parametrize("yaml_body, expected_name", [
    ({"timeouts": {"default": "삼십초"}}, "timeouts.default"),
    ({"viewport": {"width": "넓게"}}, "viewport.width"),
    ({"slow_mo": "천천히"}, "slow_mo"),
])
def test_non_numeric_setting_names_the_nested_key(
    yaml_config, yaml_body: dict, expected_name: str
) -> None:
    """오류 메시지가 중첩 키의 전체 이름을 말해야 한다.

    ``default 는 숫자여야 합니다`` 로는 timeouts 인지 viewport 인지 알 수 없다.
    """
    yaml_config(yaml_body)
    with pytest.raises(ValueError, match=expected_name.replace(".", r"\.")):
        load_config(env="staging")


# ---------------------------------------------------------------------------
# yaml 빈 값 — 문자열 설정
#
# 숫자·불리언만 고치고 문자열을 빼먹으면 같은 버그가 그대로 남는다.
# test_id_attribute 가 None 이면 conftest 가 set_test_id_attribute(None) 을
# 불러 세션 fixture 단계에서 TypeError 로 죽는다 (UsageError 도 아니다).
# ---------------------------------------------------------------------------

#: (표시용 이름, 빈 값을 넣은 yaml, RunConfig 속성, 기대 기본값)
EMPTY_STRING_CASES = [
    ("project_name", {"project_name": None}, "project_name", "Automation"),
    ("api_base_url", {"api_base_url": None}, "api_base_url", ""),
    ("locale", {"locale": None}, "locale", "ko-KR"),
    ("timezone", {"timezone": None}, "timezone", "Asia/Seoul"),
    ("test_id_attribute", {"test_id_attribute": None}, "test_id_attribute", "data-testid"),
    ("browser", {"browser": None}, "browser", "chromium"),
    ("evidence.screenshot", {"evidence": {"screenshot": None}}, "screenshot_mode", "on-failure"),
    ("evidence.trace", {"evidence": {"trace": None}}, "trace_mode", "on-failure"),
]


@pytest.mark.tc_id("UNIT221")
@pytest.mark.parametrize("name, yaml_body, attribute, expected", EMPTY_STRING_CASES,
                         ids=[case[0] for case in EMPTY_STRING_CASES])
def test_empty_string_settings_fall_back_to_default(
    yaml_config, name: str, yaml_body: dict, attribute: str, expected: str
) -> None:
    """문자열 설정에 값을 안 주면 기본값이다. None 이 흘러가지 않는다."""
    yaml_config(yaml_body)
    assert getattr(load_config(env="staging"), attribute) == expected


@pytest.mark.tc_id("UNIT222")
def test_numeric_project_name_becomes_text(yaml_config) -> None:
    """``project_name: 2026`` 은 yaml 이 int 로 읽는다. 리포트 제목에 쓰이므로 문자열이어야 한다."""
    yaml_config({"project_name": 2026})
    assert load_config(env="staging").project_name == "2026"


# ---------------------------------------------------------------------------
# 불리언 오타
#
# 숫자는 오타를 거절하는데 불리언만 조용히 False 로 떨어지면 규칙이 어긋난다.
# headless: ture -> False 면 화면 없는 CI 에서 이유를 알 수 없이 죽는다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT223")
@pytest.mark.parametrize("yaml_body, needle", [
    ({"headless": "ture"}, "headless"),
    ({"ignore_https_errors": "예"}, "ignore_https_errors"),
    ({"report": {"show_triggered_by": "nope"}}, "report.show_triggered_by"),
])
def test_unknown_boolean_string_is_rejected(yaml_config, yaml_body: dict, needle: str) -> None:
    """모르는 문자열은 ValueError. conftest 가 UsageError 로 바꿔 보여준다."""
    yaml_config(yaml_body)
    with pytest.raises(ValueError, match=needle):
        load_config(env="staging")


@pytest.mark.tc_id("UNIT224")
@pytest.mark.parametrize("value, expected", [
    ("false", False), ("off", False), ("no", False), ("0", False),
    ("true", True), ("on", True), ("yes", True), ("1", True),
    (False, False), (True, True),
])
def test_boolean_strings_are_understood(yaml_config, value, expected: bool) -> None:
    """따옴표를 쳐도 환경변수와 같은 규칙으로 읽는다."""
    yaml_config({"report": {"show_triggered_by": value}})
    assert load_config(env="staging").show_triggered_by is expected


@pytest.mark.tc_id("UNIT225")
def test_nested_numeric_error_names_the_parent_key(yaml_config) -> None:
    """중첩 키는 오류 메시지에 부모까지 적는다. keep_days 만 나오면 어느 설정인지 모른다."""
    yaml_config({"artifacts": {"keep_days": "이주일"}})
    with pytest.raises(ValueError, match=r"artifacts\.keep_days"):
        load_config(env="staging")


# ---------------------------------------------------------------------------
# 오류 메시지가 "어느 설정인지" 를 말하는가 — 빠뜨리기 쉬운 자리
#
# label 을 붙이는 작업은 한 군데만 빠뜨려도 티가 안 난다. 테스트가 통과하고
# 동작도 정상이라, 사용자가 오타를 냈을 때에만 드러난다.
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT226")
def test_report_auto_open_error_names_its_section(yaml_config) -> None:
    """``report.auto_open`` 오타도 섹션을 밝힌다.

    바로 옆 ``show_triggered_by`` 에만 label 이 붙어 있어서, 이 키는
    "auto_open 는 참/거짓이어야 합니다" 로 끝나 어느 섹션인지 알 수 없었다.
    """
    yaml_config({"report": {"auto_open": "ture"}})
    with pytest.raises(ValueError, match=r"report\.auto_open"):
        load_config(env="staging")


@pytest.mark.tc_id("UNIT227")
@pytest.mark.parametrize("key, setting", [
    ("screenshot", "evidence.screenshot"),
    ("trace", "evidence.trace"),
    ("page_html", "evidence.page_html"),
    ("log", "evidence.log"),
])
def test_evidence_mode_error_names_the_yaml_key(yaml_config, key: str, setting: str) -> None:
    """yaml 오타인데 환경변수 이름만 말하면 안 된다.

    ``evidence: {screenshot: alwyas}`` 에 "SCREENSHOT_MODE 값이 올바르지
    않습니다" 만 뜨면, 사용자는 **설정한 적도 없는 환경변수**를 뒤진다.
    값이 어느 쪽에서 왔는지 알 수 없으므로 둘 다 보여준다.
    """
    yaml_config({"evidence": {key: "alwyas"}})
    with pytest.raises(ValueError, match=setting.replace(".", r"\.")):
        load_config(env="staging")
