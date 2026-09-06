# Playwright Automation Base

여러 고객사 / 여러 웹사이트의 UI 자동화 프로젝트에서 **공통으로 재사용하는 시작 키트**입니다.
이 저장소를 복사해서 새 프로젝트를 시작하면, 리포트·Evidence·환경관리·CI 는 이미 되어 있고
**테스트 코드만 쓰면 됩니다.**

- Python 3.12+ / Playwright / pytest
- 실행할 때마다 결과가 `artifacts/<실행시각>/` 에 통째로 남습니다 (덮어쓰지 않음)
- 실패하면 Screenshot / Trace / Page HTML / Log 가 자동 저장됩니다
- 리포트 2종: **개발자용**(pytest-html) + **고객사·관리자용**(Custom HTML)
- `result.json` 은 Test Runner UI·Dashboard·Slack 알림이 읽는 표준 인터페이스입니다

---

## 목차

1. [빠른 시작](#1-빠른-시작)
2. [실행 방법](#2-실행-방법)
3. [리포트 보기](#3-리포트-보기)
4. [실패 원인 분석 (Evidence)](#4-실패-원인-분석-evidence)
5. [프로젝트 구조](#5-프로젝트-구조)
6. [환경 설정](#6-환경-설정)
7. [테스트 추가하기](#7-테스트-추가하기)
8. [Page Object 추가하기](#8-page-object-추가하기)
9. [Locator 작성 기준](#9-locator-작성-기준)
10. [Assertion 작성 기준](#10-assertion-작성-기준)
11. [Marker / Category](#11-marker--category)
12. [테스트 데이터](#12-테스트-데이터)
13. [까다로운 상황 처리](#13-까다로운-상황-처리-popup--iframe--download-)
14. [로그인 세션 재사용](#14-로그인-세션-재사용)
15. [API 로 사전조건 만들기](#15-api-로-사전조건-만들기)
16. [Retry 정책](#16-retry-정책)
17. [CI 에서 실행하기](#17-ci-에서-실행하기)
18. [새 고객사 프로젝트 시작하기](#18-새-고객사-프로젝트-시작하기)
19. [향후 확장 포인트](#19-향후-확장-포인트)
20. [자주 겪는 문제](#20-자주-겪는-문제)

---

## 1. 빠른 시작

```bash
# 1) 가상환경
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 2) 패키지 설치
#   검증된 버전 조합 그대로 (팀/CI 권장)
pip install -r requirements.lock
#   또는 그 시점의 최신으로
#   pip install -r requirements.txt

# 3) Playwright Browser 설치 (최초 1회, 용량이 큽니다)
playwright install
#   특정 브라우저만:  playwright install chromium

# 4) 환경설정 파일 준비
#   Windows
copy .env.example .env
#   Linux / macOS
cp .env.example .env

# 5) 실행
pytest
```

정상이면 마지막에 이런 요약이 나옵니다.

```text
============================================================
Test Execution Summary
============================================================

Project : Example Automation
Env     : STAGING
Browser : Chromium (headless)
URL     : https://demo.playwright.dev/todomvc/

Total   : 21
Passed  : 21
Failed  : 0
Skipped : 0

Pass Rate : 100.0%
Duration  : 9s

Custom Report:
  ...\artifacts\20260906_142212\report\report.html

Pytest Report:
  ...\artifacts\20260906_142212\report\pytest_report.html

Evidence:
  ...\artifacts\20260906_142212

============================================================
```

> **Windows 에서 한글이 깨진다면** `set PYTHONUTF8=1` (PowerShell 은 `$env:PYTHONUTF8=1`)
> 를 한 번 실행하세요. 리포트 파일은 항상 UTF-8 이라 영향이 없습니다.

### 버전 관리 — requirements.txt 와 requirements.lock

| 파일 | 뜻 | 언제 쓰나 |
|---|---|---|
| `requirements.txt` | "이 범위면 동작한다" (하한선만) | 최신 버전으로 올려보고 싶을 때 |
| `requirements.lock` | "실제로 검증된 조합" (딸려온 패키지까지 고정) | **팀 공유 / CI / 새 고객사 프로젝트 시작** |

Base 는 여러 고객사가 **각자 다른 시점에** 복사해 갑니다.
lock 을 쓰면 6개월 뒤에 시작한 프로젝트도 똑같은 환경에서 출발합니다.

**버전을 올릴 때** (분기에 한 번 정도 권장)

```bash
# 1) 새 가상환경에 최신으로 설치
python -m venv .venv-new
.venv-new\Scripts\activate          # Linux: source .venv-new/bin/activate
pip install -r requirements.txt
playwright install

# 2) 전부 통과하는지 확인 (실패 예제까지)
pytest
pytest -m failure_demo

# 3) 통과했으면 고정
pip freeze > requirements.lock
```

> Playwright 는 파이썬 패키지와 브라우저 엔진 버전이 짝을 이룹니다.
> lock 으로 설치한 뒤에는 **반드시 `playwright install` 을 다시 실행**하세요.
> 현재 검증된 조합: playwright 1.62.0 / chromium 151 · firefox 153 · webkit 26.5

**검증된 환경** (세 조합 모두 전체 테스트 통과)

| OS | Python | 비고 |
|---|---|---|
| Windows 10 | 3.12.10 | |
| Windows 10 | 3.14.2 | 개발 환경 |
| Linux (Debian) | 3.12.12 | CI 절차 그대로 재현 (`pip install -r requirements.lock` → `playwright install --with-deps`) |

---

## 2. 실행 방법

| 하고 싶은 것 | 명령 |
|---|---|
| 전체 실행 | `pytest` |
| Smoke 만 | `pytest -m smoke` |
| Regression 만 | `pytest -m regression` |
| E2E 시나리오만 | `pytest -m e2e` |
| 특정 파일 | `pytest tests/example/test_example.py` |
| 특정 테스트 | `pytest tests/example/test_example.py::test_add_todo` |
| 이름으로 고르기 | `pytest -k "login and not admin"` |
| 환경 바꾸기 | `pytest --env=staging` |
| Browser 바꾸기 | `pytest --browser=firefox` |
| 브라우저 띄워서 보기 | `pytest --headed` |
| 천천히 보기 | `pytest --headed --slowmo 500` |
| 조합 | `pytest --env=staging --browser=chromium --headed` |
| 여러 Browser 동시에 | `pytest --browser=chromium --browser=firefox` |
| 병렬 실행 | `pytest -n 4` |
| 실패 시 재시도 | `pytest --reruns 1` |
| 재시도 강제로 끄기 | `pytest --reruns 0` |
| Trace 항상 남기기 | `pytest --tracing on` |
| Screenshot 항상 남기기 | `pytest --screenshot on` |
| 첫 실패에서 멈추기 | `pytest -x` |
| 실패한 것만 다시 | `pytest --lf` |
| Evidence 확인용 실패 예제 | `pytest -m failure_demo` |

기본 실행(`pytest`)에서는 `failure_demo` 테스트가 자동으로 제외되므로 **항상 전부 PASS** 여야 합니다.

지원 환경: `dev` / `staging` / `prod`
지원 Browser: `chromium` / `firefox` / `webkit`

---

## 3. 리포트 보기

실행이 끝나면 `artifacts/<실행시각>/report/` 에 3개가 생깁니다.

```text
artifacts/20260906_133000/report/
├─ report.html          ← 고객사 / 관리자용 (Custom Report)
├─ pytest_report.html   ← 자동화 담당자용 (pytest-html, traceback 상세)
└─ result.json          ← 프로그램이 읽는 표준 결과
```

브라우저로 열기만 하면 됩니다.

```bash
# Windows
start artifacts\20260906_133000\report\report.html
# macOS
open  artifacts/20260906_133000/report/report.html
```

마지막 실행 폴더는 `artifacts/latest_run.txt` 에 적혀 있습니다.

```bash
# Windows PowerShell
start "$(Get-Content artifacts/latest_run.txt)\report\report.html"
```

### Custom Report 에 있는 것

- 상단 Dashboard — 프로젝트 / 환경 / Browser / 대상 URL / 시작·종료 / 전체 수행시간
- Total · Passed · Failed · Skipped, Pass Rate 진행바 + 도넛 차트
- **Category 별 결과** (업무 영역별 통계)
- **Failed Tests** 영역 — 실패 사유, 실패 시점 URL, Screenshot 썸네일(클릭하면 확대), Trace / HTML / Log 링크
- 전체 테스트 표 — 필터(All/Passed/Failed/Skipped) + 검색, 행을 누르면 **Step 목록**이 펼쳐짐

무거운 UI 라이브러리를 쓰지 않고 HTML/CSS/JS 만으로 만들어서 파일 하나만 메일로 보내도 열립니다.

### Markdown 요약 (Slack / CI 붙여넣기용)

```bash
python -m reporting.ci_summary
```

`result.json` 구조는 [`reporting/result_schema.md`](reporting/result_schema.md) 를 보세요.

---

## 4. 실패 원인 분석 (Evidence)

테스트가 실패하면 아무 설정 없이 아래가 자동 저장됩니다.

```text
artifacts/20260906_133000/
├─ screenshots/TC901_test_missing_element_fails_chromium.png
├─ traces/     TC901_test_missing_element_fails_chromium.zip
├─ html/       TC901_test_missing_element_fails_chromium.html
├─ logs/       TC901_test_missing_element_fails_chromium.log
└─ logs/       run.log        (실행 전체 로그)
```

파일 이름은 `TC ID + 함수명 + 파라미터` 라서 어떤 테스트 것인지 바로 알 수 있습니다.
현재 URL 은 `result.json` 과 Custom Report 에 기록됩니다.

### Trace 보기 (가장 강력한 분석 도구)

```bash
playwright show-trace artifacts/20260906_133000/traces/TC901_test_missing_element_fails_chromium.zip
```

클릭 하나하나의 DOM 스냅샷, 네트워크, 콘솔을 타임라인으로 되감아 볼 수 있습니다.

### 성공한 테스트도 남기고 싶다면

일회성이면 CLI 로:

```bash
pytest --tracing on          # 모든 테스트의 Trace 보관
pytest --screenshot on       # 모든 테스트의 Screenshot 보관
```

계속 그렇게 쓰려면 `.env` 또는 `config/*.yaml` 에서:

```bash
SCREENSHOT_MODE=always     # always | on-failure | never
TRACE_MODE=always
```

> Evidence 는 Base 가 직접 관리합니다. `--tracing` / `--screenshot` 값은 위 모드로
> 옮겨 담기고, pytest-playwright 자체 수집은 꺼집니다. 그래서 결과물이 `test-results/`
> 로 흩어지지 않고 항상 `artifacts/<실행시각>/` 한 곳에 모입니다.
>
> `on-failure` 모드는 실패 순간을 담기 위해 모든 테스트에서 Trace 수집을 시작하고
> 통과하면 버립니다. 통과 테스트당 약 0.1~0.2초가 더 듭니다. 실패 분석 가치가 훨씬
> 크므로 기본값으로 두고, 속도가 급한 대규모 회귀에서만 `TRACE_MODE=never` 를 쓰세요.

---

## 5. 프로젝트 구조

```text
playwright_base/
├─ tests/                     테스트 코드
│  ├─ smoke/                    배포 직후 최소 확인
│  ├─ regression/               회귀 테스트
│  ├─ e2e/                      업무 흐름 시나리오 (순서 의존 허용)
│  └─ example/                  실행 가능한 예제 모음
│     ├─ test_example.py          기본 흐름 + 데이터 기반 테스트
│     ├─ test_base_page_example.py  BasePage 공통 메서드
│     ├─ test_interactions_example.py  Popup/iframe/Dialog/Upload/Download
│     ├─ test_role_session_example.py  로그인 세션 재사용
│     ├─ test_api_example.py       API CRUD + 사전조건/Cleanup
│     └─ test_failure_demo.py      Evidence 확인용 의도적 실패
│
├─ pages/                     Page Object (화면 단위)
│  ├─ base_page.py              공통 동작 (goto/click/fill/wait/upload ...)
│  └─ example_page.py           예제 (TodoMVC)
│
├─ components/                재사용 UI 조각 (헤더, 그리드, 모달 ...)
│  ├─ base_component.py
│  └─ filter_bar.py             예제
│
├─ fixtures/                  pytest fixture 모음
│  └─ auth.py                   로그인 세션 재사용 / 역할별 계정 (뼈대)
│
├─ utils/                     공통 유틸
│  ├─ config.py                 설정 로딩 (yaml + .env + CLI)
│  ├─ paths.py                  실행별 artifacts 폴더
│  ├─ logger.py                 로깅 + 민감정보 마스킹
│  ├─ testmeta.py               TC ID / 제목 / Category 수집
│  ├─ steps.py                  test_step() - Step 기록
│  ├─ evidence.py               Screenshot / HTML / Trace 저장
│  ├─ assertions.py             자주 쓰는 검증 helper
│  ├─ interactions.py           Popup / iframe / Download / Dialog / API 대기
│  └─ data_loader.py            JSON / YAML / CSV 로딩
│
├─ api/
│  └─ api_client.py            사전조건·Cleanup 용 REST 클라이언트
│
├─ data/                      테스트 데이터 (코드와 분리)
│  ├─ users.json                JSON 예시
│  ├─ products.json
│  ├─ orders.csv                CSV 예시
│  ├─ test_cases.yaml           YAML (데이터 기반 테스트)
│  └─ sample.pdf                파일 업로드 예시용
│
├─ config/                    환경별 설정 (민감정보 제외)
│  ├─ default.yaml              공통 기본값
│  ├─ dev.yaml / staging.yaml / prod.yaml
│
├─ reporting/                 리포트 생성
│  ├─ result_collector.py       pytest 결과 수집
│  ├─ report_generator.py       result.json + Custom HTML + Console Summary
│  ├─ ci_summary.py             Markdown 요약 (CI/Slack 용)
│  ├─ result_schema.md          result.json 스키마 문서
│  ├─ templates/report.html     Custom Report 템플릿
│  └─ static/                   로고 등 (기본은 비어 있음)
│
├─ artifacts/                 실행 결과 (Git 에 올리지 않음)
│  └─ 20260906_133000/
│     ├─ report/  screenshots/  traces/  html/  logs/
│
├─ .github/workflows/playwright.yml   GitHub Actions 예시
├─ conftest.py                모든 배선이 모이는 곳
├─ pytest.ini                 marker / 기본 옵션
├─ requirements.txt           버전 범위 (하한선)
├─ requirements.lock          검증된 버전 조합 (딸려온 패키지까지 고정)
├─ .env.example
└─ .gitignore
```

### 설계 방식 한 줄 요약

| 관심사 | 어디에 | 왜 |
|---|---|---|
| 화면 조작 | `pages/` | 화면이 바뀌면 여기만 고친다 |
| 테스트 의도 | `tests/` | Locator 없이 읽히는 시나리오만 |
| 값(URL/계정/타임아웃) | `config/`, `.env` | 코드에 하드코딩하지 않는다 |
| 배선(Browser/리포트/Evidence) | `conftest.py` | 테스트는 몰라도 된다 |
| 결과 | `artifacts/<실행시각>/` | 실행마다 분리, 덮어쓰지 않는다 |

---

## 6. 환경 설정

### 우선순위 (뒤로 갈수록 강함)

```text
config/default.yaml  →  config/<env>.yaml  →  .env / 환경변수  →  CLI 옵션
```

### `.env` 에는 최소한만 두세요

`.env` 는 `config/*.yaml` 보다 **강합니다.** 그래서 `.env` 에 값을 적어두면
환경을 바꿔도 그 값이 계속 따라옵니다.

```bash
# 예: .env 에 HEADLESS=true 를 적어두면
#     config/dev.yaml 의 headless:false 가 무시되어 dev 에서도 브라우저가 안 보입니다.
```

`.env.example` 은 이 함정을 피하려고 **환경(`ENV`)과 민감정보만 활성 상태**이고
나머지는 주석 처리해 두었습니다. 필요할 때만 주석을 푸세요.
일회성 변경은 `.env` 를 고치지 말고 CLI 를 쓰는 편이 안전합니다.

```bash
pytest --browser=firefox --headed        # .env 를 건드리지 않고 이번만
```

값이 잘못되면(`ENV=qa`, `SCREENSHOT_MODE=nevr`, `DEFAULT_TIMEOUT=30초`)
실행 시작 시점에 한 줄짜리 에러로 바로 알려줍니다. 조용히 기본값으로 되돌아가지 않습니다.

### 민감정보는 `.env` 에만

`config/*.yaml` 에는 **비밀번호를 절대 쓰지 않습니다.** 변수 이름만 가리킵니다.

```yaml
# config/default.yaml
accounts:
  user:
    username: "standard_user"
    password_env: USER_PASSWORD     # 실제 값은 .env 의 USER_PASSWORD
  admin:
    username: "admin_user"
    password_env: ADMIN_PASSWORD
```

```bash
# .env  (Git 에 올라가지 않음)
USER_PASSWORD=실제비밀번호
ADMIN_PASSWORD=실제비밀번호
```

테스트에서 쓰기:

```python
def test_login(page, run_config):
    account = run_config.account("user")     # 없으면 이해하기 쉬운 에러
    page.get_by_label("아이디").fill(account.username)
    page.get_by_label("비밀번호").fill(account.password)
```

로그에 비밀번호/토큰이 찍히면 자동으로 `***` 로 가려집니다.

### 설정 항목 추가하기

1. `config/default.yaml` 에 값을 넣는다.

   ```yaml
   features:
     new_checkout: true
   timeouts:
     upload: 120000
   ```

2. 테스트에서 꺼내 쓴다.

   ```python
   def test_결제(page, run_config):
       if not run_config.get("features.new_checkout"):
           pytest.skip("이 환경에는 신규 결제가 없습니다.")
   ```

자주 쓰는 값이면 `utils/config.py` 의 `RunConfig` 에 필드로 승격시키고,
환경변수로도 바꿀 수 있게 `_env_*` 한 줄을 추가하면 됩니다.

### 환경 추가하기 (예: `qa`)

1. `config/qa.yaml` 생성
2. `utils/config.py` 의 `SUPPORTED_ENVS` 에 `"qa"` 추가
3. `pytest --env=qa`

---

## 7. 테스트 추가하기

`tests/` 아래 알맞은 폴더에 `test_*.py` 를 만듭니다.

```python
import pytest
from playwright.sync_api import Page, expect

from pages.login_page import LoginPage
from utils.steps import test_step


@pytest.mark.smoke              # 실행 유형
@pytest.mark.login              # 업무 영역 → 리포트 Category
@pytest.mark.tc_id("TC001")     # TC 관리 도구의 ID
def test_login_success(page: Page, run_config):
    """정상 로그인"""            # ← 리포트에 표시될 이름

    login = LoginPage(page)
    account = run_config.account("user")

    with test_step("로그인 페이지 접속"):
        login.open()

    with test_step("아이디 / 비밀번호 입력"):
        login.fill_credentials(account.username, account.password)

    with test_step("로그인 버튼 클릭"):
        login.submit()

    with test_step("대시보드 확인"):
        expect(page.get_by_role("heading", name="대시보드")).to_be_visible()
```

리포트에는 이렇게 나옵니다.

```text
TC001  정상 로그인   Login   PASSED   2.40 sec
  1. 로그인 페이지 접속      PASSED  0.62s
  2. 아이디 / 비밀번호 입력   PASSED  0.18s
  3. 로그인 버튼 클릭        PASSED  0.31s
  4. 대시보드 확인          PASSED  1.29s
```

### 규칙

- **함수 이름은 영문**, **설명은 docstring 에 한글** — CI 로그와 `-k` 필터가 편해집니다.
- `test_step()` 은 선택입니다. 중요한 흐름에만 붙이세요. 안 써도 테스트는 동작합니다.
- 각 테스트는 **독립적으로** 실행되어야 합니다. 앞 테스트가 만든 상태에 기대지 마세요.
  (Browser Context 가 테스트마다 새로 만들어지므로 쿠키·로컬스토리지는 자동으로 초기화됩니다)
- 순서 의존이 꼭 필요한 업무 흐름은 `tests/e2e/` 에 **한 함수 안에서** 이어지게 씁니다.
- `time.sleep()` 은 쓰지 않습니다. `expect(...)` 가 알아서 기다립니다.

---

## 8. Page Object 추가하기

`pages/login_page.py`

```python
from playwright.sync_api import Locator

from pages.base_page import BasePage


class LoginPage(BasePage):
    path = "login"                      # base_url 뒤에 붙는 경로

    # --- Locator 는 전부 여기 (테스트 코드에는 쓰지 않는다) ---
    @property
    def username_input(self) -> Locator:
        return self.page.get_by_label("아이디")

    @property
    def password_input(self) -> Locator:
        return self.page.get_by_label("비밀번호")

    @property
    def submit_button(self) -> Locator:
        return self.page.get_by_role("button", name="로그인")

    @property
    def error_message(self) -> Locator:
        return self.page.get_by_role("alert")

    def loaded_locator(self) -> Locator:
        # open() 이 이 요소가 보일 때까지 기다려 줍니다.
        return self.username_input

    # --- 동작 ---
    def fill_credentials(self, username: str, password: str) -> "LoginPage":
        self.username_input.fill(username)
        self.password_input.fill(password)
        return self

    def submit(self) -> "LoginPage":
        self.submit_button.click()
        return self
```

`BasePage` 의 모든 메서드를 실제로 써보는 예제가 있습니다.

```bash
pytest tests/example/test_base_page_example.py -v
```

`BasePage` 가 이미 주는 것: `open()` `goto()` `click()` `fill()` `type_text()`
`select_option()` `check()` `hover()` `press()` `scroll_to()` `upload_file()`
`get_text()` `get_texts()` `get_value()` `count()` `is_visible()`
`wait_for_visible()` `wait_for_hidden()` `reload()` `screenshot()`

> Playwright API 를 감추지 않습니다. 필요하면 `self.page` 를 그대로 쓰세요.
> **wrapper 를 늘리는 것보다 Playwright 원본을 쓰는 쪽이 낫습니다.**

### Component (화면 안의 재사용 영역)

헤더, 좌측 메뉴, 페이징, 그리드처럼 여러 화면에 반복되는 영역은 `components/` 에 만듭니다.

```python
from components.base_component import BaseComponent


class Header(BaseComponent):
    @property
    def logout_button(self):
        return self.root.get_by_role("button", name="로그아웃")


# Page Object 안에서
self.header = Header(page, page.get_by_role("banner"))
```

`root` 안에서만 요소를 찾기 때문에 같은 컴포넌트가 여러 개 있어도 헷갈리지 않습니다.

---

## 9. Locator 작성 기준

**위에 있는 것부터** 시도하세요. 사용자가 화면을 인식하는 방식에 가까울수록 잘 안 깨집니다.

| 순위 | 방법 | 예시 |
|---|---|---|
| 1 | `get_by_role()` | `page.get_by_role("button", name="로그인")` |
| 2 | `get_by_label()` | `page.get_by_label("아이디")` |
| 3 | `get_by_placeholder()` | `page.get_by_placeholder("검색어 입력")` |
| 4 | `get_by_text()` | `page.get_by_text("주문이 완료되었습니다")` |
| 5 | `data-testid` | `page.get_by_test_id("order-row")` |
| 6 | CSS | `page.locator("footer.footer")` |

- **XPath 는 쓰지 않습니다.** DOM 구조가 조금만 바뀌어도 깨집니다.
- 인덱스(`nth(3)`)에 기대지 말고 텍스트나 역할로 좁히세요.
- 자동 생성된 클래스(`css-1a2b3c`)는 쓰지 마세요.
- 안정적인 Locator 를 만들 수 없으면 **개발팀에 `data-testid` 추가를 요청**하는 것이 정답입니다.
- Locator 는 반드시 Page Object 안에 두고, 테스트 코드에는 쓰지 않습니다.

### 좋은 예 / 나쁜 예

```python
# 나쁨 — 테스트 코드에 Locator, 구조 의존
page.locator("//div[@class='form']/div[2]/input").fill("hong")

# 좋음 — Page Object 안에서 역할 기반
self.page.get_by_label("아이디").fill("hong")
```

---

## 10. Assertion 작성 기준

**Playwright 의 `expect()` 를 기본으로 씁니다.** 조건이 만족될 때까지 자동으로 기다립니다.

```python
from playwright.sync_api import expect

expect(locator).to_be_visible()
expect(locator).to_have_text("주문 완료")
expect(locator).to_contain_text("완료")
expect(locator).to_have_count(3)
expect(page).to_have_url(re.compile(r".*/orders/\d+"))
expect(page).to_have_title("주문 내역")
```

`assert page.locator(...).is_visible()` 같은 즉시 판정은 쓰지 마세요.
화면이 아직 안 그려졌을 뿐인데 실패합니다 (대표적인 Flaky 원인).

여러 곳에서 똑같이 반복되는 검증만 `utils/assertions.py` 에 helper 로 둡니다.
검증 의도를 로그에 남기고 싶을 때 유용합니다.

```python
from utils.assertions import should_be_visible, should_have_status

should_be_visible(dashboard.title, "대시보드 제목")
should_have_status(response, 200)
```

---

## 11. Marker / Category

`pytest.ini` 의 `markers` 에 등록된 것만 쓸 수 있습니다 (`--strict-markers`).
오타를 내면 바로 에러가 나서 조용히 누락되는 일이 없습니다.

```python
@pytest.mark.smoke          # 실행 유형: smoke / regression / e2e / failure_demo
@pytest.mark.login          # 업무 영역: login / payment / product / search / api
@pytest.mark.slow           # 특성:     slow / flaky
@pytest.mark.tc_id("TC001") # TC 관리 도구 ID
@pytest.mark.category("결제") # Category 를 직접 지정하고 싶을 때
@pytest.mark.title("정상 로그인")  # docstring 대신 제목을 지정하고 싶을 때
```

### Category 가 정해지는 순서

1. `@pytest.mark.category("...")` 가 있으면 그 값
2. 없으면 **업무 영역 marker 중 첫 번째** (실행 유형·특성 marker 는 제외)
3. 그것도 없으면 `Uncategorized`

즉 `@pytest.mark.payment` 만 붙여도 리포트에 **Payment** 카테고리로 집계됩니다.

### 업무 영역 추가하기

`pytest.ini` 에 한 줄 추가하면 끝입니다.

```ini
markers =
    ...
    order: 업무 영역 - 주문
    delivery: 업무 영역 - 배송
```

리포트의 Category 표와 `result.json` 의 `categories[]` 에 자동으로 들어갑니다.

---

## 12. 테스트 데이터

데이터는 코드와 분리해서 `data/` 에 둡니다.

```python
from utils.data_loader import load_data, pick

users = load_data("users.json")          # JSON
cases = load_data("test_cases.yaml")     # YAML
rows  = load_data("orders.csv")          # CSV → list[dict]

username = pick("users.json", "valid.username")
customer = pick("orders.csv", "0.customer")
```

호출할 때마다 **복사본**을 돌려줍니다. 한 테스트가 값을 바꿔도 다음 테스트는
원본을 받으므로 테스트 독립성이 깨지지 않습니다.

동작하는 예제: `tests/example/test_example.py::test_csv_data_becomes_todos`

### 데이터로 케이스 늘리기 (Data Driven)

테스트 코드는 그대로 두고 YAML 만 늘리면 케이스가 늘어납니다.

```python
@pytest.mark.parametrize(
    "case",
    load_data("test_cases.yaml")["todo_cases"],
    ids=lambda case: case["id"],
)
def test_remaining_count(page, case):
    """데이터 파일로 케이스를 늘리는 예시"""
    ...
```

```yaml
# data/test_cases.yaml
todo_cases:
  - id: TC-DATA-001
    description: 한 건 추가하면 남은 개수가 1이다
    todos: ["회의록 정리"]
    expected_remaining: "1 item left"
```

Excel / DB / API 로 넓힐 때는 `utils/data_loader.py` 에 같은 모양(리스트·딕셔너리를 돌려주는)
함수를 하나 더 추가하면 테스트 코드는 안 바뀝니다.

---

## 13. 까다로운 상황 처리 (Popup / iframe / Download …)

`utils/interactions.py` 에 helper 가 있습니다. 전부 Playwright 의 `expect_*` 위에 얇게 올린 것입니다.

**실제로 돌아가는 예제가 있습니다.** 화면을 `set_content` 로 직접 만들기 때문에
특정 사이트에 의존하지 않고, 그대로 복사해 쓸 수 있습니다.

```bash
pytest tests/example/test_interactions_example.py -v
```

```python
from utils.interactions import (
    open_popup, open_new_tab, frame, download_file,
    handle_dialog, wait_for_response,
)

# 새 창 / Popup
popup = open_popup(page, lambda: page.get_by_role("link", name="약관").click())
expect(popup.get_by_role("heading")).to_be_visible()

# target=_blank 새 탭
new_tab = open_new_tab(page, lambda: page.get_by_role("link", name="상세").click())

# iframe
payment = frame(page, "#payment-frame")
payment.get_by_label("카드번호").fill("4111111111111111")

# 파일 업로드 (BasePage)
page_object.upload_file(page.get_by_label("첨부파일"), "data/sample.pdf")

# 다운로드
saved = download_file(page, lambda: page.get_by_role("button", name="엑셀 다운로드").click(),
                      save_dir=Path("artifacts/downloads"))

# alert / confirm
with handle_dialog(page, accept=True) as messages:
    page.get_by_role("button", name="삭제").click()
assert messages == ["정말 삭제할까요?"]

# 특정 API 응답 기다리기
res = wait_for_response(page, "**/api/orders",
                        lambda: page.get_by_role("button", name="주문").click())
assert res.status == 200

# hover / scroll 은 BasePage 에
page_object.hover(menu)
page_object.scroll_to(footer)
```

> `wait_for_network_idle()` 도 있지만 되도록 쓰지 마세요.
> **요소를 기다리는 것**(`expect`)이 네트워크를 기다리는 것보다 훨씬 안정적입니다.

---

## 14. 로그인 세션 재사용

기본은 테스트마다 새 Context 라 매번 로그인해야 합니다.
로그인이 느린 사이트라면 세션을 저장해두고 재사용하세요.

1. `fixtures/auth.py` 의 `perform_login()` 을 실제 로그인 절차로 구현합니다.

   ```python
   def perform_login(page, config, role):
       account = config.account(role)
       page.goto("login")
       page.get_by_label("아이디").fill(account.username)
       page.get_by_label("비밀번호").fill(account.password)
       page.get_by_role("button", name="로그인").click()
       expect(page.get_by_role("heading", name="대시보드")).to_be_visible()
   ```

2. 테스트에서 `role_page` 를 받아 씁니다.

   ```python
   def test_주문내역(role_page):
       page = role_page("user")      # 이미 로그인된 상태
       page.goto("orders")
   ```

3. 권한별 테스트는 역할만 바꿉니다: `role_page("admin")`

세션 파일은 `auth_state/<환경>_<역할>.json` 에 저장되고 Git 에 올라가지 않습니다.
계정/권한은 `config/*.yaml` 의 `accounts` 에 역할을 추가하면 늘어납니다.

**`role_page` 로 만든 Page 도 기본 `page` 와 똑같이 실패 시 Evidence 가 남습니다.**
파일 이름 뒤에 역할이 붙어서 어느 세션의 것인지 구분됩니다.

```text
TC010_test_admin_flow_chromium_admin.png
TC010_test_admin_flow_chromium_admin.zip
```

동작하는 예제: `tests/example/test_role_session_example.py`
(TodoMVC 에는 로그인이 없어서 `perform_login` 을 "상태를 만들어 저장"하는 것으로
바꿔 끼운 형태입니다. 세션 저장·복원과 Evidence 수집이 실제로 검증됩니다.)

---

## 15. API 로 사전조건 만들기

UI 로 데이터를 만들면 느리고 잘 깨집니다. 사전조건·Cleanup 은 API 로 처리하세요.

```python
from api.api_client import ApiClient


@pytest.fixture
def order_api(run_config):
    with ApiClient(base_url=run_config.api_base_url,
                   token=os.getenv("API_TOKEN")) as client:
        yield client


def test_주문_취소(page, order_api):
    """사전조건은 API 로, 검증은 UI 로"""
    order = order_api.json(order_api.expect_ok(
        order_api.post("/orders", json={"productId": "P001"}), 201))

    try:
        page.goto(f"orders/{order['id']}")
        page.get_by_role("button", name="주문 취소").click()
        expect(page.get_by_text("취소되었습니다")).to_be_visible()
    finally:
        order_api.delete(f"/orders/{order['id']}")      # Cleanup
```

프로젝트 API 는 `ApiClient` 를 상속해 메서드로 정리하세요.

동작하는 예제: `pytest -m api`
(GET / POST / PUT / PATCH / DELETE 와 `try/finally` Cleanup 패턴)

---

## 16. Retry 정책

**기본 재시도는 0회입니다.** 무조건 재시도하면 진짜 버그가 묻힙니다.

```bash
pytest --reruns 1            # 이번 실행만 1회 재시도
pytest --reruns 0            # 설정에 retries 가 있어도 이번엔 재시도 안 함
```

```yaml
# config/staging.yaml — 환경 단위로 정하고 싶을 때
retries: 0
```

권장 운영 방식:

- **로컬 = 0회.** 실패하면 원인을 봅니다.
- **CI = 1회.** 네트워크 순간 장애로 파이프라인이 빨개지는 것만 막습니다.
- 재시도로 통과한 테스트는 리포트에 `retry 1` 배지가 붙고
  `result.json` 의 `tests[].retries` 로 남습니다. **Flaky 목록으로 관리하세요.**

---

## 17. CI 에서 실행하기

`.github/workflows/playwright.yml` 예시가 들어 있습니다. 핵심만 보면:

```yaml
- run: pip install -r requirements.txt
- run: python -m playwright install --with-deps chromium
- run: pytest --env=staging --browser=chromium -m "smoke and not failure_demo" --reruns 1
  env:
    HEADLESS: "true"
    USER_PASSWORD: ${{ secrets.USER_PASSWORD }}   # .env 는 커밋하지 않는다
- uses: actions/upload-artifact@v4                # artifacts/ 통째로 보관
  if: always()
  with: { path: artifacts/ }
- run: python -m reporting.ci_summary >> "$GITHUB_STEP_SUMMARY"
```

- 로컬은 `--headed` 가능, CI 는 `HEADLESS=true` 로 headless 고정
- 민감정보는 반드시 CI Secrets 로 주입 (`.env` 는 절대 커밋하지 않습니다)
- GitLab CI / Jenkins 도 같은 명령 3줄이면 됩니다

---

## 18. 새 고객사 프로젝트 시작하기

이 저장소는 **고객사에 종속된 로직을 담지 않습니다.** 아래만 갈아끼우면 됩니다.

```text
1) 저장소 복사 → 새 저장소로 시작
2) config/*.yaml 의 base_url / api_base_url / accounts 교체
3) .env.example 을 프로젝트에 맞게 손질 → .env 생성
4) pytest.ini 의 업무 영역 marker 교체 (login/payment → 실제 업무)
5) pages/example_page.py, components/filter_bar.py 삭제
   → 실제 화면 Page Object 작성
6) tests/example/ 삭제 (test_failure_demo.py 는 남겨두면 Evidence 점검에 유용)
7) data/*.json, data/*.yaml 교체
8) 로그인이 있으면 fixtures/auth.py 의 perform_login() 구현
9) README 상단의 프로젝트 소개만 고쳐 쓰기
```

**손대지 않아도 되는 것** — `conftest.py`, `reporting/`, `utils/`, `pages/base_page.py`,
`components/base_component.py`, `api/api_client.py`.
공통 기능이 개선되면 Base 에서 고쳐 각 프로젝트로 내려보냅니다.

---

## 19. 향후 확장 포인트

지금은 **구조만** 잡아두고 과하게 구현하지 않았습니다. 필요할 때 이 지점에서 이어가세요.

| 확장 | 어디서 시작하나 | 지금 상태 |
|---|---|---|
| **Test Runner UI (PySide6)** | `result.json` 을 읽는다 | 스키마 확정, GUI 비의존 |
| 사내 Dashboard / 수행이력 DB | `result.json` 을 적재 | 스키마 문서화 완료 |
| Trend Report | 실행별 `result.json` 누적 | 필요한 필드 전부 포함 |
| Slack / Email 알림 | `reporting/ci_summary.py` 재사용 | Markdown 요약 제공 |
| Jenkins / GitLab CI | `.github/workflows/` 참고 | 명령 3줄로 동일 |
| API 테스트 확대 | `api/api_client.py` 상속 | 클라이언트 + 예제 있음 |
| DB 검증 | `utils/` 에 `db_client.py` 추가 | 자리만 |
| Excel 데이터 | `utils/data_loader.py` 에 함수 추가 | JSON/YAML/CSV 지원 중 |
| 시각 회귀 테스트 | `expect(page).to_have_screenshot()` | Playwright 내장 |
| Appium (모바일) | 별도 fixture 패키지 | 구조만 |

### Test Runner UI 연동 방법

```python
import json, subprocess
from pathlib import Path

subprocess.run(["pytest", "--env=staging", "--browser=chromium", "-m", "smoke"])

run_dir = Path(Path("artifacts/latest_run.txt").read_text(encoding="utf-8"))
result = json.loads((run_dir / "report" / "result.json").read_text(encoding="utf-8"))

print(result["summary"]["pass_rate"])
for test in result["tests"]:
    ...  # 목록/진행률/결과 Dashboard 에 표시
```

- 테스트 목록은 `pytest --collect-only -q` 로 가져옵니다 (이때는 artifacts 를 만들지 않습니다)
- 실시간 로그는 `artifacts/<run_id>/logs/run.log` 를 tail 하면 됩니다
- 리포트 열기는 `report/report.html` 경로를 그대로 쓰면 됩니다

---

## 20. 자주 겪는 문제

| 증상 | 원인과 해결 |
|---|---|
| `playwright: command not found` | 가상환경 활성화 후 `pip install -r requirements.txt` |
| `Executable doesn't exist ...` | `playwright install` 을 실행하지 않음 |
| 설치 중 `WinError 206` (경로가 너무 김) | Playwright 패키지 구조가 깊어 Windows 260자 제한에 걸립니다. 프로젝트를 짧은 경로(`C:\work\...`)로 옮기거나 긴 경로 지원을 켜세요 |
| 콘솔에 한글이 깨짐 | `set PYTHONUTF8=1` (리포트 파일은 항상 UTF-8) |
| `'qa' 는 invalid choice` | `--env` 는 dev/staging/prod 만. 추가하려면 6장 참고 |
| 테스트가 가끔 실패 | `time.sleep()`·`is_visible()` 대신 `expect()` 사용. Trace 로 원인 확인 |
| Locator 를 못 찾음 | `playwright show-trace ...` 로 그 시점 DOM 확인. `--headed --slowmo 500` 으로 눈으로 확인 |
| Evidence 가 안 생김 | 실패했을 때만 저장됩니다. 항상 남기려면 `SCREENSHOT_MODE=always` |
| artifacts 폴더가 계속 쌓임 | Git 에는 안 올라갑니다. 오래된 폴더는 주기적으로 지우세요 |
| 여러 사람이 동시에 실행 | 폴더를 만들면서 자리를 잡으므로 같은 초에 시작해도 겹치지 않습니다 (`_1` 이 붙음) |
| `SCREENSHOT_MODE 값이 올바르지 않습니다` | `always` / `on-failure` / `never` 중 하나여야 합니다. 오타는 실행 시작 시 바로 잡힙니다 |
| `.env` 값이 안 먹는 것 같음 | CLI 옵션이 `.env` 보다 강합니다. 반대로 `.env` 는 `config/*.yaml` 보다 강해서, 주석을 풀면 환경별 설정이 무시됩니다 |

### 디버깅에 제일 쓸모 있는 3가지

```bash
pytest tests/... --headed --slowmo 500     # 눈으로 보기
PWDEBUG=1 pytest tests/...                 # Playwright Inspector (한 줄씩)
playwright show-trace <trace.zip>          # 실패한 실행 되감아 보기
```
