# HANDOFF: 3회차 잔여 작업 처리 (artifacts 자동 정리 + Claude 협업 문서)

> 최신 세션이 맨 위입니다. 아래로 갈수록 과거 기록입니다.

---

## Goal

이 저장소는 여러 고객사의 Playwright 자동화에 공통으로 쓰는 **껍데기(템플릿) 전용**입니다.
실제 자동화는 이 Base 를 복사해 별도 저장소에서 합니다 (3회차 확정, 유효).
이번 회차는 3회차 핸드오프의 「Remaining Work」 7개를 실제로 처리했습니다.

## Current Status: Completed (3회차 잔여 작업 기준)

3회차 「Remaining Work」 7개를 전부 처리하고 `PR #4` 로 `main` 에 머지했습니다
(rebase 머지 — `feat` 과 `docs` 의 설계 근거를 따로 남기기 위해 이번만 squash 를 쓰지
않았습니다). 머지 후 게이트 3종과 GitHub Actions 를 실제로 돌려 전부 통과를 확인했습니다
(값은 아래 Verification Commands).

**다음 세션의 첫 할 일은 아래 「Remaining Work」 1번(데모 프로젝트 이전)** 이고,
새로 시작할 만한 것은 3번(Template 경로 실증)입니다.

### What Was Done

3회차 「Remaining Work」 대조표입니다.

| # | 항목 | 결과 | 검증 |
|---|---|---|---|
| 1 | 가이드 「Claude와 함께 쓰기」 절 | **완료** — `docs/AUTOMATION_GUIDE.md` **9장 신설**. 기존 1~8장 번호를 그대로 둬 외부 링크 보존 | 링크 61개 기계 검증, 깨짐 0 |
| 2 | `CLAUDE.md` 생성 | **완료** — 규칙만 담고 설명은 가이드/README 로 링크 | 링크 검증 통과 |
| 3 | Flaky 표 뷰포트 행 | **완료** — 5장 표에 추가, 9장 실패 사례로 연결 | 상동 |
| 4 | `.gitignore` 에 `.playwright-mcp/` | **완료** (+ `.claude/worktrees/` 도 추가) | — |
| 5 | artifacts 자동 정리 | **완료** — `utils/paths.py::prune_old_runs` + `config` 의 `keep_days`/`keep_min_runs` | 단위 테스트 8개 + 실제 폴더 심어서 e2e 확인 |
| 6 | Template repository 켜기 | **완료** — 사용자 승인 후 실행. `isTemplate: true` | `gh repo view` 로 확인 |
| 7 | 공개범위 | **조치 없음** — "Public 유지" 로 3회차에 이미 결론 | `visibility: PUBLIC` |

추가로 `/code-review high` 를 돌려 **지적 4건을 전부 반영**했고, 지적마다 회귀 테스트를
붙였습니다 (단위 테스트 5개 → 8개). 상세는 PR #4 본문에 있습니다.

### What Was NOT Done

- **macOS / 모바일 뷰포트 / SNS 로그인** — 여전히 미검증 (3회차부터 이월).
- **Template 경로(`Use this template`)로 저장소를 만들어본 적이 없습니다.** 설정만 켰고,
  3회차 데모는 폴더 복사로 했습니다.
- **`.playwright-mcp/` 가 실제로 생기는 것을 이번 회차에는 못 봤습니다.** MCP 를 쓰지
  않았기 때문입니다. `.gitignore` 규칙은 넣어뒀지만 실물 검증은 다음으로 넘어갑니다.

## What Worked

**병렬 에이전트를 파일 경계로 나눈 것.** 문서(사람)/코드(worktree 격리 에이전트)로
쪼개 동시에 진행했고 충돌이 없었습니다. 결정적이었던 것은 에이전트 프롬프트에
**"README.md 와 docs/ 는 절대 건드리지 마세요. 다른 작업자가 동시에 편집 중입니다"** 를
명시한 것입니다. 대신 에이전트가 만든 기능이 문서화되지 않은 채로 남으므로
**메인에서 문서 마감을 반드시 이어서** 해야 합니다 (README 4장·`.env.example`·구조 트리).

**`/code-review` 가 실제 버그를 잡았습니다.** `keep_min_runs` 오프바이원(medium)은
재현 스크립트로 확인했습니다 — `keep_min_runs=5` 인데 이전 실행이 4개만 남았습니다.
원인은 conftest 가 실행 폴더를 만든 **뒤에** 정리를 부르기 때문입니다.
1회차에 이어 두 번째로 값을 했습니다.

**문서 링크 기계 검증.** 앵커까지 확인하는 스크립트를 쓰면 손으로 못 잡는 것을 잡습니다.
GitHub 슬러그 규칙: 제목을 strip → `[^\w\s-]` 제거 → 소문자 → **공백 1개당 하이픈 1개**
(연속 공백을 합치지 않고, 뒤쪽 공백도 strip 하지 않음).

## What Didn't Work / Gotchas

**① 한글 콘솔 출력이 깨져 판정을 두 번 틀렸습니다.** Windows 콘솔이 cp949 라
Python stdout 의 한글이 깨집니다. `PYTHONIOENCODING=utf-8` 로 **파일에 쓰고 Read 로 읽는**
방식이 유일하게 신뢰할 수 있었습니다. 커밋 메시지도 heredoc 대신 파일에 쓰고
`git commit -F <파일>` 로 넣었습니다.

**② 앵커 슬러그 계산에서 `\u1100-\uD7AF` 범위를 쓰면 안 됩니다.** em-dash(U+2014)가
이 범위 안에 들어가 문장부호가 살아남습니다. Python 3 의 `\w` 가 이미 한글을 포함하므로
`[^\w\s-]` 만으로 충분합니다. 이걸로 "링크 4개 깨짐" 오탐이 났습니다.

**③ `caplog` 가 이 저장소 로거를 못 받습니다.** `utils/logger.py:129` 가
`automation` 로거의 `propagate = False` 를 켭니다. caplog 는 루트 핸들러라 아무것도
안 잡힙니다. 테스트에서 `monkeypatch.setattr(logging.getLogger("automation"), "propagate", True)`
로 그 테스트 동안만 되돌려야 합니다.

**④ worktree 격리 에이전트는 저장소 안에 `.claude/worktrees/` 를 만듭니다.**
저장소 전체 복사본이라 커밋되면 사고입니다. `.gitignore` 에 넣었고, 작업 후
`git worktree remove --force` + `git branch -D` 로 정리해야 남지 않습니다.

**⑤ 에이전트 보고를 그대로 믿지 마세요.** 이번 에이전트 보고는 정확했지만,
`git diff` 를 직접 읽고 `diff -q` 로 원본과 대조한 뒤에야 확인이 됐습니다.
그리고 그 정확한 보고에도 `/code-review` 는 버그를 찾아냈습니다.

**⑥ `gh pr merge --delete-branch` 는 로컬 원격추적 ref 를 안 지웁니다.**
원격 브랜치는 지워지는데 `git branch -a` 에는 `remotes/origin/<브랜치>` 가 남아
"브랜치 정리 실패" 로 보입니다. `git fetch --prune` 을 한 번 더 돌려야 사라집니다.
3회차 목표가 "브랜치를 main 하나로 정리" 였으니 다음에도 여기서 헷갈리기 쉽습니다.

## 이번 회차 결정 (되돌리는 법 포함)

**① `pytest` 가 `base_unit` 을 제외합니다.** `tests/unit/` 은 Base 프레임워크 자체
회귀 테스트라 고객사용 리포트에 업무 테스트와 섞이면 안 된다고 판단했습니다
(`failure_demo` 와 같은 방식). 대신 게이트가 3종으로 늘었습니다.
→ 원복: `pytest.ini` 의 `addopts` 에서 `and not base_unit` 만 제거.

**② `keep_days` 기본값 14.** 기존 프로젝트에 이 Base 를 반영하면 **다음 실행에서
14일 지난 artifacts 폴더가 지워집니다.** 최근 5개는 나이와 무관하게 보호됩니다.
→ 끄기: `config/default.yaml` 의 `artifacts.keep_days: 0`.

## Remaining Work

1. **데모 프로젝트를 임시 폴더에서 옮기기** — 4회차 종료 시점에 아직 살아 있는 것을
   확인했습니다.
   `%LOCALAPPDATA%\Temp\claude\C--Users-klyhj-dev-e2etest-playwright-base\0a7cd08f-6455-4d87-89f1-028ede4d8f49\scratchpad\qmeet_demo`
   → `C:\Users\klyhj\dev\e2etest\qmeet\` 등으로. **이 저장소에 넣으면 안 됩니다**
   (껍데기 전용 원칙 위반). 세션 임시 폴더라 언제든 사라질 수 있습니다.
2. **`.playwright-mcp/` 실제 발생 확인** — MCP 로 Locator 를 조사할 때 `.gitignore` 가
   제대로 먹는지 한 번 보면 됩니다. 별도 작업이 아니라 다음 조사에 끼워서 하세요.
3. **Template 경로로 첫 고객사 프로젝트 실증** — 남은 것 중 **유일하게 새 정보를 주는
   작업**입니다. GitHub 에서 "Use this template" 로 새 저장소를 만들어
   [README 18장](README.md) 절차를 그대로 따라가 보고, 폴더 복사(3회차 방식)와
   달라지는 지점이 있는지 확인하세요. 코드를 얹은 뒤에는 `/code-review` 를 붙입니다.
4. **macOS / 모바일 뷰포트 / SNS 로그인 검증** (3회차부터 이월, 우선순위 낮음).

## Key File Paths

이번 회차에 새로 생기거나 바뀐 것만 적습니다. 나머지는 [README 5장](README.md) 참고.

| role | path |
|---|---|
| **Claude 규칙 (신규, 껍데기와 함께 복사됨)** | `CLAUDE.md` |
| Claude 협업 가이드 (신규 9장) | `docs/AUTOMATION_GUIDE.md` |
| artifacts 정리 로직 | `utils/paths.py::prune_old_runs` |
| 정리 호출부 (컨트롤러 1회) | `conftest.py` 의 `pytest_configure` 끝 |
| 정리 설정 | `config/default.yaml` 의 `artifacts:` 블록 |
| 정리 회귀 테스트 (8개) | `tests/unit/test_paths_retention.py` |
| `base_unit` marker 정의·제외 | `pytest.ini` |

## Verification Commands

아래 기대값은 **머지된 `main` 에서 실제로 돌려 확인한 값**입니다 (예측 아님).

```bash
# 게이트 4종
pytest                    # 30 passed                           ← deselected 수는 기준 아님(계속 변함)
pytest -m failure_demo    # 3 failed, 1 skipped        (11.1s)  ← 의도된 실패
pytest -m base_unit       # 36 passed                           ← Base 자체 회귀
pytest -n 2               # 30 passed                           ← 머지 전 확인

# 30 이 아니면 예제 사이트(demo.playwright.dev/todomvc) 변경을 먼저 의심할 것
# base_unit 수는 Base 자체 테스트가 늘면 같이 늘어난다. 갑자기 줄었으면 의심할 것
# deselected = failure_demo + base_unit 몫이라 base_unit 테스트를 추가할 때마다 바뀐다. 고정값으로 박지 말 것

git status -sb            # 변경 없음
gh pr list                # 열린 PR 없음
gh run list --branch main --limit 1          # 최신 커밋 CI: success 확인함
gh repo view --json isTemplate,visibility   # {"isTemplate":true,"visibility":"PUBLIC"}
```

한글 판정이 필요한 검사는 `PYTHONIOENCODING=utf-8` 를 주고 **파일로 받아서** 읽으세요
(Gotcha ①).

## Uncommitted Changes

**없습니다.** `git status` clean, `main` 은 `origin/main` 과 동기화돼 있고 열린 PR 도
없습니다. 브랜치는 `main` 하나입니다.

이번 회차가 `main` 에 남긴 **실질 변경**은 둘입니다 (PR #4, rebase 머지라 그대로
올라갔습니다). 그 뒤에 붙은 `docs: 핸드오프...` 커밋들은 이 문서를 갱신한 것입니다.

```
docs: Claude 협업 가이드(9장)와 CLAUDE.md 규칙 추가
feat: 오래된 artifacts 실행 폴더 자동 정리
```

> 핸드오프 갱신 커밋을 이 목록에 하나씩 적지 마세요. 적는 순간 그것을 적는 커밋이
> 또 생겨서 끝나지 않습니다 (3회차에 커밋 해시로 같은 일을 겪었습니다).

> 이 문서에 `main` 의 커밋 해시를 적지 않습니다. 해시를 적으면 그것을 고치는
> 커밋이 다시 해시를 바꿔 영원히 어긋납니다(3회차에 실제로 겪음).
> 위치 확인은 `git log --oneline -5` 로 커밋 제목을 보세요.

자격증명 위치 (값은 기록하지 않음): 데모 프로젝트의 `.env` (gitignored).
**이 저장소는 Public 이므로 고객사 URL·계정을 절대 커밋하지 마세요.**

---

## Previous Handoff (archived)

1~3회차 기록 중 아직 유효한 부분만 남깁니다. 3회차 전문은 PR #3, 1·2회차는 PR #1 참고.

### 3회차 실측 데이터 (재측정 불필요)

측정 환경: i5-13400 (10코어/16스레드), RAM 31.8 GB. 대상은 TodoMVC.

| 실행 | 브라우저 최대 RAM | python 증가분 | 합계 | 소요 |
|---|---|---|---|---|
| 순차 | 248 MB | ~130 MB | ~380 MB | 14.1s |
| `-n 2` | 499 MB | ~200 MB | ~700 MB | 9.4s (1.50배) |
| `-n 4` | 988 MB | 331 MB | ~1.3 GB | 7.4s (1.91배) |

```
필요 RAM ≈ 400 MB + 310 MB × 병렬 worker 수
실무 사이트(무거운 SPA)는 2~3배로 보정할 것
권장 -n 값 = 물리코어의 절반 (그 이상은 CPU 경합으로 Flaky 증가)
```

최소 4코어/8GB/5GB여유, 권장 8코어+/16GB+/20GB+.
디스크: chromium 만 700 MB / 3브라우저 1.2 GB / 파이썬 패키지 150 MB.

**`playwright install` 은 옛 브라우저 버전을 지우지 않습니다.** 이 PC 에 chromium
6개 버전이 쌓여 4.88 GB 였습니다. `playwright uninstall --all && playwright install chromium`
으로 약 4.2 GB 회수됩니다.

### 3회차 결정 (유효)

**리포트 스크린샷은 상대경로 참조를 유지합니다** (base64 임베드하지 않음).
Trace·Page HTML 은 어차피 임베드 대상이 아니라 이미지를 넣어도 폴더 단위 전달이
필요하고, 실패가 많을수록 리포트가 무거워지는데 그때가 제일 빨리 열어봐야 할 때입니다.
→ **운영 규칙: 리포트는 `artifacts/<실행시각>/` 폴더째 전달합니다.**

**리포트 기능을 텍스트 추출로 판정하지 마세요.** `report.html` 에서 태그를 걷어내고
읽다가 "썸네일이 없다" 고 잘못 판단한 적이 있습니다. 실제로는 `.thumbs` 블록과
라이트박스가 이미 있습니다. 브라우저로 열거나 태그를 직접 세세요.

### 발견한 결함 의심 (데모 대상 사이트, 개발팀 확인 필요)

로그인 실패 피드백이 케이스마다 다릅니다. 형식 오류 이메일과 틀린 비밀번호는 각각
문구가 뜨는데, **형식은 맞지만 없는 계정이면 아무것도 뜨지 않습니다.**
의도된 account enumeration 방지라면 모호한 문구라도 떠야 합니다. 현재는 사용자가
"버튼이 안 먹는다" 로 인식합니다. **테스트로 만들지 않았습니다** — 버그라면
테스트가 버그를 정답으로 고정시키기 때문입니다.

### 여전히 유효한 설계 결정 (1·2회차)

- **pytest-playwright 를 재발명하지 않고 fixture 만 덮어썼다.** `--browser` `--headed`
  `--base-url` 은 플러그인 것을 쓰고 `--env` 만 추가.
- **Evidence 는 Base 가 직접 관리한다.** 플러그인의 `--tracing`/`--screenshot` 은 끈다.
  같은 Context 에 tracing 을 두 번 시작하면 Trace 가 통째로 사라진다.
- **테스트 함수명은 영문, 설명은 docstring 한글.** docstring 이 리포트 제목이 된다.
- **`result.json` 이 외부 연동의 표준 인터페이스.** 스키마: `reporting/result_schema.md`.
- **tracing 기본값 `on-failure` 유지.** 통과 테스트당 0.1~0.2초를 더 쓰지만
  재현 안 되는 실패는 Trace 없이 분석 불가.
- **`requirements.txt`(범위) + `requirements.lock`(고정) 두 벌.** CI 는 lock 사용.
- `fixtures/auth.py::perform_login` 은 `NotImplementedError`. **프로젝트가 채우는 자리**(의도).

### 검증 완료 환경 (재검증 불필요)

Windows 10 (3.12.10 / 3.14.2), Linux Debian `python:3.12-slim` (3.12.12) 전부 통과.
GitHub Actions ubuntu-latest (3.12.14) smoke 4 passed. **macOS 는 미검증.**

### 추천 스킬 (1회차부터 유효, 이번 회차에 재확인)

- **`/code-review`** — Base 본체를 고칠 때 반드시. 1회차 15건(보안 2건), 4회차 4건
  (재현 가능한 medium 1건 포함)을 잡았습니다.
- **`superpowers:verification-before-completion`** — "통과했다" 를 말하기 전에 실제 실행
  결과를 붙이는 습관. **Claude 는 요약하지 말고 터미널 출력을 그대로 붙입니다**
  (이 규칙은 이제 `CLAUDE.md` 와 가이드 9장에 박혀 있습니다).
