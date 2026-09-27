"""리포트 생성 (result.json + Custom HTML + Console Summary).

pytest-html 이 만드는 pytest_report.html 은 자동화 담당자용,
여기서 만드는 report.html 은 고객사/관리자용입니다.
"""

from __future__ import annotations

import json
import re
import threading
import webbrowser
from pathlib import Path
from typing import Any

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


# ----------------------------------------------------------------------
# 실패 요약 (화면 표시용. result.json 에는 넣지 않습니다)
# ----------------------------------------------------------------------
#: Playwright 동작 이름 → 리포트에 쓸 말
_ACTION_NAMES = {
    "click": "클릭", "dblclick": "더블클릭", "fill": "입력", "type": "입력", "pressSequentially": "입력",
    "press": "키 입력", "check": "체크", "uncheck": "체크 해제", "setChecked": "체크",
    "selectOption": "선택", "hover": "마우스 올리기", "waitFor": "대기", "waitForSelector": "대기",
    "goto": "페이지 이동", "setInputFiles": "파일 올리기",
}
#: 값을 비교하는 expect → 기대값 앞에 붙일 말 (소문자로 찾음)
_VALUE_VERBS = {"have text": "", "contain text": "포함 ", "have count": "건수 ", "have value": "입력값 ",
                "have attribute": "속성 "}
#: 상태를 보는 expect → 말
_STATE_VERBS = {"be visible": "화면에 보임", "be hidden": "화면에서 사라짐", "be enabled": "사용 가능",
                "be disabled": "사용 불가", "be checked": "체크됨", "be empty": "비어 있음",
                "be attached": "화면에 있음", "be editable": "입력 가능", "be focused": "선택됨"}

_EXPECT_HEAD = re.compile(r"^(?:Locator|Page(?: title| URL)?|APIResponse) expected (?P<neg>not )?to "
                          r"(?P<verb>.+?)(?: '(?P<value>.*)')?$")
_ACTUAL = re.compile(r"(?s)^(?P<actual>.*?)(?:\nError: (?P<error>[^\n]*))?\s*Call log:")
_WAIT_MS = re.compile(r"with timeout (\d+)ms")
_WAITING_FOR = re.compile(r"waiting for (.+)")
_ACTION_TIMEOUT = re.compile(r"\.(\w+): Timeout (\d+)ms exceeded")
_REGEX_VALUE = re.compile(r"^re\.compile\('(.*)'\)$")


def summarize_failure(test: dict[str, Any]) -> dict[str, Any] | None:
    """실패를 한 줄로 요약합니다. 실패가 아니면 None.

    ``{"kind": 유형, "step": 실패한 Step 번호(없으면 None), "text": 요약}``.
    Reason 칸에 Playwright 원문(Call log, locator 내부 표현)이 그대로 나와 읽기 어려웠습니다
    (2026-09-18 리포트 검토). 원문은 그 아래 traceback 칸에 그대로 남습니다.

    유형은 **무엇이 일어났는지**만 나눕니다: 값 불일치 / 요소 없음 / 대기 시간 초과 / 조건 불충족 / 기타 오류.
    제품 결함인지 테스트 문제인지는 사람이 판단합니다.
    """
    if test.get("status") not in FAILURE_STATUSES:
        return None
    message = ((test.get("error") or {}).get("message") or "").strip()
    # 마지막으로 실패한 Step 입니다. Step 안에 Step 을 넣으면 바깥도 실패로 끝나는데 실제로 깨진 것은
    # 나중에 시작한 안쪽이고, 앞에서 잡힌(pytest.raises 등) 실패보다 뒤의 실패가 테스트를 끝냈습니다.
    step = next((s.get("index") for s in reversed(test.get("steps") or []) if s.get("status") == "failed"), None)
    kind, text = _classify_failure(message)
    return {"kind": kind, "step": step, "text": text}


def _classify_failure(message: str) -> tuple[str, str]:
    first = message.split("\n", 1)[0].strip()
    wait = _WAIT_MS.search(message)
    waited = f" ({_seconds(wait.group(1))} 대기)" if wait else ""
    locator = _WAITING_FOR.search(message)
    target = f" · {locator.group(1).strip()}" if locator else ""

    head, found_actual, rest = message.partition("\nActual value: ")
    if found_actual:                                   # expect(...) 실패
        parts = _ACTUAL.match(rest)
        actual = " ".join((parts.group("actual") if parts else rest).split())
        missing = bool(parts and parts.group("error") and "not found" in parts.group("error"))
        lines = [_without_type(line.strip()) for line in head.split("\n") if line.strip()]
        standard = _EXPECT_HEAD.match(lines[0]) if lines else None
        if standard:
            if missing:
                return "요소 없음", f"요소를 찾지 못함{target}{waited}"
            return "값 불일치", f"기대 {_expected_text(standard)} · 실제 '{actual}'{waited}"
        # expect(locator, "설명") 처럼 사람이 적은 문구는 그대로 씁니다.
        custom = lines[0] if lines else ""
        if missing:
            return "요소 없음", f"{custom} · 요소를 찾지 못함{target}{waited}"
        expected = next((line[len("Expected value: "):] for line in lines[1:]
                         if line.startswith("Expected value: ")), "")
        return "값 불일치", f"{custom}{f' · 기대 {expected}' if expected else ''} · 실제 '{actual}'{waited}"

    timeout = _ACTION_TIMEOUT.search(first)
    if "TimeoutError" in first and timeout:
        action = _ACTION_NAMES.get(timeout.group(1), timeout.group(1))
        return "대기 시간 초과", f"{action} {_seconds(timeout.group(2))} 안에 끝나지 않음{target}"
    if first.startswith("AssertionError"):
        # assert 문의 설명 문구. pytest 가 덧붙이는 assert 식 줄(둘째 줄부터)은 뺍니다.
        return "조건 불충족", _without_type(first)
    return "기타 오류", first


def _expected_text(match: re.Match) -> str:
    verb, value = match.group("verb"), match.group("value")
    if value is None:
        text = _STATE_VERBS.get(verb, verb)
    else:
        pattern = _REGEX_VALUE.match(value)
        shown = f"패턴 '{pattern.group(1)}'" if pattern else f"'{value}'"
        text = _VALUE_VERBS.get(verb.lower(), f"{verb} ") + shown
    return text + (" 아님" if match.group("neg") else "")


def _without_type(line: str) -> str:
    """'AssertionError: 문구' → '문구'. 앞이 예외 이름이 아니면 그대로 둡니다."""
    head, sep, rest = line.partition(": ")
    return rest if sep and re.fullmatch(r"[\w.]+", head) else line


def _seconds(ms: str) -> str:
    return f"{int(ms) / 1000:g}초"


def _display_step(step: dict[str, Any], fail: dict[str, Any] | None) -> dict[str, Any]:
    """Step 표시용 복사본. result.json 이 쓰는 원본에 표시용 값을 섞지 않습니다.

    API 최대 시간은 그 Step 안에서 끝난 호출로만 잽니다. 뒤 Step 에서 끝난 호출(로그인 때 시작한
    약 12초짜리 대시보드 조회)까지 넣으면 짧은 Step 이 느린 것처럼 읽힙니다 (2026-09-18 리포트 검토).
    """
    shown = dict(step)
    apis = step.get("apis") or []
    answered = [api for api in apis if api.get("status") is not None]
    done = [api["total_ms"] for api in answered if not api.get("end_step")]
    shown["api_max_ms"] = max(done) if done else None
    shown["api_carried"] = len(answered) - len(done)
    shown["api_unanswered"] = len(apis) - len(answered)
    if fail and step.get("status") == "failed" and step.get("index") == fail["step"]:
        shown["error_summary"] = fail["text"]
    return shown


def unanswered_apis(test: dict[str, Any]) -> list[dict[str, Any]]:
    """실패한 TC 에서 응답을 받지 못한 호출 (schema 1.5). 통과한 TC 는 빈 목록.

    요청한 Step 과 실패한 Step 이 다를 수 있어서 모든 Step 에서 모읍니다 (1단계 로그인 때
    보낸 대시보드 조회가 끝내 응답하지 않았고, 그동안 로딩 가림막이 2단계 메뉴 클릭을 막았습니다).
    """
    if test.get("status") not in FAILURE_STATUSES:
        return []
    return [{"step": step.get("index"), "path": api.get("path"), "total_ms": api.get("total_ms") or 0,
             "failure": api.get("failure")}
            for step in test.get("steps") or [] for api in step.get("apis") or [] if api.get("status") is None]


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
        test["fail"] = summarize_failure(test)
        test["unanswered"] = unanswered_apis(test)
        test["steps"] = [_display_step(step, test["fail"]) for step in test.get("steps") or []]

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
