"""프로젝트 전역 pytest 설정.

여기서 하는 일
--------------
1. CLI 옵션(--env)과 설정 파일/.env 를 합쳐 ``RunConfig`` 를 만든다.
2. 실행마다 ``artifacts/<날짜_시각>/`` 폴더를 만들고 로그를 연결한다.
3. Browser / Context / Page 를 공통으로 준비한다 (테스트마다 Context 분리).
4. 실패하면 Screenshot / Page HTML / Trace / Log 를 자동 저장한다.
5. 결과를 모아 result.json, Custom HTML Report, Console Summary 를 만든다.
6. 업무 API 응답 시간을 Step 마다 모아 리포트에 싣는다 (config ``report.api_paths``).

테스트 코드는 위 내용을 몰라도 됩니다. ``page`` 와 Page Object 만 쓰면 됩니다.
"""

from __future__ import annotations

import dataclasses
import time
from datetime import datetime
from typing import Any, Generator
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import BrowserContext, Error, Page, Request, Response, expect

from reporting import report_generator
from reporting.result_collector import ResultCollector
from utils import evidence, runmeta, testmeta
from utils.config import SUPPORTED_ENVS, RunConfig, load_config
from utils.logger import get_logger, sensitive_filter, setup_logging, test_log_capture
from utils.paths import RunPaths, prune_old_runs, resolve_run_paths
from utils.steps import test_step  # noqa: F401  (테스트에서 conftest 경유로 쓰기 편하도록)

pytest_plugins = ["fixtures.auth"]

#: hook 사이에서 공유하는 실행 상태
_CURRENT: dict[str, Any] = {}

logger = get_logger()
api_logger = get_logger("api")

#: 테스트 본문이 끝난 시각 (아래 ``pytest_runtest_call``). 응답 없는 API 의 대기 시간을 여기까지 잽니다.
BODY_END_KEY = pytest.StashKey[float]()


# ======================================================================
# CLI 옵션
# ======================================================================
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("automation-base", "Automation Base 옵션")
    group.addoption(
        "--env",
        action="store",
        default=None,
        choices=list(SUPPORTED_ENVS),
        help="실행 환경 (기본값은 .env 의 ENV, 없으면 staging)",
    )
    group.addoption(
        "--open-report",
        action="store_true",
        default=False,
        help="실행이 끝나면 report.html 을 브라우저로 엽니다 "
             "(기본 동작. CI 나 -n 병렬처럼 자동으로 꺼지는 곳에서 강제로 켤 때 씁니다)",
    )
    group.addoption(
        "--no-open-report",
        action="store_true",
        default=False,
        help="실행이 끝나도 리포트를 열지 않습니다 (--open-report 보다 우선)",
    )
    # --browser / --headed / --base-url 은 pytest-playwright 가 이미 제공합니다.
    # --reruns 는 pytest-rerunfailures 가 제공하며 config 의 retries 값이 기본이 됩니다.


# ======================================================================
# 실행 준비
# ======================================================================
#: pytest-playwright 의 Evidence 옵션을 Base 의 모드로 옮기는 표
_TRACING_TO_MODE = {"on": "always", "off": "never", "retain-on-failure": "on-failure"}
_SCREENSHOT_TO_MODE = {"on": "always", "off": "never", "only-on-failure": "on-failure"}


def _cli_given(config: pytest.Config, flag: str) -> bool:
    """사용자가 명령줄에 그 옵션을 직접 줬는지 확인합니다.

    ``--tracing`` 처럼 기본값이 "off" 인 옵션은 값만 봐서는
    "사용자가 off 를 준 것" 과 "기본값 그대로인 것" 을 구분할 수 없습니다.
    """
    return any(arg == flag or arg.startswith(flag + "=")
               for arg in config.invocation_params.args)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    # --collect-only 는 테스트를 돌리지 않으므로 실행 폴더/리포트를 만들지 않습니다.
    collect_only = bool(getattr(config.option, "collectonly", False))
    paths = resolve_run_paths(create=not collect_only)

    browsers: list[str] = list(getattr(config.option, "browser", None) or [])
    try:
        run_config = load_config(
            env=config.getoption("--env"),
            browser=browsers[0] if browsers else None,
            headed=bool(getattr(config.option, "headed", False)),
            base_url=getattr(config.option, "base_url", None),
        )
    except ValueError as exc:
        # .env / config 값이 잘못된 경우입니다. UsageError 로 바꿔야 pytest 가
        # 내부 오류 스택 대신 이 메시지만 깔끔하게 보여줍니다.
        raise pytest.UsageError(str(exc)) from None

    # 설정값을 pytest-playwright / pytest-base-url 쪽에 넣어줍니다.
    if not browsers:
        config.option.browser = [run_config.browser]
    else:
        run_config.browser = "/".join(browsers)     # 여러 Browser 동시 실행 시 표시용
    if not getattr(config.option, "base_url", None) and run_config.base_url:
        config.option.base_url = run_config.base_url

    # Evidence 수집은 Base 가 직접 합니다 (artifacts/<run_id>/ 아래 TC 이름으로 저장).
    # pytest-playwright 가 같은 Context 에 tracing 을 또 시작하면 충돌해서
    # Base 의 Trace 가 통째로 사라집니다. 그래서 플러그인 쪽 수집은 끄고,
    # 사용자가 준 --tracing / --screenshot 값은 Base 모드로 옮겨 담습니다.
    if _cli_given(config, "--tracing"):
        run_config.trace_mode = _TRACING_TO_MODE[config.option.tracing]
    if _cli_given(config, "--screenshot"):
        run_config.screenshot_mode = _SCREENSHOT_TO_MODE[config.option.screenshot]
    for option_name in ("tracing", "screenshot"):
        if hasattr(config.option, option_name):
            setattr(config.option, option_name, "off")

    # Retry: CLI --reruns 가 있으면 그것이 우선 (0 도 "재시도 안 함" 이라는 유효한 값),
    # 없으면 설정값(기본 0)
    reruns = getattr(config.option, "reruns", None)
    if reruns is not None:
        run_config.retries = int(reruns)
    elif run_config.retries > 0 and hasattr(config.option, "reruns"):
        config.option.reruns = run_config.retries

    # 리포트 자동 열기: CLI 가 설정보다 우선합니다.
    #  - 둘 다 주면 끄는 쪽을 따릅니다 (창이 뜨는 쪽이 되돌리기 어려운 동작입니다).
    #  - -n 병렬은 커밋 게이트용 실행이라 기본으로 끕니다. 필요하면 --open-report.
    if config.getoption("--no-open-report"):
        run_config.open_report = False
    elif config.getoption("--open-report"):
        run_config.open_report = True
    elif getattr(config.option, "numprocesses", None):
        run_config.open_report = False

    expect.set_options(timeout=run_config.expect_timeout)
    config._pwbase_config = run_config          # type: ignore[attr-defined]
    config._pwbase_paths = paths                # type: ignore[attr-defined]

    if collect_only:
        return

    # pytest-html 리포트도 이번 실행 폴더 안에 만듭니다.
    if hasattr(config.option, "htmlpath") and not config.option.htmlpath:
        config.option.htmlpath = str(paths.pytest_report)
        config.option.self_contained_html = True

    # xdist 워커는 같은 run.log 에 함께 쓰므로 누가 쓴 줄인지 구분되게 합니다.
    worker_id = getattr(config, "workerinput", {}).get("workerid", "")
    setup_logging(paths.run_log, prefix=f"[{worker_id}] " if worker_id else "")
    sensitive_filter.register(*run_config.secrets())

    # 실행 메타는 컨트롤러에서만 모읍니다. pytest_configure 는 컨트롤러와 xdist
    # 워커 전부에서 돌기 때문에, 여기서 가드를 안 하면 -n 16 에 워커마다 git
    # 서브프로세스가 돌아 쓸모없이 느려지고, 워커의 command_line() 은 execnet
    # 부트스트랩 argv 를 읽어 의미 없는 값이 됩니다. 워커는 빈 dict 를 넘기고,
    # ResultCollector.to_dict() 는 빠진 키를 대부분 None 으로 채우지만
    # workers 는 self.run_meta.get("workers", 1) 이라 기본값 1 이 됩니다.
    run_meta = {} if hasattr(config, "workerinput") else {
        "git": runmeta.git_info(),
        "triggered_by": runmeta.triggered_by(run_config.show_triggered_by),
        "command": runmeta.command_line(),
        "workers": runmeta.worker_count(config),
    }
    config._pwbase_collector = ResultCollector(run_config, paths, run_meta)  # type: ignore[attr-defined]

    if not hasattr(config, "workerinput"):      # xdist 워커에서는 중복 출력 방지
        logger.info(
            "실행 준비 완료 | project=%s env=%s browser=%s headless=%s url=%s "
            "open_report=%s",
            run_config.project_name, run_config.env, run_config.browser,
            run_config.headless, run_config.base_url or "-",
            run_config.open_report,
        )
        logger.info("Artifacts: %s", paths.root)

        # 오래된 실행 폴더 정리. 워커가 동시에 같은 폴더를 지우면 경쟁이 나므로
        # 컨트롤러에서 한 번만 돌립니다. 정리 실패는 테스트 실행을 막지 않습니다.
        try:
            removed = prune_old_runs(run_config.artifacts_keep_days,
                                     run_config.artifacts_keep_min_runs)
        except OSError as exc:
            logger.warning("오래된 Artifacts 정리 실패: %s", exc)
        else:
            if removed:
                logger.info("오래된 Artifacts %d개 삭제 (보관 %d일, 최근 %d개 유지)",
                            len(removed), run_config.artifacts_keep_days,
                            run_config.artifacts_keep_min_runs)


# ======================================================================
# 설정 / 경로 fixture
# ======================================================================
@pytest.fixture(scope="session")
def run_config(pytestconfig: pytest.Config) -> RunConfig:
    """이번 실행에 적용된 설정. 테스트/Page Object 어디서든 받아 쓸 수 있습니다."""
    return pytestconfig._pwbase_config          # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def run_paths(pytestconfig: pytest.Config) -> RunPaths:
    """이번 실행의 artifacts 폴더."""
    return pytestconfig._pwbase_paths           # type: ignore[attr-defined]


# ======================================================================
# Browser / Context / Page
#   pytest-playwright 의 fixture 를 덮어써서 설정값을 주입합니다.
#   테스트마다 Context 가 새로 만들어지므로 상태가 서로 섞이지 않습니다.
# ======================================================================
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict, run_config: RunConfig) -> dict:
    args = dict(browser_type_launch_args)
    # --headed 를 주면 pytest-playwright 가 headless=False 로 넣어두므로 그쪽이 이깁니다.
    args["headless"] = args.get("headless", True) and run_config.headless
    if run_config.slow_mo:
        args.setdefault("slow_mo", run_config.slow_mo)
    # headed_window: maximized 면 창을 최대화합니다. 뷰포트를 고정하지 않으면(browser_context_args)
    # 창이 Chromium 기본 크기로 떠서 모니터보다 작게 나옵니다 (1536x960 모니터에서 창 1051x894).
    # 최대화하면 창이 뜬 모니터를 채우고 페이지 폭도 모니터 폭이 됩니다.
    if not args["headless"] and run_config.headed_window == "maximized":
        args["args"] = [*args.get("args", []), "--start-maximized"]
    return args


@pytest.fixture(scope="session")
def test_id_attribute(playwright: Any, run_config: RunConfig) -> str:
    """``get_by_test_id()`` 가 찾을 속성을 정합니다.

    사이트가 data-testid 대신 data-qa 같은 속성을 쓰면
    config 의 ``test_id_attribute`` 만 바꾸면 됩니다. 테스트 코드는 그대로입니다.
    codegen 을 쓸 때도 같은 값을 넘기세요: ``codegen --test-id-attribute=data-qa``
    """
    attribute = run_config.test_id_attribute
    if attribute != "data-testid":
        playwright.selectors.set_test_id_attribute(attribute)
        logger.info("get_by_test_id 기준 속성: %s", attribute)
    return attribute


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, run_config: RunConfig,
                         test_id_attribute: str) -> dict:
    args = dict(browser_context_args)
    if "viewport" not in args and not run_config.headless and run_config.headed_window == "maximized":
        # headed_window: maximized — 뷰포트를 고정하지 않고 창 크기를 그대로 씁니다.
        # 고정해 두면 설정값(1920x1080)이 화면에 안 들어갈 때 Chromium 이 새 탭을 열 때마다
        # 창을 다른 모니터로 옮기거나 크기를 바꿔서 창이 단계마다 움직이는 경우가 있습니다.
        # 대신 모니터가 작으면 headless 와 DOM 이 달라질 수 있어 기본값(fixed)은 고정입니다.
        args["no_viewport"] = True
    else:
        args.setdefault("viewport", run_config.viewport)   # --device 를 쓰면 그쪽 값을 유지
    args.setdefault("locale", run_config.locale)
    args.setdefault("timezone_id", run_config.timezone)
    args.setdefault("ignore_https_errors", run_config.ignore_https_errors)
    return args


@pytest.fixture
def page(page: Page, context: BrowserContext, request: pytest.FixtureRequest,
         run_config: RunConfig, run_paths: RunPaths) -> Generator[Page, None, None]:
    """설정이 적용된 Page. 실패 시 Evidence 를 자동으로 남깁니다."""
    page.set_default_timeout(run_config.default_timeout)
    page.set_default_navigation_timeout(run_config.navigation_timeout)

    # on-failure 모드에서도 일단 수집을 시작해야 실패 순간을 담을 수 있습니다.
    tracing = evidence.tracing_enabled(run_config) and evidence.start_tracing(context)
    # 실패한 탭을 고르려고 가장 최근에 요청을 보낸 탭을 기억합니다 (아래 _failed_page).
    last_request_page: list[Page] = []
    context.on("request", lambda req: _remember_request_page(last_request_page, req))

    # 실패하면 Screenshot 은 실패한 탭 한 장만, Step 이 실패한 그 순간에 찍습니다 (2026-09-18 협의).
    # 테스트가 실패 뒤에 정리(되돌리기 등)를 하면 끝난 뒤의 화면은 실패 순간이 아닙니다.
    # 열린 탭을 다 찍으면 리포트에서 어느 화면이 실패인지 가려 봐야 합니다.
    meta = testmeta.get_meta(request.node)
    step_shot: list[bool] = []
    step_url: list[str | None] = []

    def capture_failed_step() -> None:
        """``utils.steps.test_step`` 이 Step 실패 순간에 부릅니다. 리포트 '마지막 URL' 도 이 순간의 주소입니다.

        Screenshot 을 못 찍었으면(탭이 닫힘·저장 오류) 둘 다 정리 단계로 넘겨 같은 탭을 가리키게 합니다.
        """
        targets = _open_pages(page, context)
        target = _failed_page(targets, last_request_page)
        url = evidence.current_url(target)
        if evidence.should_capture(run_config.screenshot_mode, True):
            label = _tab_label(targets, target)
            shot = evidence.capture_screenshot(target, run_paths, meta, label)
            if shot is None:
                # 정리 단계의 화면은 되돌리기 등이 끝난 뒤라 실패 순간이 아닐 수 있습니다.
                logger.warning("실패 순간 Screenshot 을 저장하지 못해 테스트 정리 뒤 화면으로 대신합니다")
                return
            testmeta.record_artifact(meta, "screenshot", run_paths.relative(shot), label)
            step_shot.append(True)
        step_url.append(url)

    meta.on_step_failure = capture_failed_step

    yield page

    meta = testmeta.get_meta(request.node)
    failed = testmeta.has_failure(request.node)

    # Screenshot 저장이 어떤 이유로 실패해도 Trace 수집은 반드시 끝내야 합니다.
    # (안 그러면 Context 에 tracing 이 켜진 채 남고 Trace 파일도 사라집니다)
    try:
        # 테스트 중에 브라우저 새 탭이 열렸으면 그 탭도 남깁니다. 첫 탭은 기존 이름 그대로,
        # 나머지는 열린 순서대로 _tab2, _tab3 … 을 붙입니다. Page HTML 은 모든 탭을 남깁니다.
        # Screenshot: 실패한 Step 에서 이미 찍었으면 다시 찍지 않고, Step 밖에서 실패했으면 여기서
        # 실패한 탭 한 장만 찍습니다. 통과하면 설정대로(always 면 모든 탭) 찍습니다.
        targets = _open_pages(page, context)
        if failed:
            failed_page = _failed_page(targets, last_request_page)
            shots = [] if step_shot else [failed_page]
            # 리포트 '마지막 URL' 도 Screenshot 과 같은 화면을 가리키게 합니다 (2026-09-18 협의).
            # 통과하면 아래 capture_page_evidence 가 전처럼 첫 탭 주소를 남깁니다.
            meta.current_url = step_url[0] if step_url else evidence.current_url(failed_page)
        else:
            shots = targets
        no_screenshot = dataclasses.replace(run_config, screenshot_mode="never")
        for target in targets:
            config = run_config if any(target is s for s in shots) else no_screenshot
            evidence.capture_page_evidence(target, run_paths, meta, config, failed,
                                           label=_tab_label(targets, target))
    finally:
        # hook 은 Step 이 실패해야 쓰이므로, 통과했거나 Step 밖에서 실패했으면 남아 있습니다. TestMeta 는
        # 세션 끝까지 남아서, 지우지 않으면 이 탭·Context 를 세션 내내 붙잡습니다.
        meta.on_step_failure = None
        if tracing:
            evidence.finish_tracing(context, run_paths, meta, run_config, failed)


def _open_pages(page: Page, context: BrowserContext) -> list[Page]:
    """지금 열린 탭. 첫 탭(``page``)이 맨 앞, 나머지는 열린 순서입니다."""
    return [page, *[p for p in context.pages if p is not page]]


def _tab_label(targets: list[Page], target: Page) -> str:
    """Evidence 파일 꼬리표. 첫 탭은 없음, 나머지는 tab2, tab3 …"""
    index = next(i for i, p in enumerate(targets, start=1) if p is target)
    return "" if index == 1 else f"tab{index}"


def _remember_request_page(holder: list[Page], req: Request) -> None:
    """요청을 보낸 탭을 기억합니다. Service Worker 가 보낸 요청은 탭(frame)이 없어 예외가 나므로 건너뜁니다."""
    try:
        holder[:] = [req.frame.page]
    except Error:
        pass


def _failed_page(targets: list[Page], last_request_page: list[Page]) -> Page:
    """실패한 탭으로 볼 탭.

    Playwright 의 실패 오류에는 어느 탭에서 났는지가 없습니다. 그래서 가장 최근에 요청을 보낸 탭,
    곧 방금까지 작업하던 탭으로 봅니다. 그 탭이 이미 닫혔으면 마지막으로 열린 탭입니다.
    다른 탭이 뒤에서 혼자 요청을 보내면(주기적 조회 등) 그 탭이 골라질 수 있습니다.
    첫 탭(``page``)은 닫혀도 ``targets`` 에 남으므로 닫힌 탭은 뺍니다 (찍을 수도, 주소를 읽을 수도 없음).
    """
    open_pages = [p for p in targets if not p.is_closed()] or targets
    if last_request_page and any(last_request_page[0] is p for p in open_pages):
        return last_request_page[0]
    return open_pages[-1]


# ======================================================================
# 업무 API 응답 시간 (schema 1.3 / 1.5)
# ======================================================================
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, None, None]:
    """테스트 본문이 끝난 시각을 남깁니다 (실패해도).

    응답 없는 API 의 대기 시간을 ``context`` fixture 정리 때 재면, 그보다 먼저 도는 ``page`` fixture 의
    Evidence 저장(스크린샷·Trace·HTML) 시간까지 더해집니다.
    """
    try:
        return (yield)
    finally:
        item.stash[BODY_END_KEY] = time.monotonic()


@pytest.fixture
def context(context: BrowserContext, run_config: RunConfig,
            request: pytest.FixtureRequest) -> Generator[BrowserContext, None, None]:
    """업무 API 응답 시간을 모아 요청을 보낸 Step 기록(``apis``)에 붙입니다.

    "어느 Step 에서 부른 API 가 얼마나 걸렸는지" 를 결과 리포트에 싣습니다. 요청을 보낼 때 그 순간의
    Step 을 기억하고, 테스트가 끝날 때 시간을 잽니다 (이벤트 처리 중에 브라우저를 다시 부르지 않으려는 것).
    응답이 다음 Step 에서 끝났으면 그 번호도 남깁니다 — 로그인 때 시작한 느린 조회가 끝난 Step 으로만
    적히면 그 Step 이 느린 것처럼 보입니다.
    응답을 못 받은 요청도 싣습니다. 끝내 응답하지 않은 조회가 로딩 가림막으로 클릭을 막은 실패에서,
    응답 온 호출만 실으면 그 단서가 리포트에 없습니다.

    대상은 config ``report.api_paths`` 가 경로에 들어 있는 XHR·fetch 요청입니다. 새 탭도 같은 Context 라
    함께 기록됩니다. ``role_page`` 로 만든 Context 는 별도라 빠집니다.
    """
    if not run_config.api_paths:
        yield context
        return
    # 재시도(--reruns)는 같은 item 을 다시 돌리므로 이전 시도의 '본문 끝난 시각' 이 남아 있습니다.
    # 이번 시도가 본문 전에 실패하면 그 옛 시각으로 재서 대기 시간이 음수가 됩니다.
    if BODY_END_KEY in request.node.stash:
        del request.node.stash[BODY_END_KEY]
    calls: dict[Request, dict[str, Any]] = {}
    # 탭 번호: 열린 순서대로 1, 2, 3 … (Evidence 파일의 _tab2 와 같은 순서). 첫 탭도 page fixture 가
    # 이 Context 에서 만들므로 "page" 이벤트로 잡힙니다.
    tabs: dict[Page, int] = {}
    context.on("page", lambda new_page: tabs.setdefault(new_page, len(tabs) + 1))
    context.on("request", lambda req: _track_request(calls, tabs, req, request.node, run_config.api_paths))
    context.on("response", lambda response: _track_response(calls, response, request.node))
    context.on("requestfailed", lambda req: _track_failure(calls, req))

    yield context

    end = request.node.stash.get(BODY_END_KEY, None) or time.monotonic()   # 본문 전에 실패했으면 지금
    _attach_api_times(testmeta.get_meta(request.node), calls, end)


def _current_step(node: pytest.Item) -> dict[str, Any] | None:
    """지금 진행 중인 Step 기록. 어느 Step 인지는 테스트 항목에서 직접 꺼냅니다.

    ``testmeta.current()`` 는 ContextVar 라 Playwright 이벤트 처리 쪽에서는 비어 보입니다.
    """
    steps = testmeta.get_meta(node).steps
    return steps[-1] if steps else None


def _track_request(calls: dict[Request, dict[str, Any]], tabs: dict[Page, int],
                   req: Request, node: pytest.Item, api_paths: tuple[str, ...]) -> None:
    """업무 API 요청이면 요청을 보낸 Step·탭과 함께 기억합니다.

    Service Worker 가 보낸 요청은 탭(frame)이 없어 ``req.frame`` 에서 예외가 납니다. 그때 탭은 None 입니다.
    """
    path = urlsplit(req.url).path
    if req.resource_type not in ("xhr", "fetch"):
        return
    if not any(mark in path for mark in api_paths):
        return
    try:
        tab = tabs.get(req.frame.page)
    except Error:
        tab = None
    calls[req] = {"method": req.method, "path": path, "tab": tab, "step": _current_step(node),
                  "end_step": None, "status": None, "sent": time.monotonic(), "failed": None, "failure": None}


def _track_response(calls: dict[Request, dict[str, Any]], response: Response, node: pytest.Item) -> None:
    call = calls.get(response.request)
    if call is not None:
        call["status"] = response.status
        call["end_step"] = _current_step(node)


def _track_failure(calls: dict[Request, dict[str, Any]], req: Request) -> None:
    """응답 없이 끝난 요청의 사유를 기억합니다 (예: net::ERR_CONNECTION_RESET).

    화면 이동·탭 닫기로 브라우저가 스스로 취소한 요청(net::ERR_ABORTED)은 서버 문제가 아니라서 뺍니다.
    """
    call = calls.get(req)
    if call is None or call["status"] is not None:
        return
    failure = req.failure or "요청 실패"
    if "ERR_ABORTED" in failure:
        del calls[req]
        return
    call["failure"] = failure
    call["failed"] = time.monotonic()


def _attach_api_times(meta: testmeta.TestMeta, calls: dict[Request, dict[str, Any]], end: float) -> None:
    """모아 둔 요청의 시간을 재서, 요청을 보낸 Step 기록의 ``apis`` 에 붙입니다.

    시간은 Playwright 의 ``Request.timing`` 에서 가져옵니다. 첫 응답(``ttfb_ms``)은 첫 바이트까지,
    전체(``total_ms``)는 응답이 끝날 때까지입니다. 응답은 왔는데 아직 안 끝난 요청(-1)은 건너뜁니다.
    응답을 못 받은 요청은 ``status`` 없이 싣고, 전체 칸에 보낸 뒤 실패까지(또는 테스트 본문이 끝난 ``end``
    까지) 기다린 시간을, 실패했으면 ``failure`` 에 사유를 적습니다 (schema 1.5).
    Step 밖(첫 Step 전)의 요청과, 테스트가 리포트에서 지운 Step 의 요청은 붙일 곳이 없어 싣지 않습니다.
    기록이 실패해도 테스트 결과를 바꾸지 않도록 경고만 남깁니다.
    """
    kept = meta.steps
    for req, call in list(calls.items()):
        step = call["step"]
        if step is None or not any(s is step for s in kept):
            continue
        if call["status"] is None:
            api = {"tab": call["tab"], "method": call["method"], "path": call["path"], "status": None,
                   "ttfb_ms": None, "total_ms": round(((call["failed"] or end) - call["sent"]) * 1000)}
            if call["failure"]:
                api["failure"] = call["failure"]
            step.setdefault("apis", []).append(api)
            continue
        try:
            timing = req.timing
        except Exception as exc:                     # 닫힌 Page 의 요청 등
            api_logger.warning("API 시간 기록 실패: %s", exc)
            continue
        if timing["responseEnd"] < 0:
            continue
        api = {
            "tab": call["tab"],
            "method": call["method"],
            "path": call["path"],
            "status": call["status"],
            "ttfb_ms": round(timing["responseStart"] - timing["requestStart"]),
            "total_ms": round(timing["responseEnd"] - timing["requestStart"]),
        }
        end_step = call["end_step"]
        if end_step is not None and end_step is not step and any(s is end_step for s in kept):
            api["end_step"] = end_step["index"]
        step.setdefault("apis", []).append(api)


# ======================================================================
# 테스트 메타 / 로그 / Step
# ======================================================================
@pytest.fixture(autouse=True)
def _test_context(request: pytest.FixtureRequest) -> Generator[testmeta.TestMeta, None, None]:
    """테스트 하나의 시작/종료를 기록하고 결과를 리포트로 넘깁니다."""
    # 재시도(--reruns)는 같은 item 으로 다시 돌리므로 이전 시도의 Step/Evidence 와
    # 단계별 report 를 반드시 비워야 합니다. 안 그러면 결과가 시도마다 누적됩니다.
    request.node.stash[testmeta.PHASE_REPORTS_KEY] = {}
    meta = testmeta.reset_meta(request.node)
    testmeta.set_current(meta)
    test_log_capture.start()

    logger.info("-" * 70)
    logger.info("TEST START | %s | %s", meta.test_id, meta.title)

    yield meta

    failed = testmeta.has_failure(request.node)
    logger.info("TEST END   | %s | %s", meta.test_id, "FAILED" if failed else "PASSED")

    config = request.config
    run_config: RunConfig = config._pwbase_config       # type: ignore[attr-defined]
    paths: RunPaths = config._pwbase_paths             # type: ignore[attr-defined]

    if evidence.should_capture(run_config.log_mode, failed):
        # 재시도로 두 번 실패해도 1차 시도의 로그가 지워지지 않게
        # Screenshot/Trace 와 같은 규칙으로 파일명을 겹치지 않게 만듭니다.
        saved = test_log_capture.dump(
            evidence.unique_path(paths.logs / f"{meta.slug}.log")
        )
        if saved:
            meta.artifacts["log"] = paths.relative(saved)

    # 여러 Browser 를 동시에 돌린 경우 테스트별 실제 Browser 를 남깁니다.
    callspec = getattr(request.node, "callspec", None)
    browser_name = callspec.params.get("browser_name") if callspec else None

    # user_properties 에 실어야 xdist 병렬 실행에서도 컨트롤러까지 전달됩니다.
    request.node.user_properties.append(("meta", {
        "test_id": meta.test_id,
        "name": meta.title,
        "category": meta.category,
        "expected": meta.expected,
        "markers": meta.markers,
        "steps": meta.steps,
        "artifacts": meta.artifacts,
        "current_url": meta.current_url,
        "browser": browser_name or run_config.browser,
        "data": meta.data,
        "changes": meta.changes,
    }))
    testmeta.set_current(None)


# ======================================================================
# 결과 수집 hook
# ======================================================================
@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: Any):
    report = yield
    item.stash.setdefault(testmeta.PHASE_REPORTS_KEY, {})[report.when] = report
    return report


def pytest_sessionstart(session: pytest.Session) -> None:
    # logreport hook 은 config 를 넘겨주지 않으므로 여기서 collector 를 잡아둡니다.
    _CURRENT["collector"] = getattr(session.config, "_pwbase_collector", None)


def pytest_runtest_logreport(report: Any) -> None:
    collector: ResultCollector | None = _CURRENT.get("collector")
    if collector is not None:
        collector.handle_report(report)


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """실행이 끝나면 리포트를 만들고 요약을 출력합니다."""
    collector: ResultCollector | None = getattr(config, "_pwbase_collector", None)
    if collector is None or hasattr(config, "workerinput"):
        return

    collector.finished_at = datetime.now()
    collector.exit_status = int(exitstatus)

    try:
        report_generator.generate_all(collector)
    except Exception as exc:                       # 리포트 실패로 실행이 죽지 않도록
        terminalreporter.write_line(f"[리포트 생성 실패] {exc}", red=True)
        logger.exception("리포트 생성 실패")

    terminalreporter.write_line("")
    for line in report_generator.console_summary(collector).splitlines():
        terminalreporter.write_line(line)

    # 요약을 먼저 찍고 나서 엽니다. 브라우저가 뜨는 데 시간이 걸려도
    # 콘솔에는 경로가 이미 남아 있어야 합니다.
    run_config: RunConfig | None = getattr(config, "_pwbase_config", None)
    if run_config is not None and run_config.open_report:
        if not report_generator.open_in_browser(collector.paths.custom_report):
            terminalreporter.write_line(
                "리포트를 자동으로 열지 못했습니다. 위 Custom Report 경로를 직접 열어주세요.",
                yellow=True,
            )
