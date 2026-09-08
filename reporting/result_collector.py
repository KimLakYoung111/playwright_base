"""pytest 실행 결과 수집.

pytest 의 report 객체를 받아 result.json / Custom HTML Report 가 쓸
표준 구조로 정리합니다. 스키마는 reporting/result_schema.md 참고.

xdist(-n) 로 병렬 실행해도 동작합니다. 워커에서 만든 정보는 report 의
``user_properties`` 에 실려 컨트롤러로 전달되고, 리포트는 컨트롤러에서만 만듭니다.
"""

from __future__ import annotations

import platform
from datetime import datetime
from typing import Any

from utils.logger import mask_secrets

SCHEMA_VERSION = "1.1"

#: 상태값 (result.json 의 tests[].status)
PASSED, FAILED, SKIPPED, ERROR = "passed", "failed", "skipped", "error"
XFAILED, XPASSED = "xfailed", "xpassed"

#: 리포트에서 "실패"로 취급하는 상태
FAILURE_STATUSES = (FAILED, ERROR)


def _playwright_version() -> str:
    try:
        from importlib.metadata import version

        return version("playwright")
    except Exception:
        return "unknown"


def _crash_message(report: Any) -> str:
    """긴 traceback 대신 한 줄 요약을 뽑습니다."""
    crash = getattr(getattr(report, "longrepr", None), "reprcrash", None)
    if crash is not None and getattr(crash, "message", None):
        return str(crash.message).strip()
    text = (getattr(report, "longreprtext", "") or "").strip()
    if not text:
        return ""
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _error_type(message: str) -> str:
    if not message:
        return ""
    head = message.split(":", 1)[0].strip()
    return head if head and " " not in head else message.split("\n")[0][:60]


class ResultCollector:
    """실행 중 결과를 모아두는 객체. conftest 가 하나만 만들어 씁니다."""

    def __init__(self, run_config: Any, run_paths: Any,
                 run_meta: dict[str, Any] | None = None) -> None:
        self.config = run_config
        self.paths = run_paths
        #: conftest 가 실행 시작 때 한 번 모아 넘기는 실행 메타 (git/실행자/명령줄/병렬 수).
        #: 못 모았으면 빈 dict 이고, to_dict() 가 빠진 키를 None 으로 채웁니다.
        self.run_meta = run_meta or {}
        self.started_at = datetime.now()
        self.finished_at: datetime | None = None
        self._records: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self.exit_status: int | None = None

    # ------------------------------------------------------------------
    # 수집
    # ------------------------------------------------------------------
    def _record(self, report: Any) -> dict[str, Any]:
        nodeid = report.nodeid
        if nodeid not in self._records:
            self._order.append(nodeid)
            self._records[nodeid] = {
                "test_id": nodeid.split("::")[-1].split("[")[0],
                "name": nodeid.split("::")[-1],
                "nodeid": nodeid,
                "file": nodeid.split("::")[0],
                "function": nodeid.split("::")[-1].split("[")[0],
                "category": "Uncategorized",
                "markers": [],
                "status": PASSED,
                "duration": 0.0,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "retries": 0,
                "error": None,
                "current_url": None,
                "browser": self.config.browser,
                "steps": [],
                "artifacts": {},
            }
        return self._records[nodeid]

    def handle_report(self, report: Any) -> None:
        """pytest_runtest_logreport 에서 호출됩니다."""
        record = self._record(report)

        # pytest-rerunfailures 재시도: 이전 시도는 버리고 횟수만 남깁니다.
        if report.outcome == "rerun":
            record["retries"] += 1
            record["status"] = PASSED
            record["error"] = None
            record["steps"] = []
            record["artifacts"] = {}
            record["duration"] = 0.0
            return

        record["duration"] = round(record["duration"] + getattr(report, "duration", 0.0), 3)

        if report.when == "setup":
            if report.failed:
                record["status"] = ERROR
                self._attach_error(record, report)
            elif report.skipped:
                record["status"] = SKIPPED
                self._attach_skip_reason(record, report)

        elif report.when == "call":
            if hasattr(report, "wasxfail"):
                record["status"] = XPASSED if report.passed else XFAILED
                if report.failed:
                    self._attach_error(record, report)
            elif report.failed:
                record["status"] = FAILED
                self._attach_error(record, report)
            elif report.skipped:
                record["status"] = SKIPPED
                self._attach_skip_reason(record, report)

        elif report.when == "teardown":
            self._merge_user_properties(record, report)
            if report.failed and record["status"] == PASSED:
                record["status"] = ERROR
                self._attach_error(record, report)
            record["finished_at"] = datetime.now().isoformat(timespec="seconds")

    def _attach_error(self, record: dict[str, Any], report: Any) -> None:
        # 에러 메시지와 traceback 에는 응답 본문·입력값이 그대로 들어갑니다.
        # 이 값은 고객사에 나가는 report.html 과 result.json 에 실리므로
        # 로그와 똑같은 규칙으로 민감정보를 가려야 합니다.
        message = mask_secrets(_crash_message(report))
        record["error"] = {
            "type": _error_type(message),
            "message": message,
            "traceback": mask_secrets((getattr(report, "longreprtext", "") or ""))[:20000],
            "phase": report.when,
        }

    def _attach_skip_reason(self, record: dict[str, Any], report: Any) -> None:
        reason = ""
        longrepr = getattr(report, "longrepr", None)
        if isinstance(longrepr, tuple) and len(longrepr) == 3:
            reason = mask_secrets(str(longrepr[2]))
        record["error"] = {"type": "Skipped", "message": reason, "traceback": "", "phase": report.when}

    def _merge_user_properties(self, record: dict[str, Any], report: Any) -> None:
        """conftest 의 fixture 가 실어 보낸 메타/Step/Evidence 를 반영합니다."""
        for key, value in getattr(report, "user_properties", []) or []:
            if key != "meta" or not isinstance(value, dict):
                continue
            for field in ("test_id", "name", "category", "markers", "steps",
                          "artifacts", "current_url", "browser"):
                if value.get(field) not in (None, "", [], {}):
                    record[field] = value[field]

        # Step 의 에러 문자열과 URL 에도 민감정보가 섞일 수 있습니다.
        record["current_url"] = mask_secrets(record.get("current_url") or "") or None
        for step in record.get("steps") or []:
            if step.get("error"):
                step["error"] = mask_secrets(step["error"])

    # ------------------------------------------------------------------
    # 집계
    # ------------------------------------------------------------------
    @property
    def tests(self) -> list[dict[str, Any]]:
        return [self._records[nodeid] for nodeid in self._order]

    def summary(self) -> dict[str, Any]:
        tests = self.tests
        counts = {PASSED: 0, FAILED: 0, SKIPPED: 0, ERROR: 0, XFAILED: 0, XPASSED: 0}
        for test in tests:
            counts[test["status"]] = counts.get(test["status"], 0) + 1

        total = len(tests)
        # xpassed 는 통과로, xfailed 는 예상된 실패라 통과율 분모에서 제외합니다.
        passed = counts[PASSED] + counts[XPASSED]
        failed = counts[FAILED] + counts[ERROR]
        denominator = passed + failed
        pass_rate = round(passed / denominator * 100, 1) if denominator else 0.0

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": counts[SKIPPED],
            "error": counts[ERROR],
            "xfailed": counts[XFAILED],
            "xpassed": counts[XPASSED],
            "pass_rate": pass_rate,
            "duration": round(self.duration, 2),
            "retried": sum(1 for t in tests if t["retries"] > 0),
        }

    def _group(self, key: str) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, int]] = {}
        for test in self.tests:
            names = test[key] if isinstance(test[key], list) else [test[key]]
            for name in names or ["Uncategorized"]:
                bucket = groups.setdefault(
                    name, {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
                )
                bucket["total"] += 1
                if test["status"] in (PASSED, XPASSED):
                    bucket["passed"] += 1
                elif test["status"] in FAILURE_STATUSES:
                    bucket["failed"] += 1
                else:
                    bucket["skipped"] += 1

        result = []
        for name, bucket in sorted(groups.items()):
            done = bucket["passed"] + bucket["failed"]
            result.append({
                "name": name,
                **bucket,
                "pass_rate": round(bucket["passed"] / done * 100, 1) if done else 0.0,
            })
        return result

    def categories(self) -> list[dict[str, Any]]:
        return self._group("category")

    def markers(self) -> list[dict[str, Any]]:
        return self._group("markers")

    def failed_tests(self) -> list[dict[str, Any]]:
        return [t for t in self.tests if t["status"] in FAILURE_STATUSES]

    @property
    def duration(self) -> float:
        end = self.finished_at or datetime.now()
        return max((end - self.started_at).total_seconds(), 0.0)

    # ------------------------------------------------------------------
    # 출력용 구조
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        cfg = self.config
        return {
            "schema_version": SCHEMA_VERSION,
            "run": {
                "run_id": self.paths.run_id,
                "project": cfg.project_name,
                "environment": cfg.env,
                "browser": cfg.browser,
                "headless": cfg.headless,
                "base_url": cfg.base_url,
                "started_at": self.started_at.isoformat(timespec="seconds"),
                "finished_at": (self.finished_at or datetime.now()).isoformat(timespec="seconds"),
                "duration": round(self.duration, 2),
                "retries_configured": cfg.retries,
                "python": platform.python_version(),
                "playwright": _playwright_version(),
                "platform": f"{platform.system()} {platform.release()}",
                "artifacts_dir": str(self.paths.root),
                "exit_status": self.exit_status,
                # --- schema 1.1 에서 추가된 실행 메타 ---
                # 값을 못 구했어도 키는 남깁니다. 소비자가 KeyError 를 만나지 않게.
                "app_version": cfg.app_version or None,
                "git": self.run_meta.get("git"),
                "triggered_by": self.run_meta.get("triggered_by"),
                "command": self.run_meta.get("command"),
                "workers": self.run_meta.get("workers", 1),
            },
            "summary": self.summary(),
            "categories": self.categories(),
            "markers": self.markers(),
            # 복사본을 넘깁니다. 리포트 렌더러가 표시용 필드를 덧붙여도
            # result.json 스키마가 오염되지 않습니다.
            "tests": [dict(test) for test in self.tests],
        }
