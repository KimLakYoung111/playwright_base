"""실행 설정 로딩.

우선순위 (뒤로 갈수록 강함):
    1. config/default.yaml
    2. config/<env>.yaml
    3. .env / OS 환경변수
    4. CLI 옵션 (--env, --browser, --headed, --base-url ...)

테스트 코드는 이 모듈이 만든 ``RunConfig`` 만 보면 되고,
값이 어디서 왔는지는 알 필요가 없습니다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

SUPPORTED_ENVS = ("dev", "staging", "prod")
SUPPORTED_BROWSERS = ("chromium", "firefox", "webkit")
EVIDENCE_MODES = ("always", "on-failure", "never")


@dataclass(frozen=True)
class Account:
    """테스트 계정. password 는 .env 에서만 읽습니다."""

    role: str
    username: str
    password: str = ""

    def __repr__(self) -> str:  # 로그/에러 메시지에 비밀번호가 새지 않도록
        return f"Account(role={self.role!r}, username={self.username!r}, password=***)"


@dataclass
class RunConfig:
    """한 번의 pytest 실행에 적용되는 설정."""

    project_name: str = "Automation"
    env: str = "staging"
    base_url: str = ""
    api_base_url: str = ""

    browser: str = "chromium"
    headless: bool = True
    slow_mo: int = 0

    default_timeout: int = 30000
    navigation_timeout: int = 45000
    expect_timeout: int = 10000

    viewport_width: int = 1920
    viewport_height: int = 1080

    locale: str = "ko-KR"
    timezone: str = "Asia/Seoul"
    ignore_https_errors: bool = False

    #: get_by_test_id() 가 찾을 속성. 사이트가 data-qa 등을 쓰면 바꿉니다.
    test_id_attribute: str = "data-testid"

    #: 테스트 대상 앱의 버전 (주입값). 비어 있으면 리포트에 표시하지 않습니다.
    app_version: str = ""
    #: 실행자 이름을 리포트에 남길지 (개인정보 우려로 끌 수 있음)
    show_triggered_by: bool = True
    #: 실행이 끝나면 report.html 을 기본 브라우저로 열지.
    #: CI 로 보이는 환경에서는 기본값이 False 가 됩니다 (:func:`_running_in_ci`).
    open_report: bool = True

    retries: int = 0

    #: 오래된 artifacts/<실행시각>/ 폴더 보관 정책. 0 이면 정리하지 않습니다.
    artifacts_keep_days: int = 14
    artifacts_keep_min_runs: int = 5

    screenshot_mode: str = "on-failure"   # always | on-failure | never
    trace_mode: str = "on-failure"
    page_html_mode: str = "on-failure"
    log_mode: str = "on-failure"

    accounts: dict[str, Account] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)   # yaml 원본 (프로젝트별 확장용)

    # ------------------------------------------------------------------
    # 편의 메서드
    # ------------------------------------------------------------------
    @property
    def viewport(self) -> dict[str, int]:
        return {"width": self.viewport_width, "height": self.viewport_height}

    def account(self, role: str = "user") -> Account:
        """역할별 계정을 가져옵니다. 없으면 이해하기 쉬운 에러를 냅니다."""
        try:
            return self.accounts[role]
        except KeyError:
            known = ", ".join(sorted(self.accounts)) or "(없음)"
            raise KeyError(
                f"'{role}' 계정이 config 의 accounts 에 없습니다. 사용 가능한 역할: {known}"
            ) from None

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """yaml 원본에서 값을 꺼냅니다. 예) cfg.get("features.new_checkout")"""
        node: Any = self.raw
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def secrets(self) -> list[str]:
        """로그 마스킹 대상 문자열 목록."""
        values = [a.password for a in self.accounts.values() if a.password]
        for key in ("API_TOKEN", "AUTH_TOKEN", "ACCESS_TOKEN"):
            if os.getenv(key):
                values.append(os.environ[key])
        return [v for v in values if len(v) >= 4]


# ----------------------------------------------------------------------
# 내부 헬퍼
# ----------------------------------------------------------------------
def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def _env_str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value.strip() if value and value.strip() else default


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if not value or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        # 조용히 기본값으로 되돌리면 "왜 내가 준 값이 안 먹지?" 로 시간을 잃습니다.
        raise ValueError(
            f"{key} 는 숫자여야 합니다. 지금 값: {value.strip()!r}"
        ) from None


#: 참으로 읽는 문자열. 환경변수와 yaml 이 같은 규칙을 쓰도록 한 군데 둡니다.
TRUE_STRINGS = frozenset({"1", "true", "yes", "y", "on"})


#: 거짓으로 읽는 문자열. CI 판별처럼 "값이 있으면 참" 인 곳에서 예외를 만듭니다.
FALSE_STRINGS = frozenset({"0", "false", "no", "n", "off"})

#: CI 라고 볼 환경변수. 대부분의 CI 가 이 중 하나를 자동으로 넣어줍니다.
#: JENKINS_URL 처럼 값이 "true" 가 아닌 것도 있어 TRUE_STRINGS 로는 못 봅니다.
CI_ENV_KEYS = (
    "CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL",
    "TF_BUILD", "BUILDKITE", "CIRCLECI", "TEAMCITY_VERSION",
)


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in TRUE_STRINGS


def _running_in_ci() -> bool:
    """CI 위에서 도는 중인지.

    CI 에서 브라우저를 띄우면 아무도 못 보는 창이 프로세스에 남아 실행이
    끝나지 않을 수 있습니다. 그래서 리포트 자동 열기의 **기본값만** 여기서
    끕니다. ``OPEN_REPORT`` 나 ``--open-report`` 를 직접 주면 그것이 우선입니다.
    """
    for key in CI_ENV_KEYS:
        value = (os.getenv(key) or "").strip().lower()
        if value and value not in FALSE_STRINGS:
            return True
    return False


def _yaml_missing(value: Any) -> bool:
    """yaml 에서 "값을 안 준 것" 으로 볼지.

    ``keep_days:`` 처럼 키만 쓰고 값을 비워두면 yaml 은 None 을 줍니다.
    ``cfg.get(key, default)`` 는 키가 있으니 그 None 을 그대로 돌려주고,
    받는 쪽에서 ``int(None)`` 이 TypeError 로 터집니다. conftest 는 ValueError
    만 UsageError 로 바꾸므로 사용자는 친절한 메시지 대신 INTERNALERROR
    트레이스백을 봅니다. 그래서 "빈 값 = 안 준 것" 으로 통일합니다.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _yaml_int(cfg: dict, key: str, default: int, label: str | None = None) -> int:
    """yaml 값을 정수로. ``label`` 은 오류 메시지에 쓸 이름입니다.

    중첩 키는 ``label="timeouts.default"`` 처럼 넘기세요. 그냥 두면
    "default 는 숫자여야 합니다" 가 되어 어느 설정인지 알 수 없습니다.
    """
    value = (cfg or {}).get(key)
    if _yaml_missing(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{label or key} 는 숫자여야 합니다. 지금 값: {value!r}"
        ) from None


def _yaml_bool(cfg: dict, key: str, default: bool) -> bool:
    """yaml 값을 불리언으로.

    ``show_triggered_by: "false"`` 처럼 **따옴표를 치면 문자열로 옵니다.**
    ``bool("false")`` 는 True 라, 그대로 두면 개인정보 옵트아웃이 조용히
    무시된 채 실행자 이름이 고객사 리포트에 그대로 실립니다.
    환경변수와 같은 규칙(:data:`TRUE_STRINGS`)으로 읽습니다.
    """
    value = (cfg or {}).get(key)
    if _yaml_missing(value):
        return default
    if isinstance(value, str):
        return value.strip().lower() in TRUE_STRINGS
    return bool(value)


def _yaml_str(cfg: dict, key: str, default: str) -> str:
    """yaml 값을 문자열로. 스키마가 약속한 타입을 지킵니다.

    ``app_version: 2.10`` 은 yaml 이 **float 2.1 로 읽습니다.** 여기서 str 로
    바꿔도 이미 잃은 0 은 못 되살립니다(``"2.1"`` 이 됩니다). 이 함수가 막는
    것은 result.json 에 숫자가 들어가 ``result_schema.md`` 의 "문자열" 약속이
    깨지는 것까지입니다.
    → 자릿수를 지키려면 **yaml 에서 따옴표를 치세요**: ``app_version: "2.10"``.
    """
    value = (cfg or {}).get(key)
    if _yaml_missing(value):
        return default
    return str(value)


def _build_accounts(raw_accounts: dict) -> dict[str, Account]:
    accounts: dict[str, Account] = {}
    for role, spec in (raw_accounts or {}).items():
        spec = spec or {}
        # 비밀번호는 yaml 이 아니라 .env 의 변수에서만 읽습니다.
        password_env = spec.get("password_env", f"{role.upper()}_PASSWORD")
        username = _env_str(f"ACCOUNT_{role.upper()}_USERNAME", str(spec.get("username", "")))
        accounts[role] = Account(role=role, username=username,
                                 password=os.getenv(password_env, ""))
    return accounts


def _normalize_url(url: str) -> str:
    """base_url 은 뒤에 / 를 붙여 상대경로 결합이 예측 가능하게 만듭니다."""
    url = (url or "").strip()
    if not url:
        return ""
    return url if url.endswith("/") else url + "/"


def _evidence_mode(key: str, default: str) -> str:
    """always / on-failure / never 만 허용합니다. 오타를 조용히 넘기지 않습니다."""
    mode = _env_str(key, str(default)).strip().lower()
    if mode not in EVIDENCE_MODES:
        raise ValueError(
            f"{key} 값이 올바르지 않습니다: {mode!r}. "
            f"사용 가능: {', '.join(EVIDENCE_MODES)}"
        )
    return mode


# ----------------------------------------------------------------------
# 공개 API
# ----------------------------------------------------------------------
def load_config(
    env: str | None = None,
    browser: str | None = None,
    headed: bool | None = None,
    base_url: str | None = None,
) -> RunConfig:
    """설정을 병합해 ``RunConfig`` 를 만듭니다. 인자는 CLI 옵션(최우선)입니다.

    설정값이 잘못되면 ``ValueError`` 를 냅니다.
    conftest 가 이를 ``pytest.UsageError`` 로 바꿔 읽기 좋은 메시지로 보여줍니다.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    env = (env or _env_str("ENV", "staging")).lower()
    if env not in SUPPORTED_ENVS:
        raise ValueError(
            f"지원하지 않는 환경입니다: {env!r}. 사용 가능: {', '.join(SUPPORTED_ENVS)}"
        )

    merged = _deep_merge(
        _read_yaml(CONFIG_DIR / "default.yaml"),
        _read_yaml(CONFIG_DIR / f"{env}.yaml"),
    )

    timeouts = merged.get("timeouts") or {}
    viewport = merged.get("viewport") or {}
    evidence = merged.get("evidence") or {}
    artifacts_cfg = merged.get("artifacts") or {}
    report_cfg = merged.get("report") or {}

    resolved_browser = (browser or _env_str("BROWSER", merged.get("browser", "chromium"))).lower()
    if resolved_browser not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"지원하지 않는 Browser 입니다: {resolved_browser!r}. "
            f"사용 가능: {', '.join(SUPPORTED_BROWSERS)}"
        )

    resolved_headless = _env_bool("HEADLESS", _yaml_bool(merged, "headless", True))
    if headed:                       # --headed 는 어떤 설정보다 우선
        resolved_headless = False

    # 리포트 자동 열기. yaml 이 켜져 있어도 CI 면 기본값을 꺼둡니다.
    # OPEN_REPORT 를 직접 준 경우에는 CI 여부와 무관하게 그 값을 씁니다.
    open_report_default = _yaml_bool(report_cfg, "auto_open", True) and not _running_in_ci()

    return RunConfig(
        project_name=_env_str("PROJECT_NAME", merged.get("project_name", "Automation")),
        env=env,
        base_url=_normalize_url(base_url or _env_str("BASE_URL", merged.get("base_url", ""))),
        api_base_url=_env_str("API_BASE_URL", merged.get("api_base_url", "")),
        browser=resolved_browser,
        headless=resolved_headless,
        slow_mo=_env_int("SLOW_MO", _yaml_int(merged, "slow_mo", 0)),
        default_timeout=_env_int(
            "DEFAULT_TIMEOUT", _yaml_int(timeouts, "default", 30000, "timeouts.default")),
        navigation_timeout=_env_int(
            "NAVIGATION_TIMEOUT", _yaml_int(timeouts, "navigation", 45000, "timeouts.navigation")),
        expect_timeout=_env_int(
            "EXPECT_TIMEOUT", _yaml_int(timeouts, "expect", 10000, "timeouts.expect")),
        viewport_width=_env_int(
            "VIEWPORT_WIDTH", _yaml_int(viewport, "width", 1920, "viewport.width")),
        viewport_height=_env_int(
            "VIEWPORT_HEIGHT", _yaml_int(viewport, "height", 1080, "viewport.height")),
        locale=_env_str("LOCALE", merged.get("locale", "ko-KR")),
        timezone=_env_str("TIMEZONE", merged.get("timezone", "Asia/Seoul")),
        ignore_https_errors=_env_bool(
            "IGNORE_HTTPS_ERRORS", _yaml_bool(merged, "ignore_https_errors", False)
        ),
        test_id_attribute=_env_str("TEST_ID_ATTRIBUTE",
                                   merged.get("test_id_attribute", "data-testid")),
        app_version=_env_str("APP_VERSION", _yaml_str(merged, "app_version", "")),
        show_triggered_by=_env_bool("SHOW_TRIGGERED_BY",
                                    _yaml_bool(report_cfg, "show_triggered_by", True)),
        open_report=_env_bool("OPEN_REPORT", open_report_default),
        retries=_env_int("RETRIES", _yaml_int(merged, "retries", 0)),
        artifacts_keep_days=_env_int("ARTIFACTS_KEEP_DAYS",
                                     _yaml_int(artifacts_cfg, "keep_days", 14)),
        artifacts_keep_min_runs=_env_int("ARTIFACTS_KEEP_MIN_RUNS",
                                         _yaml_int(artifacts_cfg, "keep_min_runs", 5)),
        screenshot_mode=_evidence_mode("SCREENSHOT_MODE", evidence.get("screenshot", "on-failure")),
        trace_mode=_evidence_mode("TRACE_MODE", evidence.get("trace", "on-failure")),
        page_html_mode=_evidence_mode("PAGE_HTML_MODE", evidence.get("page_html", "on-failure")),
        log_mode=_evidence_mode("LOG_MODE", evidence.get("log", "on-failure")),
        accounts=_build_accounts(merged.get("accounts", {})),
        raw=merged,
    )
