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

ICON_PASS = "✅"
ICON_FAIL = "❌"

#: 콘솔이 아이콘을 못 쓸 때 대신 넣는 글자. 뜻이 남아야 하므로 '?' 로 뭉개지 않습니다.
ICON_FALLBACKS = {ICON_PASS: "[PASS]", ICON_FAIL: "[FAIL]"}


def find_result_json(argument: str | None = None) -> Path:
    if argument:
        return Path(argument)
    if not LATEST_POINTER.exists():
        raise SystemExit("실행 결과가 없습니다. 먼저 pytest 를 실행하세요.")
    return Path(LATEST_POINTER.read_text(encoding="utf-8").strip()) / "report" / "result.json"


def to_markdown(data: dict) -> str:
    run, summary = data["run"], data["summary"]
    icon = ICON_PASS if summary["failed"] == 0 else ICON_FAIL

    # schema 1.1 부터. 옛 result.json 을 읽어도 죽지 않게 .get 을 쓴다.
    version_bits = []
    if run.get("app_version"):
        version_bits.append(f"App `{run['app_version']}`")
    if run.get("git"):
        version_bits.append(f"Automation `{run['git']['branch'] or '-'} @ {run['git']['commit']}`")

    lines = [
        f"## {icon} {run['project']} · {run['environment'].upper()} · {run['browser']}",
        "",
    ]
    if version_bits:
        lines += [" · ".join(version_bits), ""]
    lines += [
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


def encode_safe(text: str, encoding: str | None) -> str:
    """출력 스트림이 못 쓰는 글자를 바꿔 놓습니다. **쓸 수 있으면 손대지 않습니다.**

    Windows 콘솔은 기본이 cp949 라 ``✅`` 를 인코딩하지 못하고,
    ``print`` 가 ``UnicodeEncodeError`` 로 죽습니다. 이 명령은 HANDOFF 와
    README 가 검증 절차로 안내하는 것이라, 안내대로 따라한 사람이 트레이스백을
    보게 됩니다.

    아이콘은 ``[PASS]`` / ``[FAIL]`` 로 바꿉니다 — ``?`` 로 뭉개면 통과인지
    실패인지가 사라지는데, 그게 이 줄의 유일한 정보입니다. 나머지 못 쓰는
    글자만 ``?`` 가 됩니다. 한글은 cp949 로 인코딩되므로 그대로 남습니다.

    UTF-8 스트림(CI·리눅스·리다이렉트 with PYTHONIOENCODING)에서는 첫 시도가
    성공하므로 아이콘이 그대로 나갑니다. **Markdown 본문 규약은 안 바뀝니다.**
    """
    encoding = encoding or "utf-8"
    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        pass
    except LookupError:               # 인코딩 이름 자체를 모를 때
        encoding = "ascii"
    for icon, plain in ICON_FALLBACKS.items():
        text = text.replace(icon, plain)
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def main() -> None:
    path = find_result_json(sys.argv[1] if len(sys.argv) > 1 else None)
    if not path.exists():
        raise SystemExit(f"result.json 을 찾을 수 없습니다: {path}")
    markdown = to_markdown(json.loads(path.read_text(encoding="utf-8")))
    print(encode_safe(markdown, getattr(sys.stdout, "encoding", None)))


if __name__ == "__main__":
    main()
