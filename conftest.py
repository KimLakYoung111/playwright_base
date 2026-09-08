"""프로젝트 전역 pytest 설정.

여기서 하는 일
--------------
1. CLI 옵션(--env)과 설정 파일/.env 를 합쳐 ``RunConfig`` 를 만든다.
2. 실행마다 ``artifacts/<날짜_시각>/`` 폴더를 만들고 로그를 연결한다.
3. Browser / Context / Page 를 공통으로 준비한다 (테스트마다 Context 분리).
4. 실패하면 Screenshot / Page HTML / Trace / Log 를 자동 저장한다.
5. 결과를 모아 result.json, Custom HTML Report, Console Summary 를 만든다.

테스트 코드는 위 내용을 몰라도 됩니다. ``page`` 와 Page Object 만 쓰면 됩니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generator

import pytest
from playwright.sync_api import BrowserContext, Page, expect

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
    # ResultCollector.to_dict() 가 빠진 키를 None 으로 채웁니다.
    run_meta = {} if hasattr(config, "workerinput") else {
        "git": runmeta.git_info(),
        "triggered_by": runmeta.triggered_by(run_config.show_triggered_by),
        "command": runmeta.command_line(),
        "workers": runmeta.worker_count(config),
    }
    config._pwbase_collector = ResultCollector(run_config, paths, run_meta)  # type: ignore[attr-defined]

    if not hasattr(config, "workerinput"):      # xdist 워커에서는 중복 출력 방지
        logger.info(
            "실행 준비 완료 | project=%s env=%s browser=%s headless=%s url=%s",
            run_config.project_name, run_config.env, run_config.browser,
            run_config.headless, run_config.base_url or "-",
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

    yield page

    meta = testmeta.get_meta(request.node)
    failed = testmeta.has_failure(request.node)

    # Screenshot 저장이 어떤 이유로 실패해도 Trace 수집은 반드시 끝내야 합니다.
    # (안 그러면 Context 에 tracing 이 켜진 채 남고 Trace 파일도 사라집니다)
    try:
        evidence.capture_page_evidence(page, run_paths, meta, run_config, failed)
    finally:
        if tracing:
            evidence.finish_tracing(context, run_paths, meta, run_config, failed)


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
        "markers": meta.markers,
        "steps": meta.steps,
        "artifacts": meta.artifacts,
        "current_url": meta.current_url,
        "browser": browser_name or run_config.browser,
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
