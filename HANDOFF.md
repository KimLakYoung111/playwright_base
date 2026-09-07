# HANDOFF: Base 브랜치 정리 + "Claude가 TC부터 코드까지 쓸 수 있는가" 실증

> 최신 세션이 맨 위입니다. 아래로 갈수록 과거 기록입니다.

---

## Goal

이 저장소는 여러 고객사의 Playwright 자동화에 공통으로 쓰는 **껍데기(템플릿) 전용**입니다.
실제 자동화 프로젝트는 이 Base 를 복사해 **별도 저장소에서** 진행합니다 (사용자 확정, 3회차).
이번 회차 목표는 ① 흩어진 브랜치를 `main` 하나로 정리하고 ② 이 Base 위에서
**Claude Code 가 codegen 없이 TC 정의 이후를 끝까지 수행할 수 있는지** 실측으로 확인하는 것이었습니다.

## Current Status: Partially Complete

브랜치 정리와 실증은 **완료**. 문서화 3건과 결정 2건이 남아 있습니다.
**다음 세션의 첫 할 일: 아래 「Remaining Work」 1번(「Claude와 함께 쓰기」 절 작성).**
근거 데이터는 이 문서에 전부 들어 있어 재조사가 필요 없습니다.

### What Was Done

| 항목 | 결과 | 검증 |
|---|---|---|
| PR #1(HANDOFF) · #2(가이드) 를 `main` 에 squash 머지, 브랜치 삭제 | `main` = `7f18d3f` | 머지 후 게이트 재실행 |
| 합쳐진 `main` 게이트 재검증 | `pytest` **30 passed, 4 deselected** (22.0s) / `pytest -m failure_demo` **3 failed, 1 skipped** / Evidence 16파일 | 실행 출력 확인 |
| PC 사양 요구치 실측 | 아래 「실측 데이터」 참고 | 3회 반복 측정 |
| **Claude 단독 자동화 실증** (별도 데모 프로젝트) | TC 3종 6케이스 작성 → **6 passed** / 병렬 `-n 2` 6 passed / 연속 3회 6·6·6 | 게이트 3종 + 체크리스트 6항목 |
| README 18장 "새 고객사 프로젝트 시작" 절차 검증 | Base 복사 → 설정 → 테스트 작성까지 문제없이 동작 | 데모 프로젝트로 실행 |

> `main` 저장소 파일은 **머지 외에 한 줄도 수정하지 않았습니다.** (`git status` clean)
> 실증은 전부 스크래치패드의 별도 복사본에서 진행했습니다.

### What Was NOT Done

- **`docs/AUTOMATION_GUIDE.md` 의 「Claude와 함께 쓰기」 절** — 근거 데이터는 다 모았으나 미작성.
- **`CLAUDE.md`** — 미생성. 껍데기가 복사될 때 같이 따라가므로 가치가 큰 항목.
- **Template repository 설정** — `gh repo edit --template` 미실행 (사용자 승인 전).
- **artifacts 자동 정리** — Base 에 기능 없음. 최소 사양 PC 의 유일한 실질 제약.
- **macOS / 모바일 뷰포트 / SNS 로그인** — 미검증.

## What Worked

**Playwright MCP 로 codegen 을 대체할 수 있습니다 (핵심 발견).**
`browser_navigate` → `browser_snapshot`(접근성 트리) → `browser_type`/`click`(상호작용 후 구조 확인)
→ `browser_evaluate`(testid 등 접근성 트리에 없는 속성) 순으로 Locator 를 확보했습니다.

- MCP 는 실행한 Playwright 코드를 그대로 반환합니다. codegen 과 같은 역할입니다.
- **출력이 codegen 보다 깨끗합니다.** 접근성 트리 기반이라 `#app > div:nth-child(2)` 같은
  쓰레기가 안 나옵니다. 결과적으로 가이드의 **1단계와 2단계가 하나로 합쳐집니다.**
- 검증: TodoMVC 에서 뽑은 Locator 8개가 기존 `pages/example_page.py` 와 **8/8 일치**
  (기존 코드를 보지 않고 뽑은 뒤 대조).

**로그인이 필요한 실무 SPA 에서도 사람 개입 없이 동작했습니다.**
이메일 로그인이라 `auth_state` 사전 준비도 불필요했습니다.

**`test_id_attribute` 설정(PR #2)이 첫 실전에서 바로 쓸모를 증명했습니다.**
대상 사이트가 `data-cy` 를 쓰고 있어 `config/dev.yaml` 에 한 줄 넣는 것으로
테스트 코드는 `get_by_test_id()` 를 그대로 쓸 수 있었습니다.

**실패 분석은 가이드 6장 순서가 실제로 통합니다.** 리포트 → 스크린샷 → Page HTML 순으로
따라가 근본 원인까지 도달했습니다 (아래 뷰포트 함정).

## What Didn't Work / Gotchas

**① 뷰포트에 따라 DOM 이 통째로 달라지는 사이트가 있습니다. (실제로 한 번 실패함)**
좁은 창에서 조사하고 1920 으로 테스트를 돌려 실패했습니다.

```
좁은 폭 (모바일 드로어)  ->  data-cy="logout-btn"   있음 / my-page-btn 없음
1920x1080 (데스크톱)     ->  data-cy="my-page-btn"  있음 / logout-btn  없음
```

같은 브라우저·같은 로그인 세션에서 **폭만 바꿔** 재현 확인했습니다.
→ **규칙: 조사할 때의 뷰포트를 테스트 뷰포트(`config` 의 1920x1080)와 맞출 것.**
가이드 5장 "CI 에서만 실패 → 화면 크기 차이" 항목의 실제 사례입니다.

**② 커스텀 엘리먼트는 `get_by_role` 로 안 잡힙니다.**
대상 사이트의 제출 버튼은 `<button>` 이 아니라 `<qm-button data-cy="submit">` 이었습니다.
접근성 트리에도 `generic` 으로만 나옵니다. `to_be_disabled()` 도 통하지 않아
`to_have_attribute("disabled", "true")` 로 판정해야 했습니다.

**③ MCP 는 저장소 pytest 와 별개 브라우저입니다.** 세션·쿠키가 공유되지 않습니다.
Locator 조사용이지 테스트 실행 대체재가 아닙니다.

**④ MCP 가 작업 디렉터리에 `.playwright-mcp/` 를 만듭니다.** `.gitignore` 에 없어
매번 수동 삭제했습니다. 정식 도입 시 추가 필요.

**⑤ `playwright install` 은 옛 브라우저 버전을 지우지 않습니다.**
이 PC 의 `%LOCALAPPDATA%\ms-playwright` 에 chromium 6개 버전이 쌓여 **4.88 GB** 였습니다.
`playwright uninstall --all && playwright install chromium` 으로 약 4.2 GB 회수 가능.

**⑥ 한글이 섞인 heredoc/`grep` 출력이 콘솔에서 깨집니다.** 판정이 필요한 검사는
ASCII 키워드나 `unicode_escape` 로 출력해야 결과를 신뢰할 수 있습니다.

**⑦ 리포트를 텍스트로 추출해 판정하면 `<img>` 를 놓칩니다.**
`report.html` 에서 태그를 걷어내고 읽다가 "썸네일이 없다" 고 잘못 판단했습니다.
실제로는 `templates/report.html` 에 `.thumbs` 블록과 라이트박스(`#lb`)가 이미 있고
실패 건마다 스크린샷이 렌더링됩니다. 리포트 기능 판정은 텍스트 추출이 아니라
**브라우저로 열어서** 하거나 태그를 직접 세야 합니다.

## 결정 사항 (3회차)

**리포트 스크린샷은 상대경로 참조를 유지한다 (base64 임베드하지 않음).**
현재 `<img src="../screenshots/...">` 라서 `report.html` 파일만 떼어내면 이미지가 깨집니다.
data URI 로 임베드하면 단일 파일이 되지만 채택하지 않았습니다.

- Trace(0.49 MB)·Page HTML(3.68 MB)은 어차피 임베드 대상이 아니라
  **이미지를 넣어도 여전히 폴더 단위 전달이 필요**합니다.
- 실패가 많을수록 리포트가 무거워지는데, 실패가 많은 실행일수록 빨리 열어봐야 합니다.
  (실패 3건 +140 KB, 20건이면 +1 MB, 50건이면 +2.5 MB)
- CI 아티팩트는 원래 폴더째 zip 으로 받습니다.

→ **운영 규칙: 리포트는 `artifacts/<실행시각>/` 폴더째 전달합니다.**
단일 파일이 꼭 필요해지면(예: Slack 에 리포트 하나만 던지는 용도)
`report.embed_screenshots` 옵션으로 빼는 안을 검토하되, 기본값은 끔으로 둡니다.

## 실측 데이터 (PC 사양 요구치)

측정 환경: i5-13400 (10코어/16스레드), RAM 31.8 GB, C: 여유 66.5 GB.
`ms-playwright` 경로 프로세스만 필터링해 최대 메모리를 샘플링했습니다.

| 실행 | 브라우저 최대 RAM | python 증가분 | 합계 | 소요 |
|---|---|---|---|---|
| 순차 | 248 MB | ~130 MB | ~380 MB | 14.1s |
| `-n 2` | 499 MB | ~200 MB | ~700 MB | 9.4s (1.50배) |
| `-n 4` | 988 MB | 331 MB | ~1.3 GB | 7.4s (1.91배) |
| `--headed` | 328 MB | — | — | headless 대비 1.3배 |

```
필요 RAM ≈ 400 MB + 310 MB × 병렬 worker 수      (worker당 브라우저 247 + python 66)
실무 사이트(무거운 SPA)는 2~3배로 보정할 것 — 측정 대상이 TodoMVC 였음
권장 -n 값 = 물리코어의 절반 (그 이상은 CPU 경합으로 Flaky 증가)
```

디스크: chromium 만 700 MB / 3브라우저 1.2 GB / 파이썬 패키지 150 MB.
artifacts 는 통과 실행 0.22 MB, 실패 3건 포함 0.68 MB (Trace 가 72%).
실무 추정 60 MB/회 → 하루 10회면 600 MB/일. **정리 정책 없으면 참.**

| | 최소 | 권장 |
|---|---|---|
| CPU | 4코어 (`-n 2`) | 8코어 이상 (`-n 4~6`) |
| RAM | 8 GB | 16 GB 이상 |
| 디스크 여유 | 5 GB | 20 GB 이상 |

## 발견한 결함 의심 (대상 사이트, 개발팀 확인 필요)

로그인 실패 시 피드백이 케이스마다 다릅니다.

| 입력 | 화면에 뜨는 것 |
|---|---|
| 형식이 틀린 이메일 | "이메일이 올바르지 않습니다. 다시 한번 확인해주세요." (email 칸) |
| 형식 맞음 + 틀린 비밀번호 | "비밀번호가 올바르지 않습니다. 다시 한번 확인해주세요." (password 칸) |
| **형식 맞음 + 없는 계정** | **아무것도 뜨지 않음** — 오류 문구·토스트·다이얼로그 전부 없음 |

의도된 account enumeration 방지일 수도 있으나, 그렇다면 모호한 문구라도 떠야 합니다.
현재는 사용자가 "버튼이 안 먹는다" 로 인식합니다.
**테스트로 만들지 않았습니다** — 버그라면 테스트가 버그를 정답으로 고정시키기 때문입니다.

## Remaining Work

1. **`docs/AUTOMATION_GUIDE.md` 에 「Claude와 함께 쓰기」 절 추가.**
   목차 뒤에 새 장을 넣고 README 최상단 안내에도 한 줄 추가. 담을 내용:
   - 단계별 역할표 — 0단계 사람 / **1~4·6~8 Claude** / 5단계는 목적에 따라 갈림
     (테스트 동작 확인은 Claude, "화면이 업무적으로 맞나" 는 사람)
   - codegen 경로가 둘이라는 것: 사람은 `playwright codegen`, Claude 는 MCP snapshot
   - **뷰포트를 맞추라는 규칙** (위 Gotcha ①, 실패 사례 포함)
   - 사람이 반드시 확인할 것: 단독/병렬/연속 3회 실행 결과.
     Claude 는 요약하지 말고 출력을 그대로 붙일 것
2. **`CLAUDE.md` 생성** — Locator 우선순위, 안티패턴 10개, 커밋 전 게이트 2종,
   손대지 말 파일(`conftest.py`/`reporting/`/`utils/`/`pages/base_page.py`).
   규칙은 여기, 사람용 설명은 가이드에 두고 서로 링크 (중복 금지).
3. **가이드 5장 Flaky 표에 뷰포트 행 추가** — "뷰포트에 따라 DOM 이 다름 → 조사 뷰포트와
   테스트 뷰포트를 맞출 것". 다른 고객사에서도 밟을 함정.
4. **`.gitignore` 에 `.playwright-mcp/` 추가** (Gotcha ④).
5. **artifacts 자동 정리** — 보관 일수를 `config` 에 두고 오래된 실행 폴더 삭제.
   `conftest.py`/`utils/paths.py` 에 걸치므로 작업 후 `/code-review` 권장.
6. **Template repository 켜기** — `gh repo edit KimLakYoung111/playwright_base --template`.
   껍데기 전용이므로 "Use this template" 이 fork 보다 적합 (히스토리가 안 따라감).
7. **공개범위** — 현재 **Public**. 2회차의 Private 권장 근거("고객사 URL·계정이
   `config/*.yaml` 에 들어갈 자리")는 **이 저장소에서 자동화를 하지 않기로 하면서 소멸**했습니다.
   정책상 감추려는 게 아니면 Public 유지로 정리 가능.

> 1~4번은 문서·설정이라 서로 독립적입니다. 5번만 Base 본체를 건드립니다.
> **6·7번은 사용자 승인 없이 실행하지 마세요.**

## Key File Paths

| role | path |
|---|---|
| **가이드 (다음 회차 수정 대상)** | `docs/AUTOMATION_GUIDE.md` |
| 기능별 레퍼런스 (20장) | `README.md` |
| 모든 배선 (설정·Browser·Evidence·리포트 hook) | `conftest.py` |
| 설정 로딩 (yaml + .env + CLI) · `SUPPORTED_ENVS` 는 dev/staging/prod 고정 | `utils/config.py` |
| `test_id_attribute` 등 공통 기본값 | `config/default.yaml` |
| 실행별 artifacts 폴더 (원자적 예약) | `utils/paths.py` |
| 로깅 + 민감정보 마스킹 (`mask_secrets`) | `utils/logger.py` |
| TC ID/제목/Category/Step, 재시도 리셋 | `utils/testmeta.py` |
| Screenshot/HTML/Trace 저장 공통 진입점 | `utils/evidence.py` |
| Page Object 부모 | `pages/base_page.py` |
| 로그인 세션 재사용 (프로젝트가 `perform_login` 구현) | `fixtures/auth.py` |
| 결과 수집 → result.json / Custom HTML | `reporting/result_collector.py`, `reporting/report_generator.py` |
| **result.json 스키마 (외부 연동의 계약)** | `reporting/result_schema.md` |
| Custom Report 템플릿 (단일 파일, CDN 없음) | `reporting/templates/report.html` |
| 데이터 기반 테스트 로더 | `utils/data_loader.py` + `data/test_cases.yaml` |
| CI 예시 | `.github/workflows/playwright.yml` |
| **실증용 데모 프로젝트 (임시)** | `%LOCALAPPDATA%\Temp\claude\C--Users-klyhj-dev-e2etest-playwright-base\0a7cd08f-6455-4d87-89f1-028ede4d8f49\scratchpad\qmeet_demo` |

데모 프로젝트에서 새로 쓴 파일 (Base 복사본 위에):
`pages/qmeet_login_page.py` (Locator 근거 문서화 포함) · `pages/qmeet_home_page.py`
(뷰포트 함정 경고 포함) · `tests/smoke/test_qmeet_login.py` (QM001~003) ·
`data/login_cases.yaml` (이메일 형식 오류 4케이스) · `config/dev.yaml` · `.env`

> ⚠️ 데모는 **임시 폴더**라 세션 종료 시 사라질 수 있습니다. 계속 쓰려면
> `C:\Users\klyhj\dev\e2etest\qmeet\` 등으로 옮기세요. 이 저장소에 넣으면 안 됩니다
> (껍데기 전용 원칙 위반).

## Verification Commands

```bash
# 이 저장소 (기대값)
pytest                    # 30 passed, 4 deselected
pytest -m failure_demo    # 3 failed, 1 skipped   ← 의도된 실패
pytest -n 2               # 30 passed
git status -sb            # main...origin/main, 변경 없음
gh pr list                # 열린 PR 없음

# 30 이 아니면 예제 사이트(demo.playwright.dev/todomvc) 변경을 먼저 의심할 것

# 데모 프로젝트 (위 경로에서)
python -m pytest tests/smoke/test_qmeet_login.py --env=dev        # 6 passed
python -m pytest tests/smoke/test_qmeet_login.py --env=dev -n 2   # 6 passed

# 브라우저 버전 누적 확인 (Gotcha ⑤)
du -sh "$LOCALAPPDATA/ms-playwright"
```

## Uncommitted Changes

없습니다. `git status` clean, `main` 은 `origin/main` 과 동기화돼 있습니다.
이번 회차 저장소 변경은 **PR #1·#2·#3 머지와 `HANDOFF.md` 갱신뿐**이며,
그 외 파일을 직접 수정한 것은 없습니다. 열린 PR 도 없고 브랜치는 `main` 하나입니다.

> 이 문서에 `main` 의 커밋 해시를 적지 않습니다. 해시를 적으면 그것을 고치는
> 커밋이 다시 해시를 바꿔 영원히 어긋납니다(3회차에 실제로 한 번 겪음).
> 위치 확인은 `git log --oneline -5` 로 커밋 제목을 보세요.

머지 후 게이트 재확인: `pytest` → **30 passed, 4 deselected** (18.1s).

자격증명 위치 (값은 기록하지 않음): 데모 프로젝트의 `.env` (gitignored).
`config/dev.yaml` 에는 계정 이메일과 `password_env` 변수명만 두었습니다.
**이 저장소는 Public 이므로 고객사 URL·계정을 절대 커밋하지 마세요.**

---

## Previous Handoff (archived)

1·2회차 기록 중 아직 유효한 부분만 남깁니다. 전문은 커밋 `d470a32` 참고.

### 여전히 유효한 설계 결정

- **pytest-playwright 를 재발명하지 않고 fixture 만 덮어썼다.** `--browser` `--headed`
  `--base-url` 은 플러그인 것을 쓰고 `--env` 만 추가 (`conftest.py:167-183`).
- **Evidence 는 Base 가 직접 관리한다.** 플러그인의 `--tracing`/`--screenshot` 은 끈다
  (`conftest.py:103-109`). 같은 Context 에 tracing 을 두 번 시작하면 Trace 가 통째로 사라진다.
- **테스트 함수명은 영문, 설명은 docstring 한글.** docstring 이 리포트 제목이 된다.
- **`result.json` 이 외부 연동의 표준 인터페이스.** 스키마: `reporting/result_schema.md`.
- **tracing 기본값 `on-failure` 유지.** 통과 테스트당 0.1~0.2초를 더 쓰지만
  재현 안 되는 실패는 Trace 없이 분석 불가.
- **`requirements.txt`(범위) + `requirements.lock`(고정) 두 벌.** CI 는 lock 사용.
- **`interactions.py`/`assertions.py` 는 요구사항 8·9번 명시 항목**이라 "호출처 0" 지적에
  삭제 대신 실행 가능한 예제를 붙였다 (`tests/example/test_interactions_example.py`).

### 검증 완료 환경 (재검증 불필요)

Windows 10 (3.12.10 / 3.14.2), Linux Debian `python:3.12-slim` (3.12.12) 전부 30 passed.
GitHub Actions ubuntu-latest (3.12.14) smoke 4 passed. **macOS 는 미검증.**

### 알려진 의도적 공백

- `utils/interactions.py::wait_for_network_idle` — 권장하지 않는 API 라 예제 없음(의도).
- `ApiClient.set_token` — `.env` 의 `API_TOKEN` 이 있을 때만 도는 조건부 경로.
- `fixtures/auth.py::perform_login` — `NotImplementedError`. **프로젝트가 채우는 자리**(의도).
  동작 예시는 `tests/example/test_role_session_example.py` 가 monkeypatch 로 보여준다.

### 추천 스킬 (1회차부터 유효)

- **`/code-review`** — 고객사 프로젝트를 이 Base 위에 얹은 뒤 얹은 코드에 대해 한 번.
  1회차에 15건이 나왔고 그중 2건이 보안 문제였다. Base 본체를 고칠 때도 유효.
- **`superpowers:verification-before-completion`** — "통과했다" 를 말하기 전에 실제 실행
  결과를 붙이는 습관. 1회차에서 `role_page` Evidence 를 파일 단독 실행으로만 확인하고
  "검증 완료" 라고 보고했다가 전체 실행에서 실패한 사례가 있었다.
  3회차의 "Claude 는 요약하지 말고 출력을 그대로 붙인다" 규칙이 여기서 나왔다.
