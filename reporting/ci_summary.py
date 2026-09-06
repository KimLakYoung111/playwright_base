"""result.json 을 Markdown 요약으로 출력합니다.

CI(예: GitHub Actions Step Summary)나 Slack/Email 알림에 그대로 붙여 쓸 수 있습니다.

    python -m reporting.ci_summary                       # 마지막 실행
    python -m reporting.ci_summary artifacts/2026.../report/result.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from utils.config import PROJECT_ROOT

LATEST_POINTER = PROJECT_ROOT / "artifacts" / "latest_run.txt"


def find_result_json(argument: str | None = None) -> Path:
    if argument:
        return Path(argument)
    if not LATEST_POINTER.exists():
        raise SystemExit("실행 결과가 없습니다. 먼저 pytest 를 실행하세요.")
    return Path(LATEST_POINTER.read_text(encoding="utf-8").strip()) / "report" / "result.json"


def to_markdown(data: dict) -> str:
    run, summary = data["run"], data["summary"]
    icon = "✅" if summary["failed"] == 0 else "❌"

    lines = [
        f"## {icon} {run['project']} · {run['environment'].upper()} · {run['browser']}",
        "",
        "| Total | Passed | Failed | Skipped | Pass Rate | Duration |",
        "|---|---|---|---|---|---|",
        f"| {summary['total']} | {summary['passed']} | {summary['failed']} "
        f"| {summary['skipped']} | {summary['pass_rate']}% | {summary['duration']}s |",
    ]

    if data.get("categories"):
        lines += ["", "### Category", "", "| Category | Total | Passed | Failed | Pass Rate |",
                  "|---|---|---|---|---|"]
        for category in data["categories"]:
            lines.append(
                f"| {category['name']} | {category['total']} | {category['passed']} "
                f"| {category['failed']} | {category['pass_rate']}% |"
            )

    failed = [t for t in data["tests"] if t["status"] in ("failed", "error")]
    if failed:
        lines += ["", "### Failed Tests", ""]
        for test in failed:
            message = (test.get("error") or {}).get("message", "").splitlines()
            head = message[0][:150] if message else ""
            lines.append(f"- **{test['test_id']}** {test['name']} — `{head}`")

    return "\n".join(lines)


def main() -> None:
    path = find_result_json(sys.argv[1] if len(sys.argv) > 1 else None)
    if not path.exists():
        raise SystemExit(f"result.json 을 찾을 수 없습니다: {path}")
    print(to_markdown(json.loads(path.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    main()
