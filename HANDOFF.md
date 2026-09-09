# HANDOFF: 코드 리뷰 지적 반영 (실행 메타·마스킹·설정 파싱 + 회귀 테스트 배증)

> 최신 세션이 맨 위입니다. 아래로 갈수록 과거 기록입니다.

---

## Goal

5회차에 넣은 **실행 메타(schema 1.1)와 artifacts 자동 정리**를 고객사 프로젝트
(`qmeet`)로 내려보내는 과정에서 `/code-review` 가 결함 15건을 올렸습니다.
전부 이 저장소가 원인이므로 **여기서 고치고 각 프로젝트로 다시 내려보냈습니다.**

## Current Status: Completed — 커밋 전 (워킹트리에만 있음)

게이트 4종 통과. `qmeet` 저장소의 `utils/`·`reporting/`·`tests/unit/`·`conftest.py` 는
이 저장소와 **바이트 단위로 동일**합니다 (`diff -rq` EXIT=0).

### What Was Done

| 파일 | 수정 |
|---|---|
| `utils/testmeta.py` | `NON_CATEGORY_MARKERS` 에 `base_unit` 추가. 안 넣어서 리포트 Category 에 `Base_Unit` 이 뜨고 있었음 (`result.json` 으로 실측 확인) |
| `utils/runmeta.py` | `subprocess.run` 에 `encoding="utf-8", errors="replace"`. `text=True` 만 두면 Windows 는 cp949 로 디코드해 한글 브랜치명이 깨지거나 통째로 사라짐 |
| `utils/runmeta.py` | `status --porcelain=v2 --branch` **1회**로 브랜치·커밋·dirty 수집 (기존 3회 × 최대 `GIT_TIMEOUT`). git 2.13.1 미만은 기존 3-call 로 자동 폴백 |
| `utils/runmeta.py` | `dirty` 를 못 구하면 `None`. `False` 로 적으면 "커밋과 정확히 일치" 를 거짓 단정. detached HEAD 는 `branch: None` |
| `utils/logger.py` | URL userinfo 마스킹(`_mask_url_credentials`). `https://user:pw@`·`https://token@`·`https://:pw@` 세 형태. 콜론이 없으면 사용자명인지 토큰인지 구분 불가라 **가리는 쪽으로 실패** |
| `utils/logger.py` | `_SECRET_PATTERNS` 를 `(정규식, 치환식)` 쌍으로. 인덱스 참조를 없애 패턴 추가가 안전해짐 |
| `utils/config.py` | `_yaml_int`/`_yaml_bool`/`_yaml_str` + `_yaml_missing`. `keep_days:` 처럼 값을 비우면 yaml 이 None 을 주는데 `int(None)` 은 TypeError 라 conftest 의 `except ValueError` 를 빠져나가 INTERNALERROR 가 됨 |
| `utils/config.py` | 같은 버그가 있던 **기존 설정 전부에 적용** — `slow_mo`·`retries`·`timeouts.*`·`viewport.*`·`headless`. 중첩 키는 `label="timeouts.default"` 로 오류 메시지에 경로를 남김 |
| `utils/config.py` | `show_triggered_by: "false"`(따옴표) 가 `bool("false")=True` 로 뒤집히던 문제. `TRUE_STRINGS` 를 환경변수와 공유 |
| `utils/config.py` | `app_version` 을 `str()` 로. `app_version: 2.10` 은 yaml 이 float 2.1 로 읽어 `result_schema.md` 의 "문자열" 약속이 깨짐 |
| `reporting/templates/report.html` | `dirty is none` 이면 "(변경 여부 확인 못 함)" 별도 표기. None 은 falsy 라 한 갈래로는 깨끗한 것과 구별 안 됨 |
| `reporting/templates/report.html` | 느린 테스트 Top 5 를 `[:5]` 슬라이스로. 전체 순회 후 `loop.index <= 5` 였음 |
| `reporting/result_schema.md` | `dirty`·`branch` 가 null 일 수 있음 명시 |
| `tests/unit/test_config_report.py` | `_read_yaml` 을 갈아끼워 **저장소 설정과 분리**. 이전에는 고객사가 `show_triggered_by: false` 로 두면 커밋 게이트가 엉뚱하게 깨졌음 |
| `tests/unit/test_runmeta.py` | `sensitive_filter._literals` 저장/복원 fixture. 전역 싱글턴에 리터럴을 등록만 하고 안 지워 이후 테스트의 로그·트레이스백이 조용히 `***` 로 바뀌었음 |
| `tests/unit/*.py` | 6개 파일(`test_logger_masking.py` 신규) 전부 `tc_id` + `category` marker. 이전엔 8/37 개만 있어 리포트에 함수명이 그대로 나왔음 |

**회귀 테스트 37 → 81개.** 새로 지키는 것: UTF-8 디코드, git 호출 1회, `dirty=None`,
detached HEAD, untracked=dirty, v2 폴백, URL 자격증명 3형태, yaml 빈 값(설정 7종
parametrize), 따옴표 친 불리언, 숫자형 버전.

### What Was NOT Done

리뷰 지적 중 **설계 판단이 필요한 3건은 고치지 않았습니다.**

1. **`keep_days: 14` 기본 ON** — 새 고객사 프로젝트가 README 를 읽기 전에 Evidence
   삭제를 켠 채 시작합니다. 유지 이유: 문서 3곳에 설명돼 있고 `keep_min_runs`
   안전장치가 있음. 끄려면(`0`) 정책 결정이 필요합니다.
2. **`prune_old_runs` 를 `pytest_configure` 에서 실행** — 리뷰는 "시작 지연" 을
   지적했으나, **디스크가 찼을 때 이번 실행의 Evidence 쓸 공간을 먼저 확보한다**는
   반대 논리가 더 강해 유지했습니다. `sessionfinish` 로 옮기면 그 효과가 사라집니다.
3. **`base_unit` 실행이 `keep_min_runs` 슬롯 잠식** — 브라우저도 안 쓰는 1초짜리
   실행도 `artifacts/<run_id>/` 를 만듭니다. 게이트 3종을 두 번 돌리면 보호 슬롯
   5개가 껍데기로 찹니다. 고치려면 "base_unit 실행은 artifacts 를 만들지 않는다"
   같은 설계 변경이 필요합니다.

## What Worked

- **고객사 프로젝트에서 고치지 않고 Base 로 올려 고친 것.** `qmeet` 에서 직접
  고쳤으면 다음 동기화에 되돌아갔습니다. 고친 뒤 다시 내려보내 두 저장소를 맞췄습니다.
- **`result.json` 을 직접 열어 검증.** `categories` 가 `['Base_Unit']` →
  `['Artifacts','Config','Report','RunMeta']` 로 바뀐 것을 JSON 에서 확인했습니다.
- **`git status --porcelain=v2 --branch` 한 방.** `# branch.oid`/`# branch.head` 를
  읽고, `#` 로 시작하지 않는 줄이 하나라도 있으면 dirty 입니다.

## What Didn't Work / Gotchas

- **`python -m reporting.ci_summary` 가 Windows 콘솔에서 죽습니다.**
  `UnicodeEncodeError: 'cp949' codec can't encode character '\u274c'` — 실패한
  실행의 `❌` 아이콘 때문입니다. `to_markdown()` 자체는 정상이고 **콘솔 출력만**
  깨집니다. 이번 변경 이전부터 있던 문제입니다. HANDOFF 가 검증 절차로 안내하는
  명령이라 고칠 값어치가 있습니다.
- **`pytest -n 2` 가 한 번 실패했습니다.** `test_home_page_opens` 가
  `Page.goto: Timeout 45000ms`. 재실행하니 84초 → 10초에 30 passed.
  외부 예제 사이트(`demo.playwright.dev/todomvc`) 접속 지연이고 코드 변경과 무관합니다.
- **`Path.read_text(newline=...)` 는 Python 3.13 부터입니다.** 3.12 에서는 TypeError.
  CRLF 를 보존하려면 `io.open(p, newline="")` 을 쓰세요.

## Remaining Work

1. **`reporting/ci_summary.py` 의 cp949 크래시** — `main()` 의 `print` 앞에
   `sys.stdout.reconfigure(encoding="utf-8")` 를 넣거나 아이콘을 ASCII 로.
2. **위 「What Was NOT Done」 3건 결정** — 특히 3번은 실측으로 확인된 현상입니다.
3. 5회차의 잔여 항목(인쇄 미리보기 육안 확인, Template 경로 실증)은 아래 5회차
   기록에 그대로 남아 있습니다.

## Verification Commands

```bash
# 게이트 4종 — 이 세션에서 실제로 나온 수치
pytest                    # 30 passed, 57 deselected   (16s)
pytest -m failure_demo    # 3 failed, 1 skipped        (11s)  <- 의도된 실패
pytest -m base_unit       # 81 passed, 34 deselected   (1.4s) <- 브라우저 없음
pytest -n 2               # 30 passed                  (10s)

# 30 이 아니면 예제 사이트(demo.playwright.dev/todomvc) 변경을 먼저 의심할 것
# base_unit 수는 Base 자체 테스트가 늘면 같이 는다. 갑자기 줄었으면 의심할 것

# 고객사 프로젝트와 공통 파일이 일치하는지 (EXIT=0 이어야 함)
diff -rq --exclude=__pycache__ utils ../qmeet/utils
diff -rq --exclude=__pycache__ reporting ../qmeet/reporting
diff -rq --exclude=__pycache__ tests/unit ../qmeet/tests/unit
diff -q conftest.py ../qmeet/conftest.py
```

## Uncommitted Changes

```
 M HANDOFF.md                        M utils/config.py
 M reporting/result_schema.md        M utils/logger.py
 M reporting/templates/report.html   M utils/runmeta.py
 M tests/unit/test_config_report.py  M utils/testmeta.py
 M tests/unit/test_report_render.py
 M tests/unit/test_result_meta.py
 M tests/unit/test_runmeta.py
```

11 files changed, 648 insertions(+), 87 deletions(-). 전부 이번 세션 작업물입니다.

---

## 5회차 — 리포트 보강 (Marker·Flaky·느린 테스트·인쇄 + 실행 메타)

## Goal

이 저장소는 여러 고객사의 Playwright 자동화에 공통으로 쓰는 **껍데기(템플릿) 전용**입니다.
실제 자동화는 이 Base 를 복사해 별도 저장소에서 합니다 (3회차 확정, 유효).

이번 회차는 고객사에 전달하는 `report.html` 에 **이미 수집하고 있는데 화면에 안 그리던
데이터**를 그리고, 인쇄본을 쓸 수 있게 만들고, "어느 앱 빌드를 무슨 명령으로 테스트했나"
를 `result.json` 에 남겼습니다.

## Current Status: Completed — `main` 에 머지·푸시됨

설계 → 계획 → Task 8개 구현을 마쳤고, 게이트 4종을 실제로 돌려 통과를 확인한 뒤
`main` 에 fast-forward 머지했습니다. 열린 PR 은 없습니다.

**다음 세션의 첫 할 일은 아래 「Remaining Work」 1번(인쇄 미리보기 육안 확인)** 이고,
새로 시작할 만한 것은 3번(Template 경로 실증, 이전 회차부터 이월)입니다.

### What Was Done

두 단계로 나눠 커밋했습니다. 설계 근거는 `docs/superpowers/specs/`,
단계별 계획은 `docs/superpowers/plans/` 에 있습니다.

**Step A — 템플릿만 고침 (`result.json` 불변)**

| 내용 | 메모 |
|---|---|
| Marker 별 집계 표 | `markers[]` 를 이미 수집하는데 안 그리고 있었음 |
| 재시도(Flaky) 목록 + 요약에서 앵커 링크 | 건수만 있고 어느 테스트인지 알 수 없었음 |
| 느린 테스트 Top 5 (`<details>` 기본 접힘) | 5건 이하면 섹션 숨김 |
| 인쇄/PDF CSS (`@media print`) | 전체 테스트 표·느린 테스트만 뺌 |

`result.json` 을 안 건드려 기존 소비자(Test Runner UI, 사내 Dashboard, `ci_summary`)에
위험이 0 입니다.

**Step B — 실행 메타 (`schema_version` 1.0 → 1.1)**

`run` 블록에 `app_version`, `git{branch,commit,dirty}`, `triggered_by`, `command`,
`workers` 를 추가했습니다. **기존 15개 필드는 하나도 없애지 않았습니다** — 리뷰에서
`result_schema.md` 의 1.0 목록과 1:1 대조해 확인했습니다.

**리뷰를 10회 붙였습니다.** Task 별 8회 + 브랜치 전체 1회 + 수정분 `/code-review` 1회.
뒤 두 번이 각각 실제 결함을 잡았습니다 (아래 Gotchas ①②).

### What Was NOT Done

- **Ctrl+P 인쇄 미리보기를 사람 눈으로 본 적이 없습니다.** Chrome 확장이 연결되지
  않아 확인하지 못했습니다. 구조(섹션 id, 인쇄 규칙)는 생성된 리포트에서 확인했지만
  실제 인쇄 화면은 미확인입니다.
- **영상(video) 은 의도적으로 뺐습니다.** 사유와 재검토 조건 3가지가 설계 문서
  「영상(video): 보류」 절에 있습니다. 다시 꺼내기 전에 그 절을 먼저 읽으세요.
- README / `docs/AUTOMATION_GUIDE.md` 에 새 섹션 4개와 새 설정 2개를 반영하지
  않았습니다 (최종 리뷰가 Minor 로 지적).
- macOS / 모바일 뷰포트 / SNS 로그인 — 3회차부터 이월, 여전히 미검증.

## What Worked

**구현 에이전트와 리뷰 에이전트를 Task 마다 갈라 붙이고, 판정은 메인에서 한 것.**
리뷰어에게 "무엇을 지적하지 말라" 를 절대 쓰지 않았더니 계획 자체의 결함이 계속
올라왔습니다. 지적 중 상당수가 **계획서에 박아둔 테스트 코드** 문제였습니다.

**변이 테스트(mutation test) 를 습관으로 만든 것.** "테스트가 통과했다" 로는
아무것도 증명되지 않습니다. 구현을 일부러 깨서 테스트가 **실패하는지** 확인한 뒤에야
그 테스트에 값이 있습니다. 이번에 이 방법으로 무력한 테스트 5개를 찾아냈습니다.

**최종 브랜치 리뷰를 별도로 돌린 것.** 개별 Task 리뷰 8회가 전부 통과시킨 인쇄본
버그를 최종 리뷰가 잡았습니다. Task 3(섹션 생성)과 Task 4(인쇄 CSS)가 따로 만들어져
생긴 **이음매** 문제라, 한 Task 만 보는 리뷰로는 구조적으로 볼 수 없었습니다.

## What Didn't Work / Gotchas

**① `monkeypatch.delenv` 는 `.env` 를 막지 못합니다.** `load_config` 가 안에서
`load_dotenv(PROJECT_ROOT / ".env", override=False)` 를 부르는데, `override=False` 는
**이미 `os.environ` 에 있는 키만** 건너뜁니다. `delenv` 로 지운 키는 "없는" 상태라
`.env` 값이 그대로 재주입됩니다. 실측:

```
delenv 후 load_dotenv     -> 'from_dotenv'   (재주입됨)
setenv(이름, "") 후        -> ''              (dotenv 가 건너뜀)
```

→ **설정 기본값 테스트는 `monkeypatch.setenv(이름, "")` 로 막으세요.**
`_env_str`/`_env_bool` 이 빈 값을 "없음" 으로 처리해 기본값 경로도 그대로 탑니다.
`tests/unit/test_paths_retention.py` 의 `delenv` 는 `load_dotenv` 경로가 아니라
그대로 둬도 됩니다.

**② 인쇄 CSS 로 섹션 "안쪽" 만 숨기면 빈 상자가 남습니다.** `#tests` 처럼 내부
요소만 숨기면 감싸는 `<section class="panel">` 이 테두리째 인쇄됩니다. 섹션 자체에
id 를 주고(`#slow-tests`, `#all-tests`) 그것을 숨겨야 합니다. `details` 같은 **태그
셀렉터도 쓰지 마세요** — 나중에 누가 `<details>` 를 하나 더 넣으면 인쇄에서 조용히
사라집니다.

**③ 문자열 존재만 확인하는 테스트는 아무것도 지키지 않습니다.** 이번에 5개를
고쳤습니다. 대표적인 것들:

- `assert "#tests" in print_block` → `display:block` 이라고 정반대로 써도 통과
- `assert "느린 테스트" not in html` → CSS 주석에 같은 문구가 생기자 무너짐
- 재시도 목록 테스트가 "포함" 만 보고 "제외" 를 안 봐서 전체를 나열해도 통과
- git 실패 테스트의 `stdout=""` 때문에 `returncode` 검사를 빼먹어도 통과
- 헤더 숨김 테스트가 `{% if run.git %}` 가드를 통째로 지워도 통과
  (Jinja 가 `None.branch` 를 빈 문자열로 렌더)

**④ 계획서에 `deselected` 수치를 박지 마세요.** `base_unit` 테스트를 추가할 때마다
변합니다. Task 1 시점에 이미 틀려서 이후 모든 Task 를 헛되이 실패시킬 값이었습니다.

**⑤ 서브에이전트가 커밋 메시지 파일을 UTF-8 BOM 으로 씁니다.** 커밋 제목 앞에
보이지 않는 문자가 붙습니다. 이 저장소에 2건 남아 있습니다(제목이 `fix: Task 6 리뷰
지적 수정`, `test: flaky 섹션 테스트 강화` 인 커밋). 기능엔 영향 없지만 나중에
커밋을 grep 으로 찾을 때 걸립니다. 지시할 때 **"UTF-8 without BOM"** 을 명시하세요.

**⑥ 서브에이전트 보고의 "확인했습니다" 를 그대로 믿지 마세요.** 인쇄 선택자 4종을
확인했다는 보고가 있었는데, 근거로 든 리포트는 테스트가 4건뿐이라 `<details>` 가
아예 렌더되지 않았습니다. 30건 실행으로 다시 확인해야 했습니다.
(이전 회차 Gotcha ⑤ 와 같은 교훈이 또 나왔습니다.)

## 이번 회차 결정 (되돌리는 법 포함)

**① `result.json` schema 1.0 → 1.1.** 추가만 했고 기존 필드는 그대로입니다.
소비자는 모르는 키를 무시하면 되므로 되돌릴 필요가 없습니다.
→ 원복이 필요하면 `reporting/result_collector.py` 의 `SCHEMA_VERSION` 과 `run` 블록
추가분만 되돌리면 됩니다.

**② `app_version` 은 주입식이고 형식을 강제하지 않습니다.** 고객사마다 버전 체계가
달라서입니다. 비우면 리포트에 줄 자체가 안 나옵니다.
→ CI 에서 `APP_VERSION` 환경변수로 주는 것을 권장합니다.

**③ 실행자 이름은 끌 수 있습니다.** 개인정보가 걸리는 고객사면
`config/default.yaml` 의 `report.show_triggered_by: false`.

**④ 인쇄본에서 빼는 것은 전체 테스트 표와 느린 테스트뿐입니다.** Marker 표와
재시도 표는 인쇄합니다 — Marker 는 비개발자가 인쇄본에서 가장 먼저 보는 집계이고,
재시도는 실패에 준하는 신호라 빼면 손해라는 판단입니다.

**⑤ 영상(video) 은 넣지 않았습니다.** Trace 가 이미 화면 프레임·DOM·네트워크·콘솔을
담고 있어 원인 규명에서 영상이 이길 수 없습니다. 재검토 조건 3가지가 설계 문서에
있으니 **추측으로 다시 꺼내지 마세요.**

## Remaining Work

1. **인쇄 미리보기를 눈으로 한 번 보기** — `artifacts/<실행시각>/report/report.html` 을
   브라우저로 열고 Ctrl+P. 확인할 것: 빈 상자가 없는지, 실패 카드가 페이지 중간에서
   잘리지 않는지, 다크모드 브라우저에서도 흰 바탕으로 나오는지. **이번 회차에서
   유일하게 사람 눈이 필요한 항목입니다.**
2. **README / `docs/AUTOMATION_GUIDE.md` 갱신** — 새 섹션 4개(Marker·재시도·느린
   테스트·인쇄)와 새 설정 2개(`app_version`, `report.show_triggered_by`) 가 아직
   문서에 없습니다. 외부 계약인 `reporting/result_schema.md` 는 갱신했습니다.
3. **Template 경로로 첫 고객사 프로젝트 실증** (이전 회차부터 이월) — 남은 것 중
   **유일하게 새 정보를 주는 작업**입니다. "Use this template" 로 새 저장소를 만들어
   README 절차를 따라가 보세요.
4. **데모 프로젝트 이전** (이전 회차 이월) — 다만 기록된 경로의 사용자명이 `klyhj`
   이고 현재 PC 사용자는 `user` 입니다. **경로가 이미 안 맞으니 존재부터 확인하세요.**
5. macOS / 모바일 뷰포트 / SNS 로그인 검증 (우선순위 낮음).

## Key File Paths

이번 회차에 새로 생기거나 크게 바뀐 것만 적습니다.

| role | path |
|---|---|
| 설계 근거 (영상 보류 사유 포함) | `docs/superpowers/specs/2026-09-09-report-enhancement-design.md` |
| 단계별 구현 계획 | `docs/superpowers/plans/2026-09-09-report-enhancement.md` |
| 실행 메타 수집 (**예외를 절대 안 올림**) | `utils/runmeta.py` |
| 메타 주입부 (컨트롤러 1회) | `conftest.py` 의 `pytest_configure` |
| `run` 블록 조립 | `reporting/result_collector.py::to_dict` |
| 리포트 화면 전부 | `reporting/templates/report.html` |
| **외부 계약 (1.1 문서)** | `reporting/result_schema.md` |
| 새 설정 2개 | `config/default.yaml` 의 `app_version`, `report:` |

## Verification Commands

아래 기대값은 **머지 직전 브랜치에서 실제로 돌려 확인한 값**입니다 (예측 아님).

```bash
# 게이트 4종
pytest                    # 30 passed            <- deselected 수는 기준 아님(계속 변함)
pytest -m failure_demo    # 3 failed, 1 skipped  <- 의도된 실패
pytest -m base_unit       # 53 passed            <- Base 자체 회귀
pytest -n 2               # 30 passed

# 30 이 아니면 예제 사이트(demo.playwright.dev/todomvc) 변경을 먼저 의심할 것
# base_unit 수는 Base 자체 테스트가 늘면 같이 는다. 갑자기 줄었으면 의심할 것

# 실행 메타가 실제로 들어갔는지
python -m reporting.ci_summary   # 제목 아래 Automation `<브랜치> @ <커밋>` 줄
```

한글 판정이 필요한 검사는 `PYTHONIOENCODING=utf-8` 를 주고 **파일로 받아서** 읽으세요.
커밋 메시지도 파일에 쓰고 `git commit -F <파일>` (Gotcha ⑤ 도 함께 볼 것).

## 다음 세션 추천 스킬

- **`/code-review high`** — Base 본체를 고칠 때 반드시. 이번 회차에 개별 리뷰 8회가
  놓친 것을 두 번 잡았습니다.
- **`superpowers:verification-before-completion`** — "통과했다" 앞에 실제 출력을
  붙이는 습관. 이번 회차 교훈은 여기서 한 발 더 나갑니다: **통과는 증거가 아닙니다.
  구현을 깨서 테스트가 실패하는 것까지 봐야 그 테스트에 값이 있습니다.**
- **`superpowers:subagent-driven-development`** — Task 가 나뉘는 작업에 잘 맞았습니다.
  단, **최종 브랜치 리뷰를 반드시 별도로** 돌리세요. Task 사이 이음매는 개별 리뷰가
  구조적으로 못 봅니다.

## Uncommitted Changes

**없습니다.** `main` 이 `origin/main` 과 동기화돼 있고 열린 PR 도 없습니다.

`.superpowers/sdd/` 아래에 이번 회차의 작업 브리프·리뷰 패키지·에이전트 보고서가
남아 있습니다. **git-ignored 스크래치라 커밋하지 않았습니다.** 다음 세션에 필요 없으면
지워도 됩니다.

> 이 문서에 커밋 해시를 적지 않습니다. 해시를 적으면 그것을 고치는 커밋이 다시
> 해시를 바꿔 영원히 어긋납니다(3회차에 실제로 겪음).
> 위치 확인은 `git log --oneline -5` 로 커밋 제목을 보세요.

자격증명 위치 (값은 기록하지 않음): `.env` (gitignored).
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

---

### 4회차 전문 (3회차 잔여 작업 처리)

### Goal

이 저장소는 여러 고객사의 Playwright 자동화에 공통으로 쓰는 **껍데기(템플릿) 전용**입니다.
실제 자동화는 이 Base 를 복사해 별도 저장소에서 합니다 (3회차 확정, 유효).
이번 회차는 3회차 핸드오프의 「Remaining Work」 7개를 실제로 처리했습니다.

### Current Status: Completed (3회차 잔여 작업 기준)

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

### What Worked

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

### What Didn't Work / Gotchas

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

### 이번 회차 결정 (되돌리는 법 포함)

**① `pytest` 가 `base_unit` 을 제외합니다.** `tests/unit/` 은 Base 프레임워크 자체
회귀 테스트라 고객사용 리포트에 업무 테스트와 섞이면 안 된다고 판단했습니다
(`failure_demo` 와 같은 방식). 대신 게이트가 3종으로 늘었습니다.
→ 원복: `pytest.ini` 의 `addopts` 에서 `and not base_unit` 만 제거.

**② `keep_days` 기본값 14.** 기존 프로젝트에 이 Base 를 반영하면 **다음 실행에서
14일 지난 artifacts 폴더가 지워집니다.** 최근 5개는 나이와 무관하게 보호됩니다.
→ 끄기: `config/default.yaml` 의 `artifacts.keep_days: 0`.

### Remaining Work

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

### Key File Paths

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

### Verification Commands

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

### Uncommitted Changes

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
