# 자동화 스크립트 작성 가이드

이 Base 위에서 **실제로 테스트 스크립트를 쓰는 사람**을 위한 문서입니다.

| 문서 | 다루는 것 |
|---|---|
| [`README.md`](../README.md) | 기능별 레퍼런스 — "이 기능은 어떻게 쓰나" |
| **이 문서** | 작업 흐름 — "새 화면을 받았다. 뭐부터 하나" |

README 를 다 읽고 시작할 필요는 없습니다. 이 문서의 1장을 그대로 따라 하면
첫 테스트가 나오고, 막히는 지점에서 README 의 해당 장을 찾아보면 됩니다.

> **Claude Code 에게 맡길 생각이라면 [9장](#9-claude-와-함께-쓰기)을 먼저 보세요.**
> 8단계 중 어디까지 넘길 수 있고 어디를 사람이 붙잡아야 하는지 정리돼 있습니다.

---

## 목차

1. [첫 테스트 만들기 — 8단계 워크스루](#1-첫-테스트-만들기--8단계-워크스루)
2. [손에 익혀야 할 도구 4가지](#2-손에-익혀야-할-도구-4가지)
3. [무엇을 자동화하고 무엇을 안 하나](#3-무엇을-자동화하고-무엇을-안-하나)
4. [안티패턴 도감](#4-안티패턴-도감)
5. [Flaky 처방전](#5-flaky-처방전)
6. [실패했을 때 보는 순서](#6-실패했을-때-보는-순서)
7. [PR 올리기 전 체크리스트](#7-pr-올리기-전-체크리스트)
8. [명령어 치트시트](#8-명령어-치트시트)
9. [Claude 와 함께 쓰기](#9-claude-와-함께-쓰기)

---

## 1. 첫 테스트 만들기 — 8단계 워크스루

로그인 화면을 자동화한다고 가정합니다. 처음이면 이 순서를 그대로 따라 하세요.

### 0단계 — 대상 정하기 (5분)

코드를 열기 전에 종이에 적습니다.

```text
TC ID   : TC001
목적    : 정상 계정으로 로그인하면 대시보드가 보인다
사전조건: 활성 상태의 일반 사용자 계정
절차    : 로그인 화면 → 아이디/비밀번호 입력 → 로그인 클릭
기대결과: 대시보드 제목이 보인다
```

**여기서 정하지 못하면 코드로도 못 씁니다.** 기대결과가 "정상적으로 된다" 같은
문장이면 아직 TC 가 아닙니다. 화면에서 **눈으로 확인 가능한 것** 하나로 좁히세요.

> TC 를 여러 개 모아 문서로 남길 거라면 [`TC_TEMPLATE.md`](TC_TEMPLATE.md) 를 쓰세요.
> 위 메모의 확장판이고, 항목이 코드의 어디로 가는지까지 대응표가 있습니다.

### 1단계 — codegen 으로 화면 훑기

Locator 를 손으로 추측하지 마세요. 브라우저가 알려줍니다.

```bash
playwright codegen --target python-pytest https://staging.example.com/login
```

창이 두 개 뜹니다. 왼쪽 브라우저에서 **실제로 로그인을 해보면**,
오른쪽에 코드가 쌓입니다.

```python
page.get_by_label("아이디").fill("standard_user")
page.get_by_label("비밀번호").fill("...")
page.get_by_role("button", name="로그인").click()
```

사이트가 `data-testid` 대신 다른 속성을 쓴다면 알려주세요.

```bash
playwright codegen --test-id-attribute=data-qa https://...
```

> 같은 값을 `config/default.yaml` 의 `test_id_attribute` 에도 넣어야
> 테스트 코드의 `get_by_test_id()` 가 동일하게 동작합니다.

### 2단계 — codegen 출력을 **그대로 쓰지 않기**

codegen 은 초안입니다. 그대로 커밋하면 금방 깨집니다.

| codegen 이 뱉은 것 | 다듬은 것 | 이유 |
|---|---|---|
| `page.locator("#app > div:nth-child(2) > input")` | `page.get_by_label("아이디")` | 구조가 조금만 바뀌어도 깨짐 |
| `page.get_by_role("button").nth(3)` | `page.get_by_role("button", name="로그인")` | 버튼 순서는 언제든 바뀜 |
| `page.locator(".css-1a2b3c")` | 개발팀에 `data-testid` 요청 | 자동 생성 클래스는 빌드마다 바뀜 |

판단 기준은 하나입니다 — **"화면을 처음 보는 사람이 이 요소를 뭐라고 부를까?"**
그 이름으로 찾는 Locator 가 제일 안 깨집니다. 우선순위는 README 9장에 있습니다.

### 3단계 — Page Object 만들기

`pages/login_page.py`

```python
from playwright.sync_api import Locator
from pages.base_page import BasePage


class LoginPage(BasePage):
    path = "login"                      # base_url 뒤에 붙는 경로

    # --- Locator 는 전부 여기. 테스트 코드에는 쓰지 않는다 ---
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
        return self.username_input     # open() 이 이게 보일 때까지 기다린다

    # --- 동작 ---
    def login(self, username: str, password: str) -> "LoginPage":
        self.fill(self.username_input, username)
        self.fill(self.password_input, password)
        self.click(self.submit_button)
        return self
```

**`self.fill()` / `self.click()` 을 쓰는 이유**는 동작 하나하나가 로그에 남고,
그 로그가 실패 시 Evidence 로 저장되기 때문입니다.
로그가 필요 없는 곳은 Locator 를 직접 써도 됩니다.

### 4단계 — 테스트 쓰기

`tests/smoke/test_login.py`

```python
import pytest
from playwright.sync_api import Page, expect

from pages.login_page import LoginPage
from utils.steps import test_step


@pytest.mark.smoke                  # 실행 유형
@pytest.mark.login                  # 업무 영역 → 리포트 Category
@pytest.mark.tc_id("TC001")         # TC 관리 도구의 ID
def test_login_success(page: Page, run_config):
    """정상 로그인"""                # ← 리포트에 이 문장이 제목으로 나온다

    login = LoginPage(page)
    account = run_config.account("user")

    with test_step("로그인 화면 접속"):
        login.open()

    with test_step("아이디 / 비밀번호 입력 후 로그인"):
        login.login(account.username, account.password)

    with test_step("대시보드 확인"):
        expect(page.get_by_role("heading", name="대시보드")).to_be_visible()
```

리포트에는 이렇게 나옵니다.

```text
TC001  정상 로그인   Login   PASSED   2.40 sec
  1. 로그인 화면 접속            PASSED  0.62s
  2. 아이디 / 비밀번호 입력 후 로그인  PASSED  0.49s
  3. 대시보드 확인               PASSED  1.29s
```

> **함수 이름은 영문, 설명은 docstring 한글.**
> CI 로그가 깨지지 않고 `-k login` 같은 필터가 편해집니다.

### 5단계 — 눈으로 보면서 돌리기

처음 한 번은 반드시 브라우저를 띄워서 확인하세요.

```bash
pytest tests/smoke/test_login.py --headed --slowmo 500
```

### 6단계 — 막히면 멈춰 세우기

Locator 를 못 찾으면 그 줄 앞에 한 줄 넣습니다.

```python
page.pause()        # 여기서 멈추고 Inspector 가 열린다
```

```bash
pytest tests/smoke/test_login.py --headed
```

Inspector 의 **Pick locator** 버튼으로 화면 요소를 클릭하면
Playwright 가 권장하는 Locator 를 바로 알려줍니다. 확인 후 `page.pause()` 는 지웁니다.

### 7단계 — 안정성 확인

한 번 통과한 것은 증거가 아닙니다. **연속 3회**를 봅니다.

```bash
pytest tests/smoke/test_login.py --count 3     # pytest-repeat 설치 시
# 또는 그냥 세 번 실행
```

한 번이라도 흔들리면 [5장 Flaky 처방전](#5-flaky-처방전)으로 가세요.
**여기서 잡지 않으면 나중에 팀 전체의 시간을 먹습니다.**

### 8단계 — 커밋 전 점검

[7장 체크리스트](#7-pr-올리기-전-체크리스트)를 훑고 커밋합니다.

---

## 2. 손에 익혀야 할 도구 4가지

| 상황 | 도구 |
|---|---|
| 처음 보는 화면, Locator 를 모르겠다 | `playwright codegen` |
| 테스트가 뭘 하는지 눈으로 보고 싶다 | `--headed --slowmo 500` |
| 특정 지점의 화면 상태를 뜯어보고 싶다 | `page.pause()` |
| **이미 실패한 실행**의 원인을 찾겠다 | `playwright show-trace` |

### playwright codegen — 뼈대 뽑기

```bash
# 기본
playwright codegen --target python-pytest https://staging.example.com

# 파일로 저장
playwright codegen -o /tmp/draft.py --target python-pytest https://...

# 다른 브라우저로
playwright codegen -b firefox https://...

# testid 속성이 다른 사이트
playwright codegen --test-id-attribute=data-qa https://...
```

**로그인이 필요한 화면**은 로그인 상태를 저장해두고 재사용하면 편합니다.

```bash
# 1) 로그인까지 직접 해보고 세션 저장
playwright codegen --save-storage=auth_state/dev_user.json https://.../login

# 2) 다음부터는 로그인된 상태로 시작
playwright codegen --load-storage=auth_state/dev_user.json https://.../orders
```

이 파일 형식은 Base 의 `fixtures/auth.py` 가 쓰는 것과 같습니다 (README 14장).

### --headed --slowmo — 눈으로 보기

```bash
pytest tests/smoke/test_login.py --headed --slowmo 500
```

`--slowmo` 는 밀리초입니다. 200~500 이 보기 적당합니다.
`config/dev.yaml` 은 이미 `headless: false` 라 `--env=dev` 로도 브라우저가 뜹니다.

### page.pause() — 한 줄씩 멈춰 보기

```python
def test_something(page):
    login.open()
    page.pause()        # ← 여기서 멈춤
    login.login(...)
```

Inspector 에서 할 수 있는 것

- **Pick locator** — 요소 클릭 → 권장 Locator 확인
- **Step over** — 한 줄씩 진행
- 콘솔에서 Locator 즉석 실험

### playwright show-trace — 되감기

실패한 실행에는 이미 Trace 가 저장돼 있습니다.

```bash
playwright show-trace artifacts/20260906_133000/traces/TC001_test_login_chromium.zip
```

클릭 하나하나의 DOM 스냅샷, 네트워크, 콘솔을 타임라인으로 볼 수 있습니다.
**"내 PC 에선 되는데요"** 를 끝내는 도구입니다. CI 아티팩트에서 받아 열면 됩니다.

---

## 3. 무엇을 자동화하고 무엇을 안 하나

전부 자동화하려다 아무것도 못 믿게 되는 경우가 많습니다.

### 자동화하기 좋은 것

- 매 배포마다 확인해야 하는 **핵심 흐름** (로그인, 주문, 결제)
- 사람이 하면 지루하고 실수하기 쉬운 **반복 검증** (목록 100건 페이징)
- **회귀가 잦은 영역** — 예전에 깨진 적 있는 곳
- 데이터 조합이 많은 **입력값 검증** (`parametrize` + `data/*.yaml`)

### 자동화하지 말아야 할 것 (또는 나중에)

| 대상 | 이유 |
|---|---|
| 아직 개발 중이라 화면이 매주 바뀌는 기능 | 유지보수가 개발보다 비쌈 |
| "디자인이 예쁜지" 같은 주관적 판단 | 기준을 코드로 못 씀 |
| 1년에 한 번 쓰는 관리자 기능 | 투자 대비 회수 안 됨 |
| 외부 결제사 실제 승인 | 통제 불가. Mock 이나 API 로 대체 |
| 캡차 / SMS 인증 | 우회 자체가 목적이 되어버림. 테스트 계정 예외 요청 |

### TC 하나의 크기

**"실패했을 때 원인이 하나로 좁혀지는가?"** 로 판단합니다.

```python
# 나쁨 — 실패해도 어디가 문제인지 모른다
def test_전체_기능():
    로그인(); 상품검색(); 장바구니(); 주문(); 결제(); 취소()

# 좋음 — 각각 독립적으로 실패한다
def test_login_success(): ...
def test_search_by_keyword(): ...
def test_add_to_cart(): ...
```

업무 흐름 전체를 따라가야 하는 시나리오는 `tests/e2e/` 에 **한 함수 안에서**
이어지게 쓰고, 일반 TC 와 구분합니다.

---

## 4. 안티패턴 도감

리뷰에서 제일 자주 지적되는 것들입니다.

### ① `time.sleep()`

```python
# ✗
page.click("#save")
time.sleep(3)
assert page.locator("#toast").is_visible()

# ✓
page.get_by_role("button", name="저장").click()
expect(page.get_by_text("저장되었습니다")).to_be_visible()
```

3초는 느린 날엔 부족하고 빠른 날엔 낭비입니다. `expect()` 는 **조건이 만족될 때까지만**
기다립니다. 테스트 100개면 300초 차이가 납니다.

### ② `is_visible()` 로 즉시 단정

```python
# ✗ — 화면이 아직 안 그려졌을 뿐인데 실패한다
assert page.locator("#dashboard").is_visible()

# ✓
expect(page.get_by_role("heading", name="대시보드")).to_be_visible()
```

`is_visible()` 은 **그 순간**을 묻는 함수입니다. 분기 판단에만 쓰세요.

### ③ 테스트 코드에 Locator 직접 작성

```python
# ✗ — 화면 바뀌면 테스트 20개를 다 고쳐야 한다
def test_login(page):
    page.locator("#login-form input[name='id']").fill("hong")

# ✓ — Page Object 한 군데만 고치면 된다
def test_login(page):
    LoginPage(page).login("hong", pw)
```

### ④ XPath / 인덱스 의존

```python
# ✗
page.locator("//div[@class='form']/div[2]/input")
page.get_by_role("row").nth(3)

# ✓
page.get_by_label("아이디")
page.get_by_role("row", name="ORD-001")
```

### ⑤ 테스트 간 의존

```python
# ✗ — 단독 실행하면 깨지고, 병렬 실행하면 무작위로 깨진다
def test_01_create_order():
    global order_id
    order_id = ...

def test_02_cancel_order():
    cancel(order_id)          # 앞 테스트가 돌았다고 가정

# ✓ — 필요한 데이터는 자기가 만든다 (API 로 하면 빠르다)
def test_cancel_order(page, order_api):
    order = order_api.create()
    try:
        ...
    finally:
        order_api.delete(order["id"])
```

### ⑥ URL / 계정 하드코딩

```python
# ✗ — 환경 바뀌면 코드를 고쳐야 한다
page.goto("https://staging.example.com/login")
page.fill("#pw", "Test1234!")

# ✓
login.open()                              # base_url 은 config 에서
account = run_config.account("user")      # 비밀번호는 .env 에서
```

비밀번호를 코드에 쓰면 **Git 이력에 영원히 남습니다.** 지워도 남습니다.

### ⑦ try/except 로 실패 숨기기

```python
# ✗ — 깨져도 초록불이 뜬다. 자동화 신뢰가 무너지는 지름길
try:
    expect(page.get_by_text("완료")).to_be_visible()
except Exception:
    pass

# ✓ — 조건부 흐름이면 의도를 드러낸다
if page.get_by_role("dialog").is_visible():
    page.get_by_role("button", name="닫기").click()
expect(page.get_by_text("완료")).to_be_visible()
```

### ⑧ 검증 없는 테스트

```python
# ✗ — 클릭만 하고 끝. 아무것도 보장하지 않는다
def test_save(page):
    form.open()
    form.fill_all()
    form.submit()

# ✓
    expect(page.get_by_text("저장되었습니다")).to_be_visible()
```

### ⑨ 한 테스트에 검증 20개

실패하면 첫 번째에서 멈춰 나머지는 확인도 못 합니다.
**목적이 다르면 테스트를 나누세요.** 같은 목적의 묶음 검증은 괜찮습니다.

### ⑩ Step 을 너무 잘게 쓰기

```python
# ✗ — 리포트가 읽기 어려워진다
with test_step("아이디 필드 클릭"): ...
with test_step("아이디 입력"): ...
with test_step("비밀번호 필드 클릭"): ...

# ✓ — 사람이 TC 문서에 쓸 단위로
with test_step("아이디 / 비밀번호 입력 후 로그인"): ...
```

Step 은 **TC 명세서의 절차 한 줄**에 대응한다고 생각하면 적당합니다
([TC 명세 양식](TC_TEMPLATE.md)).

---

## 5. Flaky 처방전

가끔 실패하는 테스트는 **버그보다 나쁩니다.** 아무도 결과를 안 믿게 되니까요.

| 증상 | 흔한 원인 | 처방 |
|---|---|---|
| 요소를 못 찾음 (가끔) | 로딩 전에 찾음 | `expect(...).to_be_visible()` 로 기다리기 |
| 클릭이 먹지 않음 | 로딩 오버레이가 덮고 있음 | 오버레이가 사라질 때까지: `expect(spinner).to_be_hidden()` |
| 텍스트 비교 실패 | 공백/줄바꿈 차이 | `to_contain_text()` 또는 정규식 |
| 목록 개수 불일치 | 이전 테스트 데이터 잔존 | 테스트가 자기 데이터를 만들고 지우게 |
| 병렬(`-n`)에서만 실패 | 같은 계정/데이터를 공유 | 계정·데이터를 테스트마다 분리 |
| 첫 실행만 실패 | 캐시 워밍업 | 사전조건을 API 로 만들기 |
| CI 에서만 실패 | 화면 크기·속도 차이 | `viewport` 고정 확인, Trace 로 CI 화면 확인 |
| 특정 요소만 **늘** 못 찾음 | 뷰포트에 따라 DOM 이 통째로 다름 (모바일 드로어 ↔ 데스크톱) | 조사할 때의 창 크기를 `config` 의 `viewport` 와 맞추기 ([9장](#9-claude-와-함께-쓰기)) |
| 시간이 지나면 실패 | 날짜 하드코딩 | 상대 날짜 사용 (`오늘+1일`) |

### 재시도로 덮지 마세요

```bash
pytest --reruns 1     # CI 에서 파이프라인이 빨개지는 것만 막는 용도
```

기본값은 **0** 입니다. 재시도로 통과한 테스트는 리포트에 `retry 1` 배지가 붙고
`result.json` 의 `tests[].retries` 에 남습니다. **이 목록을 주기적으로 보고 고치세요.**
재시도는 시간을 버는 것이지 문제를 없애는 게 아닙니다.

---

## 6. 실패했을 때 보는 순서

```dot
1. Custom Report 의 Failed Tests 영역
   → 실패 사유 한 줄 + Step 어디서 멈췄는지
        ↓ 원인이 안 보이면
2. Screenshot 썸네일 클릭
   → 그 순간 화면이 기대와 다른가? (에러 팝업? 로그인 풀림? 빈 목록?)
        ↓ 화면만으론 모르겠으면
3. playwright show-trace <trace.zip>
   → 클릭 전후 DOM, 네트워크 응답, 콘솔 에러
        ↓ 그래도 모르겠으면
4. Page HTML + Log
   → 실제 DOM 구조 / 어느 Step 까지 진행됐는지
        ↓
5. 로컬에서 --headed --slowmo 500 으로 재현
```

**1번에서 3번 사이에 대부분 끝납니다.** 처음부터 로컬 재현부터 시도하면 시간을 버립니다.

리포트 위치는 실행이 끝나면 터미널에 나오고, 마지막 실행은
`artifacts/latest_run.txt` 에 적혀 있습니다.

---

## 7. PR 올리기 전 체크리스트

**테스트 코드**

- [ ] 함수 이름 영문 / docstring 에 한글 설명 (리포트 제목이 됨)
- [ ] `@pytest.mark.tc_id(...)` 와 업무 영역 marker 를 붙였다
- [ ] Locator 가 테스트 코드에 없다 (전부 Page Object 안)
- [ ] `time.sleep()` 이 없다
- [ ] 단정은 `expect()` 로 했다 (`assert ...is_visible()` 아님)
- [ ] URL / 계정 / 타임아웃 하드코딩이 없다
- [ ] `page.pause()`, `print()`, 주석 처리한 코드가 남아 있지 않다

**독립성**

- [ ] 이 테스트만 단독 실행해도 통과한다
      `pytest tests/.../test_x.py::test_y`
- [ ] 병렬 실행에서도 통과한다 — `pytest -n 2`
- [ ] 연속 3회 통과한다

**전체**

- [ ] `pytest` 전체가 통과한다
- [ ] 새 marker 를 만들었으면 `pytest.ini` 에 등록했다 (`--strict-markers`)
- [ ] 테스트 데이터는 `data/` 에 있다 (코드에 박혀 있지 않다)
- [ ] `.env` 나 실제 비밀번호를 커밋하지 않았다

**한 번 더**

- [ ] 실패했을 때 리포트만 보고 원인을 알 수 있는가?
      (Step 이름이 "1단계", "확인" 같이 무의미하지 않은지)

---

## 8. 명령어 치트시트

```bash
# ─── 작성 ─────────────────────────────────────────────
playwright codegen --target python-pytest <url>   # Locator 뽑기
playwright codegen --test-id-attribute=data-qa <url>
playwright codegen --save-storage=auth_state/dev_user.json <url>

# ─── 실행 ─────────────────────────────────────────────
pytest                                    # 전체
pytest -m smoke                           # 유형별
pytest tests/smoke/test_login.py          # 파일
pytest tests/smoke/test_login.py::test_login_success
pytest -k "login and not admin"           # 이름으로
pytest --env=dev --browser=firefox        # 환경/브라우저
pytest --headed --slowmo 500              # 눈으로 보기
pytest -n 4                               # 병렬
pytest -x                                 # 첫 실패에서 멈춤
pytest --lf                               # 실패한 것만 다시
pytest -m failure_demo                    # Evidence 동작 확인용 (의도적 실패)
pytest -m base_unit                       # Base 자체 회귀 테스트 (브라우저 없음)

# ─── 디버깅 ───────────────────────────────────────────
page.pause()                              # 코드에 한 줄 넣고 --headed
playwright show-trace <trace.zip>         # 실패 되감기

# ─── 결과 ─────────────────────────────────────────────
cat artifacts/latest_run.txt              # 마지막 실행 폴더
start <위 경로>\report\report.html        # Custom Report (Windows)
python -m reporting.ci_summary            # Markdown 요약
```

---

## 9. Claude 와 함께 쓰기

이 Base 위에서 **Claude Code 가 TC 정의 이후를 끝까지 할 수 있는지** 실제 로그인 사이트로
검증했습니다. 결론은 "된다" 이고, 대신 **사람이 반드시 붙잡아야 하는 자리**가 있습니다.

### 단계별로 누가 하나

1장의 8단계에 그대로 대응합니다.

| 단계 | 담당 | 왜 |
|---|---|---|
| 0. 대상 정하기 | **사람** | 무엇을 검증할 가치가 있는지는 업무 지식입니다. TC 가 없으면 Claude 도 못 씁니다 |
| 1. 화면 훑기 | Claude | 아래 「codegen 경로가 둘이다」 |
| 2. Locator 다듬기 | Claude | 1단계와 합쳐집니다 |
| 3. Page Object | Claude | |
| 4. 테스트 쓰기 | Claude | 0단계에서 사람이 쓴 TC 를 그대로 옮깁니다 |
| 5. 눈으로 보며 돌리기 | **갈림** | "테스트가 도는가" 는 Claude, **"이 화면이 업무적으로 맞는가" 는 사람** |
| 6. 막히면 멈춰 세우기 | Claude | |
| 7. 안정성 확인 | Claude 실행 / **사람 판정** | 아래 「사람이 반드시 볼 것」 |
| 8. 커밋 전 점검 | Claude 실행 / **사람 판정** | |

**0단계와 5단계 후반이 사람의 자리입니다.** 나머지는 넘겨도 됩니다.

### codegen 경로가 둘이다

Claude 는 `playwright codegen` 창을 띄워 사람처럼 클릭할 수 없습니다.
대신 **Playwright MCP** 가 같은 역할을 합니다 — 실행한 Playwright 코드를 그대로
돌려주기 때문입니다.

| | 사람 | Claude |
|---|---|---|
| 도구 | `playwright codegen <url>` | Playwright MCP |
| 방식 | 브라우저에서 직접 조작하면 코드가 쌓임 | 접근성 트리를 읽고 요소를 지목 |
| 출력 | 다듬어야 함 (2단계 필요) | **이미 깨끗함 (1·2단계가 하나)** |

접근성 트리에서 요소를 고르므로 `#app > div:nth-child(2)` 같은 것이 **애초에 안 나옵니다.**
그래서 Claude 에게는 1단계와 2단계의 구분이 없습니다.

```text
browser_navigate    →  화면 열기
browser_snapshot    →  접근성 트리에서 역할·이름 확보   (= Locator 1·2순위)
browser_click/type  →  상호작용 후 구조가 어떻게 변하는지
browser_evaluate    →  data-testid 등 접근성 트리에 안 나오는 속성
```

검증: TodoMVC 에서 **기존 코드를 보지 않고** 뽑은 Locator 8개가
`pages/example_page.py` 와 8/8 일치했습니다.

### MCP 의 한계 3가지

**① MCP 브라우저는 `pytest` 와 별개입니다.** 세션·쿠키가 공유되지 않습니다.
Locator 조사 도구이지 테스트 실행 대체재가 아닙니다. 확인은 반드시 `pytest` 로 하세요.

**② 커스텀 엘리먼트는 `get_by_role()` 로 안 잡힙니다.** 접근성 트리에 `generic` 으로만
보입니다. 네이티브 요소가 아니므로 상태 단정도 다르게 해야 합니다.

```python
# 제출 버튼이 <button> 이 아니라 <qm-button data-cy="submit"> 인 경우

# ✗ 역할이 없어서 못 찾는다
page.get_by_role("button", name="제출")

# ✗ 네이티브 button 이 아니라 disabled 상태를 이렇게는 못 읽는다
expect(submit).to_be_disabled()

# ✓ 속성을 직접 본다
expect(page.get_by_test_id("submit")).to_have_attribute("disabled", "true")
```

**③ 작업 폴더에 `.playwright-mcp/` 를 만듭니다.** `.gitignore` 에 이미 넣어뒀습니다.

### 규칙 — 조사 뷰포트를 테스트 뷰포트와 맞추세요

**실제로 한 번 실패한 사례입니다.** 좁은 창에서 Locator 를 조사한 뒤 1920 으로 테스트를
돌렸더니 그 요소가 아예 없었습니다. 같은 브라우저·같은 로그인 세션에서 **폭만 바꿔**
재현했습니다.

```text
좁은 폭 (모바일 드로어)  ->  data-cy="logout-btn"   있음 / my-page-btn  없음
1920x1080 (데스크톱)     ->  data-cy="my-page-btn"  있음 / logout-btn   없음
```

뷰포트에 따라 DOM 이 **통째로 달라지는** 사이트가 있습니다.
조사를 시작하기 전에 창 크기를 `config` 의 `viewport`(기본 1920x1080)에 맞추세요.
MCP 라면 `browser_resize` 를 먼저 부릅니다.
[5장 Flaky 처방전](#5-flaky-처방전)의 같은 항목과 이어집니다.

### 사람이 반드시 볼 것 — 실행 결과 3종

Claude 가 쓴 "통과했습니다" 라는 문장은 증거가 아닙니다. **출력을 보세요.**

```bash
pytest tests/smoke/test_login.py::test_login_success   # 단독
pytest -n 2                                            # 병렬
# 연속 3회
```

[7장 체크리스트](#7-pr-올리기-전-체크리스트)의 「독립성」 항목과 같은 것입니다.
이 셋을 통과하지 못한 테스트는 나중에 팀 전체의 시간을 먹습니다.

> **Claude 에게 주는 규칙:** 실행 결과를 요약하지 말고 **터미널 출력을 그대로** 붙일 것.
> 파일 하나만 돌려보고 "검증 완료" 라고 보고했다가 전체 실행에서 깨진 사례가 있었습니다.

### 규칙은 `CLAUDE.md` 에 있습니다

저장소 루트의 [`CLAUDE.md`](../CLAUDE.md) 에 Claude 가 지킬 규칙(Locator 우선순위,
안티패턴, 손대면 안 되는 파일, 커밋 전 게이트)이 들어 있습니다. Claude Code 는 그 파일을
자동으로 읽습니다.

**사람이 읽을 설명은 이 가이드에, Claude 가 지킬 규칙은 `CLAUDE.md` 에** 두고 서로
링크만 겁니다. 같은 내용을 두 군데 쓰면 반드시 어긋납니다.

---

## 더 볼 곳

| 알고 싶은 것 | 위치 |
|---|---|
| 설치 / 실행 옵션 전체 | [README 1~2장](../README.md) |
| Locator 우선순위 근거 | [README 9장](../README.md) |
| Popup / iframe / 다운로드 / Dialog | [README 13장](../README.md) + `tests/example/test_interactions_example.py` |
| BasePage 가 주는 메서드 전체 | `tests/example/test_base_page_example.py` |
| 로그인 세션 재사용 | [README 14장](../README.md) + `tests/example/test_role_session_example.py` |
| API 로 사전조건 만들기 | [README 15장](../README.md) + `tests/example/test_api_example.py` |
| result.json 스키마 (외부 연동) | [`reporting/result_schema.md`](../reporting/result_schema.md) |
| 새 고객사 프로젝트 시작 | [README 18장](../README.md) |
| TC 명세 양식 (사람이 TC 를 쓸 때) | [`TC_TEMPLATE.md`](TC_TEMPLATE.md) |
| Claude 가 지킬 규칙 (요약본) | [`CLAUDE.md`](../CLAUDE.md) |
