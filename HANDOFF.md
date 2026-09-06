# HANDOFF: Playwright 자동화 공통 Base — ✅ done, 초기 구축·리뷰 반영·4개 환경 검증 완료

## Current Status (2026-09-06): ✅ done — `main` (`b6be2eb..afb3cf3`, pushed) + 본 핸드오프는 `docs/handoff-20260906`

> 여러 고객사의 Playwright Python 자동화 프로젝트에서 공통 Base 로 쓸 스타터 킷을
> 처음부터 만들고, 코드 리뷰에서 나온 결함 15건을 전부 고친 뒤,
> Windows(3.12/3.14) · Linux(Docker) · GitHub Actions 네 환경에서 검증을 마쳤습니다.
> **다음 세션의 첫 할 일: 저장소 공개 범위 결정** (아래 "Next session" 1번).
> 기능 작업은 남아 있지 않으며, 새로 붙일 일이 없다면 이 저장소는 그대로 배포 가능합니다.

---

### What was done (commits `b6be2eb`..`afb3cf3`)

- **Base 프로젝트 전체 신규 작성** (`aa35f61`) — 55개 파일.
  환경관리(yaml→.env→CLI 3단), Page Object, 실행별 Artifact, Evidence 자동수집,
  리포트 2종, `result.json` 표준 인터페이스, Marker/Category, CI 예시.
  요구사항 34개 항목을 모두 반영했고 예제는 실제로 실행됩니다.
- **검증 환경 기록** (`afb3cf3`) — `requirements.lock` 헤더와 README 에
  실제로 통과 확인한 OS/Python 조합만 적었습니다. 추정치 아님.

> 리뷰 지적 15건 수정과 미검증 영역 보강은 `aa35f61` 안에 함께 들어 있습니다
> (커밋 전에 수정·검증을 끝낸 뒤 한 덩어리로 커밋했기 때문).
> 무엇을 왜 고쳤는지는 아래 "Decisions made" 참고.

---

### Gate results

이 핸드오프를 쓰기 직전에 실제로 돌린 결과입니다.

| 게이트 | 명령 | 결과 |
|---|---|---|
| 전체 | `pytest` | **30 passed, 4 deselected** (27.7s) |
| Evidence | `pytest -m failure_demo` | **3 failed, 1 skipped** (의도된 실패) → Evidence 20개 파일 생성 |
| 병렬 | `pytest -n 2` | **30 passed** (13.4s) |

환경별 검증 (모두 전체 통과):

| 환경 | Python | 결과 |
|---|---|---|
| Windows 10 | 3.12.10 | 30 passed |
| Windows 10 | 3.14.2 | 30 passed (개발 환경) |
| Linux (Debian, `python:3.12-slim` 컨테이너) | 3.12.12 | 30 passed — CI 절차 그대로 재현 |
| **GitHub Actions (ubuntu-latest)** | 3.12.14 | **4 passed** (smoke) — run [34034537942](https://github.com/KimLakYoung111/playwright_base/actions/runs/34034537942) 전 스텝 success |

부가 검증: `actionlint` 경고 0건 / 깨끗한 venv 에서 `requirements.lock` 설치 결과 28개 패키지 정확히 일치 /
민감정보 마스킹(등록값·패턴·traceback) 유출 0건.

---

### Decisions made (and why)

**설계**

- **pytest-playwright 를 재발명하지 않고 fixture 만 덮어썼다.**
  `--browser` `--headed` `--base-url` 은 플러그인 것을 그대로 쓰고 `--env` 만 추가.
  `browser_type_launch_args` / `browser_context_args` 에 설정값을 주입하는 방식(`conftest.py:167-183`).
- **Evidence 는 Base 가 직접 관리한다.** 플러그인의 `--tracing`/`--screenshot` 은
  Base 모드로 옮겨 담고 플러그인 수집은 끈다(`conftest.py:103-109`).
  같은 Context 에 tracing 을 두 번 시작하면 충돌해 Trace 가 통째로 사라지기 때문.
- **테스트 함수명은 영문, 설명은 docstring 한글.**
  CI 로그 깨짐과 `-k` 필터 사용성 때문. 리포트에는 docstring 이 제목으로 나온다.
- **`result.json` 을 표준 인터페이스로 고정.** Test Runner UI(PySide6)·Dashboard·
  Slack 알림·Trend 는 전부 HTML 이 아니라 이 파일을 읽는다. 스키마: `reporting/result_schema.md`.
- **tracing 기본값은 `on-failure` 유지.** 통과 테스트당 0.1~0.2초(측정: 9309ms vs 7190ms)를
  더 쓰지만, 재현 안 되는 실패는 Trace 없으면 분석이 불가능하다. `config/default.yaml:36-39` 에 비용 명시.
- **`requirements.txt`(범위) + `requirements.lock`(고정) 두 벌.**
  Base 는 고객사마다 다른 시점에 복사해 가므로 재현성이 중요. CI 는 lock 사용.

**리뷰 지적 15건 수정 (전부 재현 후 수정, 재현으로 확인)**

- 🔴 에러 메시지·traceback 이 마스킹 없이 `result.json`/`report.html` 에 실림
  → `mask_secrets()` 공개 함수화, 수집 단계에서 마스킹(`reporting/result_collector.py:145-149`)
- 🔴 `record.exc_info` 미마스킹 → 필터가 `exc_text`/`stack_info` 까지 처리(`utils/logger.py:70-76`)
- 🟠 재시도 시 `TestMeta` 재사용으로 Step 누적 → `reset_meta()` 신설(`utils/testmeta.py:171`)
- 🟠 `browser` 필드 누락 → 병합 목록에 추가 + 멀티 브라우저일 때만 리포트에 열 추가
- 🟠 `--tracing on` 충돌로 Trace 전멸 → 위 "Evidence 는 Base 가 직접" 결정으로 해결
- 🟠 재시도 시 1차 로그 덮어씀 → `unique_path()` 적용(`conftest.py:239`)
- 🟠 렌더러가 collector 레코드를 변형 → `to_dict()` 가 복사본 반환
- 🟡 `--reruns 0` 무시(falsy 체크) / `.env` 오타 시 INTERNALERROR / `lru_cache` mutable 공유 /
  실행폴더 TOCTOU / `OSError` 미포착 / `only_browser` 가 Category 로 잡힘 /
  `.env.example` 이 yaml 을 덮어씀 / 모드 오타 무검증 — 전부 수정

**리뷰에 반박한 것 1건**

- `utils/interactions.py`·`utils/assertions.py` 가 "호출처 0 = 추측성 기능" 이라는 지적은
  **요구사항 8·9번에서 명시적으로 요청된 항목**이라 삭제 대신 실행 가능한 예제를 붙였다
  (`tests/example/test_interactions_example.py`).

**추가로 잡은 것 (리뷰 목록 밖)**

- `role_page` 로 만든 Page 는 Evidence 가 안 남던 구멍 → `page` fixture 와 같은 코드 경로로 통합.
  파일명에 역할 꼬리표(`..._user.png`)를 붙여 구분(`fixtures/auth.py:111-150`).
- `storage_state_factory` 가 캐시만 믿고 파일 존재를 확인하지 않던 문제 → 사라졌으면 재생성.
- **Git CRLF 자동 변환이 `data/sample.pdf` 를 손상시킬 뻔함** → `.gitattributes` 추가,
  커밋 후 바이트 비교로 무결성 확인.
- 첫 푸시가 `workflow` 스코프 부족으로 통째 거부 → `gh auth refresh -s workflow` 로 해결.

---

### Key files

| role | path |
|---|---|
| 모든 배선(설정·Browser·Evidence·리포트 hook) | `conftest.py` |
| 설정 로딩 (yaml + .env + CLI 우선순위) | `utils/config.py` |
| 실행별 artifacts 폴더 (원자적 예약) | `utils/paths.py` |
| 로깅 + 민감정보 마스킹 (`mask_secrets`) | `utils/logger.py` |
| TC ID/제목/Category/Step, 재시도 리셋 | `utils/testmeta.py` |
| Screenshot/HTML/Trace 저장 공통 진입점 | `utils/evidence.py` |
| Page Object 부모 | `pages/base_page.py` |
| 로그인 세션 재사용 (프로젝트가 `perform_login` 구현) | `fixtures/auth.py` |
| 결과 수집 → result.json / Custom HTML | `reporting/result_collector.py`, `reporting/report_generator.py` |
| **result.json 스키마 (외부 연동의 계약)** | `reporting/result_schema.md` |
| Custom Report 템플릿 (단일 파일, CDN 없음) | `reporting/templates/report.html` |
| 신규 담당자용 전체 가이드 (20장) | `README.md` |
| CI 예시 | `.github/workflows/playwright.yml` |

---

### Next session

1. **저장소 공개 범위를 정한다.** 현재 **Public** 이다.
   지금 커밋된 내용에 민감정보는 없다(`.env` 미포함, 비밀번호 실값 0건 확인).
   다만 이 Base 는 앞으로 고객사 URL·계정이 `config/*.yaml` 에 들어갈 자리라 Private 권장.
   ```bash
   gh repo edit KimLakYoung111/playwright_base --visibility private \
     --accept-visibility-change-consequences
   ```
   → 결정만 하면 명령 한 줄. **사용자 승인 없이 실행하지 말 것.**

2. **새 고객사 프로젝트를 시작한다면** README 18장 "새 고객사 프로젝트 시작하기" 의
   9단계를 그대로 따른다. `conftest.py`/`reporting/`/`utils/`/`pages/base_page.py` 는 손대지 않는다.

3. **동작 확인이 필요하면** 아래가 기대값이다.
   ```bash
   pytest                  # 30 passed, 4 deselected
   pytest -m failure_demo  # 3 failed, 1 skipped  ← 의도된 실패
   ```
   `pytest` 가 30이 아니면 예제 사이트(demo.playwright.dev/todomvc) 변경을 먼저 의심할 것.

4. **의존성을 올릴 때** README "버전 관리" 절 절차를 따른다.
   새 venv → `requirements.txt` 설치 → 두 게이트 통과 확인 → `pip freeze > requirements.lock`.
   Playwright 는 패키지와 브라우저 엔진이 짝이므로 `playwright install` 을 반드시 다시 실행.

### 알려진 미검증 / 의도적 공백

- `utils/interactions.py::wait_for_network_idle` — 권장하지 않는 API 라 예제 없음(의도).
- `ApiClient.set_token` — `.env` 의 `API_TOKEN` 이 있을 때만 실행되는 조건부 경로.
- `fixtures/auth.py::perform_login` — `NotImplementedError`. **프로젝트가 채우는 자리**(의도).
  동작 예시는 `tests/example/test_role_session_example.py` 가 monkeypatch 로 보여준다.
- macOS 미검증. Windows/Linux/CI 만 확인.

---

### Suggested skills / 다음 세션 추천 스킬

- `code-review` — 고객사 프로젝트를 이 Base 위에 얹은 뒤, 얹은 코드에 대해 한 번.
  이번 회차에 15건이 나왔고 그중 2건이 보안 문제였다. Base 를 고칠 때도 유효.
- `superpowers:verification-before-completion` — "통과했다" 를 말하기 전에 실제 실행 결과를 붙이는 습관.
  이번에 `role_page` Evidence 를 파일 단독 실행으로만 확인했다가 전체 실행에서 실패한 사례가 있었다.

---

### Uncommitted / excluded

핸드오프 커밋 시점 기준, 아래는 **의도적으로 저장소에 넣지 않는다**.

- `.env` — 실제 비밀번호/토큰. `.gitignore` 처리됨. `.env.example` 만 커밋(값은 비어 있음).
- `.venv/` — 로컬 가상환경.
- `artifacts/**` — 테스트 실행 결과. `artifacts/.gitkeep` 만 추적.
- `auth_state/` — 로그인 세션 파일. 계정 쿠키/토큰이 들어간다.
- `.pytest_cache/`, `__pycache__/` — 캐시.

> 자격증명 위치: 테스트 계정 비밀번호는 `.env` (gitignored),
> CI 는 GitHub Secrets(`USER_PASSWORD`, `ADMIN_PASSWORD`, `API_TOKEN`).
> `config/*.yaml` 에는 변수명만 두고 값은 절대 쓰지 않는다.
