"""리포트 생성 (result.json + Custom HTML + Console Summary).

pytest-html 이 만드는 pytest_report.html 은 자동화 담당자용,
여기서 만드는 report.html 은 고객사/관리자용입니다.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from reporting.result_collector import FAILURE_STATUSES, ResultCollector
from utils.logger import get_logger

TEMPLATE_DIR = Path(__file__).parent / "templates"

logger = get_logger()


def format_duration(seconds: float) -> str:
    """872.4 -> '14m 32s'"""
    seconds = max(int(round(seconds or 0)), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_seconds(value: float) -> str:
    """2.4 -> '2.40 sec'"""
    return f"{float(value or 0):.2f} sec"


# ----------------------------------------------------------------------
# result.json
# ----------------------------------------------------------------------
def write_json(collector: ResultCollector, path: Path) -> Path:
    data = collector.to_dict()
    # Evidence 경로는 실행 폴더 기준 상대경로로 저장합니다 (폴더째 옮겨도 유효).
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Custom HTML Report
# ----------------------------------------------------------------------
def _relative_to_report(relative_path: str | None) -> str | None:
    """report/report.html 에서 본 상대경로 (report 폴더 기준이므로 ../ 를 붙임)."""
    if not relative_path:
        return None
    return f"../{relative_path}"


#: artifacts 키 -> 화면에 보여줄 이름
ARTIFACT_LABELS = {
    "screenshot": "Screenshot",
    "trace": "Trace (.zip)",
    "page_html": "Page HTML",
    "log": "Log",
}


def _artifact_links(artifacts: dict[str, str]) -> list[dict[str, str]]:
    """Evidence 목록을 링크로 만듭니다.

    한 테스트가 Page 를 여러 개 쓰면 ``screenshot_admin`` 처럼 꼬리표가 붙은 키가
    생깁니다. 그런 키도 빠짐없이 보여주고, 어느 세션 것인지 이름에 표시합니다.
    """
    links = []
    for key, relative in (artifacts or {}).items():
        kind, label = key, key
        for known, text in ARTIFACT_LABELS.items():
            if key == known:
                kind, label = known, text
                break
            if key.startswith(known + "_"):
                kind, label = known, f"{text} · {key[len(known) + 1:]}"
                break
        links.append({
            "kind": kind,
            "label": label,
            "url": _relative_to_report(relative),
            "path": relative,
        })
    return links


def render_html(collector: ResultCollector, path: Path) -> Path:
    data = collector.to_dict()

    # 템플릿에서 바로 쓸 수 있게 링크를 report/ 기준으로 바꿔둡니다.
    for test in data["tests"]:
        links = _artifact_links(test.get("artifacts") or {})
        test["artifact_links"] = links
        test["screenshot_links"] = [l for l in links if l["kind"] == "screenshot"]
        test["trace_links"] = [l for l in links if l["kind"] == "trace"]
        test["duration_text"] = format_seconds(test["duration"])
        test["is_failure"] = test["status"] in FAILURE_STATUSES

    data["failed_tests"] = [t for t in data["tests"] if t["is_failure"]]
    data["duration_text"] = format_duration(data["summary"]["duration"])
    # 여러 Browser 로 돌린 경우에만 Browser 열을 보여줍니다.
    # (한 종류만 돌렸으면 상단에 이미 나와 있어 열이 낭비입니다)
    data["multi_browser"] = len({t.get("browser") for t in data["tests"]}) > 1

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR), encoding="utf-8"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template.render(**data), encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Console Summary
# ----------------------------------------------------------------------
def console_summary(collector: ResultCollector) -> str:
    cfg = collector.config
    summary = collector.summary()
    paths = collector.paths
    line = "=" * 60

    rows = [
        line,
        "Test Execution Summary",
        line,
        "",
        f"Project : {cfg.project_name}",
        f"Env     : {cfg.env.upper()}",
        f"Browser : {cfg.browser.capitalize()} ({'headless' if cfg.headless else 'headed'})",
        f"URL     : {cfg.base_url or '-'}",
        "",
        f"Total   : {summary['total']}",
        f"Passed  : {summary['passed']}",
        f"Failed  : {summary['failed']}",
        f"Skipped : {summary['skipped']}",
    ]
    if summary["retried"]:
        rows.append(f"Retried : {summary['retried']}")
    rows += [
        "",
        f"Pass Rate : {summary['pass_rate']}%",
        f"Duration  : {format_duration(summary['duration'])}",
        "",
    ]

    failed = collector.failed_tests()
    if failed:
        rows.append("Failed Tests:")
        for test in failed[:10]:
            message = (test.get("error") or {}).get("message", "")
            rows.append(f"  - {test['test_id']} {test['name']}")
            if message:
                rows.append(f"      {message.splitlines()[0][:100]}")
        if len(failed) > 10:
            rows.append(f"  ... 외 {len(failed) - 10}건")
        rows.append("")

    rows += [
        "Custom Report:",
        f"  {paths.custom_report}",
        "",
        "Pytest Report:",
        f"  {paths.pytest_report}",
        "",
        "Evidence:",
        f"  {paths.root}",
        "",
        line,
    ]
    return "\n".join(rows)


def generate_all(collector: ResultCollector) -> dict[str, Path]:
    """실행 종료 시 conftest 가 호출합니다."""
    paths = collector.paths
    return {
        "result_json": write_json(collector, paths.result_json),
        "custom_report": render_html(collector, paths.custom_report),
    }


# ----------------------------------------------------------------------
# 리포트 열기
# ----------------------------------------------------------------------
#: 브라우저가 뜨기를 기다리는 시간(초).
#:
#: ``webbrowser.open`` 은 **돌아오지 않을 수 있습니다.** ``BROWSER`` 환경변수가
#: 가리키는 명령을 쓰면 Python 이 ``GenericBrowser`` 를 골라 ``Popen(...).wait()``
#: 를 하는데, 이건 사용자가 브라우저를 닫을 때까지 블로킹입니다 (Linux/WSL 에서
#: 흔합니다). 그대로 두면 pytest 가 요약을 다 찍어놓고 끝나지 않습니다.
#: **멈추는 것은 예외가 아니라서 try/except 로는 못 막습니다.**
OPEN_TIMEOUT_SEC = 5.0


def open_in_browser(path: Path) -> bool:
    """리포트를 기본 브라우저로 엽니다. 실제로 열었으면 True.

    **예외를 올리지도, 실행을 멈추지도 않습니다.** 테스트 결과와 아무 상관이 없는
    부가 기능이라, 띄울 브라우저가 없는 환경(헤드리스 서버, WSL, Docker)에서
    여기가 터지거나 매달려서 pytest 가 안 끝나면 안 됩니다. 열지 못하면 False 를
    주고, 부르는 쪽이 콘솔에 경로를 안내합니다.

    실제 호출은 **데몬 스레드**에서 합니다. :data:`OPEN_TIMEOUT_SEC` 안에 안
    돌아오면 "브라우저는 떴고 그 프로세스를 기다리는 중" 으로 보고 True 를 주면서
    빠져나옵니다. 데몬이라 남아 있어도 인터프리터 종료를 막지 않습니다.
    """
    if not path.exists():
        logger.warning("리포트 파일이 없어 열지 못했습니다: %s", path)
        return False

    outcome: list[bool] = []

    def _open() -> None:
        try:
            outcome.append(webbrowser.open(path.as_uri()))
        except Exception as exc:                   # webbrowser 는 OSError 외에도 냅니다
            logger.warning("리포트를 브라우저로 열지 못했습니다: %s", exc)
            outcome.append(False)

    thread = threading.Thread(target=_open, name="open-report", daemon=True)
    thread.start()
    thread.join(OPEN_TIMEOUT_SEC)

    if thread.is_alive():
        logger.info("브라우저가 떠 있는 동안 기다리지 않고 넘어갑니다: %s", path)
        return True

    opened = outcome[0] if outcome else False
    if not opened:
        logger.warning("열 수 있는 브라우저를 찾지 못했습니다: %s", path)
    return opened
