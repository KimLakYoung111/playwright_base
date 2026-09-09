# result.json 스키마 (schema_version 1.2)

`artifacts/<run_id>/report/result.json` 의 구조입니다.
이 파일은 **표준 인터페이스**입니다. Test Runner UI(PySide6), 사내 Dashboard,
Slack/Email 알림, Trend Report, CI 연동은 모두 HTML 이 아니라 이 JSON 을 읽습니다.

버전이 올라가도 기존 필드는 없애지 않고 추가만 합니다.

```jsonc
{
  "schema_version": "1.2",

  "run": {
    "run_id": "20260906_133000",        // artifacts 폴더 이름과 동일
    "project": "Example Automation",
    "environment": "staging",           // dev | staging | prod
    "browser": "chromium",              // 여러 개면 "chromium/firefox"
    "headless": true,
    "base_url": "https://example.com/",
    "started_at": "2026-09-06T13:30:00",
    "finished_at": "2026-09-06T13:44:32",
    "duration": 872.4,                  // 초
    "retries_configured": 0,
    "python": "3.12.7",
    "playwright": "1.62.0",
    "platform": "Windows 10",
    "artifacts_dir": "C:\\...\\artifacts\\20260906_133000",
    "exit_status": 1,                   // pytest 종료코드 (0=전부 성공)

    // --- schema 1.1 에서 추가 ---
    "app_version": "v2.14.3 (build 8821)",  // 테스트 대상 앱 버전(주입). 없으면 null
    "git": {                                // 자동 수집. .git 이 없으면 null
      "branch": "main",                     // detached HEAD 면 null
      "commit": "5d1ed8b",
      "dirty": false                        // 커밋 안 된 변경이 있으면 true.
                                            //  git 을 못 물어봤으면 null —
                                            //  false 로 적으면 "커밋과 일치" 를
                                            //  거짓으로 단정하게 됩니다.
    },
    "triggered_by": "klyhja",               // 실행자. show_triggered_by=false 면 null
    "command": "pytest -m smoke -n 4",      // 실행 명령 (비밀번호·토큰은 가려짐)
    "workers": 4                            // xdist 병렬 수. 순차면 1
  },

  "summary": {
    "total": 120,
    "passed": 115,                      // xpassed 포함
    "failed": 4,                        // error 포함
    "skipped": 1,
    "error": 0,                         // setup/teardown 단계 실패
    "xfailed": 0,
    "xpassed": 0,
    "pass_rate": 96.6,                  // passed / (passed + failed) * 100
    "duration": 872.4,
    "retried": 2                        // 재시도가 발생한 테스트 수
  },

  "categories": [                       // 업무 영역별 집계
    { "name": "Login", "total": 20, "passed": 19, "failed": 1,
      "skipped": 0, "pass_rate": 95.0 }
  ],

  "markers": [                          // marker 별 집계 (smoke/regression/...)
    { "name": "smoke", "total": 30, "passed": 30, "failed": 0,
      "skipped": 0, "pass_rate": 100.0 }
  ],

  "tests": [
    {
      "test_id": "TC001",               // @pytest.mark.tc_id, 없으면 함수명
      "name": "정상 로그인",              // @pytest.mark.title 또는 docstring 첫 줄
      "nodeid": "tests/login/test_login.py::test_login[chromium]",
      "file": "tests/login/test_login.py",
      "function": "test_login",
      "category": "Login",              // @pytest.mark.category 또는 업무 marker
      // --- schema 1.2 에서 추가 ---
      "expected": "홈으로 이동하고 우상단에 계정 이메일이 보인다",
                                        // @pytest.mark.expected. 없으면 ""
      "markers": ["smoke", "login"],
      "status": "passed",               // passed|failed|skipped|error|xfailed|xpassed
      "duration": 2.4,                  // setup+call+teardown 합계 (초)
      "started_at": "2026-09-06T13:30:02",
      "finished_at": "2026-09-06T13:30:04",
      "retries": 0,
      "browser": "chromium",
      "current_url": "https://example.com/dashboard",

      "error": {                        // 성공 시 null
        "type": "AssertionError",
        "message": "Locator expected to be visible",
        "traceback": "...",
        "phase": "call"                 // setup | call | teardown
      },

      "steps": [                        // utils.steps.test_step 으로 기록된 항목
        { "index": 1, "name": "로그인 페이지 접속",
          // --- schema 1.2 에서 추가 --- 명세서의 「기대결과 / 확인사항」 칸. 없으면 ""
          "expected": "로그인 화면이 뜬다",
          "status": "passed", "duration": 0.62, "error": null }
      ],

      "artifacts": {                    // 실행 폴더 기준 상대경로 (없으면 키 자체가 없음)
        "screenshot": "screenshots/TC001_test_login_chromium.png",
        "page_html":  "html/TC001_test_login_chromium.html",
        "trace":      "traces/TC001_test_login_chromium.zip",
        "log":        "logs/TC001_test_login_chromium.log"
      }
    }
  ]
}
```

## 활용 예시

### Test Runner UI / Dashboard

```python
import json
from pathlib import Path

run_dir = Path(Path("artifacts/latest_run.txt").read_text(encoding="utf-8"))
result = json.loads((run_dir / "report" / "result.json").read_text(encoding="utf-8"))

print(result["summary"]["pass_rate"])
for test in result["tests"]:
    if test["status"] == "failed":
        print(test["test_id"], test["error"]["message"])
        print(run_dir / test["artifacts"]["screenshot"])
```

### Trend Report 를 만들 때 쓰는 필드

| 만들려는 지표 | 사용할 필드 |
|---|---|
| 일별 Pass Rate | `run.started_at` + `summary.pass_rate` |
| 수행시간 변화 | `run.duration`, `tests[].duration` |
| 반복 실패 TC | `tests[].test_id` + `status` 누적 |
| Flaky Test | `tests[].retries > 0` |
| Browser 별 성공률 | `tests[].browser` + `status` |
| 환경별 성공률 | `run.environment` + `summary` |
| Category 별 성공률 | `categories[]` |
| 앱 버전별 성공률 | `run.app_version` + `summary` |
| 커밋별 회귀 추적 | `run.git.commit` + `summary.pass_rate` |

여러 실행의 `result.json` 을 DB 나 파일에 쌓기만 하면 위 지표를 모두 만들 수 있습니다.
