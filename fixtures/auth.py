"""로그인 세션 재사용 / 역할별 계정.

기본 동작
---------
테스트마다 새 Browser Context 를 쓰기 때문에 테스트끼리 상태가 섞이지 않습니다.
(pytest-playwright 의 ``context`` fixture 가 이미 그렇게 동작합니다.)

로그인이 필요한 프로젝트에서는
매 테스트마다 로그인 화면을 거치는 대신 storage_state 를 저장해두고 재사용합니다.

적용 방법 (3단계)
-----------------
1. ``perform_login`` 을 실제 로그인 절차로 채운다.
   이 파일을 직접 고쳐도 되고, 프로젝트 conftest 에서 갈아끼워도 됩니다.
2. 테스트에서 ``role_page`` 를 받아 쓴다.

       def test_주문내역(role_page):
           page = role_page("user")      # 이미 로그인된 상태
           page.goto("orders")

3. 관리자 화면은 ``role_page("admin")`` 처럼 역할만 바꾸면 된다.

Evidence
--------
``role_page`` 로 만든 Page 도 기본 ``page`` fixture 와 **똑같이** 실패 시
Screenshot / Page HTML / Trace 가 남습니다. 파일 이름 뒤에 역할이 붙어서
어느 세션의 것인지 구분됩니다.

    TC010_test_admin_flow_chromium_admin.png
    TC010_test_admin_flow_chromium_admin.zip

세션 파일은 ``auth_state/`` 에 저장되고 .gitignore 에 포함되어 있습니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from utils import evidence, testmeta
from utils.config import PROJECT_ROOT, RunConfig
from utils.logger import get_logger
from utils.paths import RunPaths

logger = get_logger("auth")

AUTH_STATE_DIR = PROJECT_ROOT / "auth_state"


@pytest.fixture(scope="session")
def auth_state_dir() -> Path:
    AUTH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return AUTH_STATE_DIR


def storage_state_file(role: str, env: str) -> Path:
    """환경이 다르면 세션도 달라야 하므로 파일 이름에 환경을 넣습니다."""
    return AUTH_STATE_DIR / f"{env}_{role}.json"


def perform_login(page: Page, config: RunConfig, role: str) -> None:
    """실제 로그인 절차. 프로젝트에서 이 함수를 구현하세요.

    예시:
        account = config.account(role)
        page.goto("login")
        page.get_by_label("아이디").fill(account.username)
        page.get_by_label("비밀번호").fill(account.password)
        page.get_by_role("button", name="로그인").click()
        expect(page.get_by_role("heading", name="대시보드")).to_be_visible()
    """
    raise NotImplementedError(
        "fixtures/auth.py 의 perform_login() 을 프로젝트 로그인 절차로 구현하세요."
    )


@pytest.fixture(scope="session")
def storage_state_factory(
    browser: Browser, run_config: RunConfig, auth_state_dir: Path
) -> Callable[[str], Path]:
    """역할별 로그인 세션 파일을 만들어 두고 경로를 돌려줍니다 (세션당 1회)."""
    created: dict[str, Path] = {}

    def _factory(role: str = "user") -> Path:
        target = created.get(role) or storage_state_file(role, run_config.env)

        # 캐시에 있어도 파일이 사라졌으면 다시 만듭니다.
        # (누군가 auth_state/ 를 지웠거나 세션이 만료돼 파일을 치운 경우)
        if not target.exists():
            logger.info("[%s] 로그인 세션 생성", role)
            context = browser.new_context(base_url=run_config.base_url or None)
            page = context.new_page()
            page.set_default_timeout(run_config.default_timeout)
            try:
                # 모듈 전역을 통해 호출해야 프로젝트에서 갈아끼운 구현이 반영됩니다.
                globals()["perform_login"](page, run_config, role)
                target.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(target))
            finally:
                context.close()
        created[role] = target
        return target

    return _factory


@pytest.fixture
def role_context(
    browser: Browser,
    browser_context_args: dict,
    storage_state_factory: Callable[[str], Path],
    request: pytest.FixtureRequest,
    run_config: RunConfig,
    run_paths: RunPaths,
) -> Generator[Callable[[str], BrowserContext], None, None]:
    """역할별로 로그인된 Browser Context 를 만들어 줍니다.

    테스트가 끝나면 Evidence 를 남기고 Context 를 정리합니다.
    """
    opened: list[tuple[str, BrowserContext, bool]] = []

    def _factory(role: str = "user") -> BrowserContext:
        args = dict(browser_context_args)
        args["storage_state"] = str(storage_state_factory(role))
        context = browser.new_context(**args)
        tracing = evidence.tracing_enabled(run_config) and evidence.start_tracing(context)
        opened.append((role, context, tracing))
        return context

    yield _factory

    meta = testmeta.get_meta(request.node)
    failed = testmeta.has_failure(request.node)

    for role, context, tracing in opened:
        # Context 를 닫기 전에 Evidence 를 남겨야 합니다.
        try:
            for page in context.pages:
                evidence.capture_page_evidence(
                    page, run_paths, meta, run_config, failed, label=role
                )
        finally:
            if tracing:
                evidence.finish_tracing(context, run_paths, meta, run_config,
                                        failed, label=role)
            context.close()


@pytest.fixture
def role_page(role_context, run_config: RunConfig) -> Callable[[str], Page]:
    """역할별로 로그인된 Page 를 돌려줍니다.

    기본 ``page`` fixture 와 동일하게 timeout 이 적용되고 Evidence 도 남습니다.
    """

    def _factory(role: str = "user") -> Page:
        page = role_context(role).new_page()
        page.set_default_timeout(run_config.default_timeout)
        page.set_default_navigation_timeout(run_config.navigation_timeout)
        return page

    return _factory
