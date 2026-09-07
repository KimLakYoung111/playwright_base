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

    retries: int = 0

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


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


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

    resolved_browser = (browser or _env_str("BROWSER", merged.get("browser", "chromium"))).lower()
    if resolved_browser not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"지원하지 않는 Browser 입니다: {resolved_browser!r}. "
            f"사용 가능: {', '.join(SUPPORTED_BROWSERS)}"
        )

    resolved_headless = _env_bool("HEADLESS", bool(merged.get("headless", True)))
    if headed:                       # --headed 는 어떤 설정보다 우선
        resolved_headless = False

    return RunConfig(
        project_name=_env_str("PROJECT_NAME", merged.get("project_name", "Automation")),
        env=env,
        base_url=_normalize_url(base_url or _env_str("BASE_URL", merged.get("base_url", ""))),
        api_base_url=_env_str("API_BASE_URL", merged.get("api_base_url", "")),
        browser=resolved_browser,
        headless=resolved_headless,
        slow_mo=_env_int("SLOW_MO", int(merged.get("slow_mo", 0))),
        default_timeout=_env_int("DEFAULT_TIMEOUT", int(timeouts.get("default", 30000))),
        navigation_timeout=_env_int("NAVIGATION_TIMEOUT", int(timeouts.get("navigation", 45000))),
        expect_timeout=_env_int("EXPECT_TIMEOUT", int(timeouts.get("expect", 10000))),
        viewport_width=_env_int("VIEWPORT_WIDTH", int(viewport.get("width", 1920))),
        viewport_height=_env_int("VIEWPORT_HEIGHT", int(viewport.get("height", 1080))),
        locale=_env_str("LOCALE", merged.get("locale", "ko-KR")),
        timezone=_env_str("TIMEZONE", merged.get("timezone", "Asia/Seoul")),
        ignore_https_errors=_env_bool(
            "IGNORE_HTTPS_ERRORS", bool(merged.get("ignore_https_errors", False))
        ),
        test_id_attribute=_env_str("TEST_ID_ATTRIBUTE",
                                   merged.get("test_id_attribute", "data-testid")),
        retries=_env_int("RETRIES", int(merged.get("retries", 0))),
        screenshot_mode=_evidence_mode("SCREENSHOT_MODE", evidence.get("screenshot", "on-failure")),
        trace_mode=_evidence_mode("TRACE_MODE", evidence.get("trace", "on-failure")),
        page_html_mode=_evidence_mode("PAGE_HTML_MODE", evidence.get("page_html", "on-failure")),
        log_mode=_evidence_mode("LOG_MODE", evidence.get("log", "on-failure")),
        accounts=_build_accounts(merged.get("accounts", {})),
        raw=merged,
    )
