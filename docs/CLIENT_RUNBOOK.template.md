# 실행 가이드 — 고객사 전달용 템플릿

> ## ⚠ 이 블록은 전달 전에 지우세요
>
> 이 파일은 **Base 에 있는 템플릿**입니다. 고객사 프로젝트 저장소로 복사한 뒤
> `docs/RUNBOOK.md` 로 이름을 바꾸고, `{{ }}` 로 표시된 빈칸을 채우고,
> **이 블록을 지운 것**이 고객사에 전달할 문서입니다.
> (원본을 `.template.md` 로 남겨두는 이유는 Base 가 갱신됐을 때 대조하기 위해서입니다.)
>
> ```bash
> cp docs/CLIENT_RUNBOOK.template.md docs/RUNBOOK.md
> grep -n "{{" docs/RUNBOOK.md      # 남은 빈칸 확인
> ```
>
> **채울 빈칸**
>
> | 빈칸 | 무엇을 넣나 |
> |---|---|
> | `{{프로젝트명}}` | `config/default.yaml` 의 `project_name` 과 같게 |
> | `{{대상 사이트}}` | 무엇을 테스트하는지 한 줄 |
> | `{{저장소 URL}}` | 고객사가 clone 할 주소 |
> | `{{환경명}}` | 주로 쓰는 환경 (`dev` / `staging` / `prod`) |
> | `{{업무 marker 표}}` | `pytest.ini` 의 업무 영역 marker 를 고객사 용어로 |
> | `{{계정 발급}}` | `.env` 에 넣을 계정을 어디서 받나 |
> | `{{실행 주기}}` | 누가 언제 돌리나 / 리포트를 언제 받나 |
> | `{{담당자}}` | 이름 · 연락처 · 회신 채널 |
>
> **독자가 두 종류입니다.**
>
> - **직접 돌리는 담당자** — 이 문서 전체를 줍니다.
> - **리포트만 받아보는 관리자** — **4장만** 잘라서 줍니다
>   (4장 시작·끝에 `✂` 표시가 있습니다). 설치·실행 절은 필요 없습니다.
>
> 4장을 잘라 보낼 때는 **실행 폴더 전체를 압축**해서 보내세요. 이유는 4장 안의
> 「보낼 때 주의」에 적혀 있고, 그 문장은 관리자도 읽어야 하므로 지우지 마세요.

---

# {{프로젝트명}} 자동화 테스트 실행 가이드

{{대상 사이트}} 의 UI 를 자동으로 검증합니다. 이 문서는 **테스트를 돌리고 결과를 보는
방법**만 다룹니다. 테스트를 새로 만드는 방법은 자동화 담당자용 문서(`README.md`)에
있습니다.

| | |
|---|---|
| 대상 | {{대상 사이트}} |
| 기본 환경 | `{{환경명}}` |
| 실행 주기 | {{실행 주기}} |
| 문의 | {{담당자}} |

---

## 1. 준비물

| | 비고 |
|---|---|
| Python 3.10 이상 | `python --version` 으로 확인 |
| Git | 저장소를 받을 때만 |
| 대상 사이트 접근 | 사내망·VPN 이 필요하면 미리 확인하세요 |
| 테스트 계정 | {{계정 발급}} |

브라우저는 따로 설치하지 않아도 됩니다. 2장에서 자동화 전용 브라우저를 내려받습니다
(**PC 에 설치된 Chrome 과는 별개**이고, 기존 브라우저에 영향을 주지 않습니다).

---

## 2. 최초 1회 설치

```bash
git clone {{저장소 URL}}
cd {{프로젝트명}}

# 1) 가상환경
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2) 패키지 설치 (검증된 버전 조합)
pip install -r requirements.lock

# 3) 자동화용 브라우저 설치 — 최초 1회, 용량이 큽니다 (수백 MB)
playwright install

# 4) 환경설정 파일
#   Windows
copy .env.example .env
#   macOS / Linux
cp .env.example .env
```

만든 `.env` 를 열어 **계정 비밀번호만** 채웁니다. 나머지 항목은 주석 처리된 채로
두세요 — 주석을 풀면 환경별 설정(`config/{{환경명}}.yaml`)이 무시됩니다.

```bash
ENV={{환경명}}
USER_PASSWORD=발급받은_비밀번호
```

> `.env` 는 Git 에 올라가지 않습니다. **비밀번호를 다른 파일에 적지 마세요.**

설치가 끝났는지 확인:

```bash
pytest -m smoke
```

---

## 3. 실행

```bash
pytest
```

| 하고 싶은 것 | 명령 |
|---|---|
| 전체 | `pytest` |
| 핵심 기능만 빠르게 | `pytest -m smoke` |
| 회귀 전체 | `pytest -m regression` |
| 업무 흐름 시나리오 | `pytest -m e2e` |
| 업무 영역별 | `pytest -m {{업무 marker 표}}` |
| 브라우저를 눈으로 보며 | `pytest --headed` |
| 천천히 보며 | `pytest --headed --slowmo 500` |
| 다른 환경 | `pytest --env=prod` |
| 빠르게 (병렬) | `pytest -n 4` |

끝나면 콘솔에 요약이 나오고, 마지막 줄에 리포트 경로가 찍힙니다.

```text
Total   : 21
Passed  : 21
Failed  : 0
Pass Rate : 100.0%

Custom Report:
  ...\artifacts\20260906_142212\report\report.html
```

**전부 Passed 인 것이 정상입니다.** 하나라도 Failed 면 4장·5장을 보세요.

---

<!-- ✂ ---------- 여기부터 : 리포트만 받아보는 분께 잘라서 전달 ---------- ✂ -->

## 4. 결과 보기

실행이 끝나면 `artifacts/<실행시각>/report/` 에 3개가 생깁니다.

```text
artifacts/20260906_133000/report/
├─ report.html          ← 이것을 보세요
├─ pytest_report.html   ← 자동화 담당자용 (오류 상세)
└─ result.json          ← 프로그램이 읽는 결과 데이터
```

`report.html` 을 브라우저로 열기만 하면 됩니다. 마지막 실행 폴더 이름은
`artifacts/latest_run.txt` 에 적혀 있습니다.

```bash
# Windows
start artifacts\20260906_133000\report\report.html
# macOS
open artifacts/20260906_133000/report/report.html
```

### 화면에서 볼 것

| 위치 | 무엇 |
|---|---|
| 상단 Dashboard | 언제 · 어느 환경 · 어느 URL 을 · 얼마나 걸려 검증했나 |
| Pass Rate | **100% 가 아니면 실패가 있다는 뜻**입니다 |
| Category 별 결과 | 업무 영역별 통계 — 어느 업무가 깨졌는지 |
| Failed Tests | 실패한 것만 모아 보여줍니다 (아래 참고) |
| 전체 테스트 표 | 필터(All/Passed/Failed/Skipped) · 검색. 행을 누르면 수행 절차가 펼쳐집니다 |

### 실패를 발견했을 때

Failed Tests 영역에 실패마다 이만큼이 붙어 있습니다.

- **실패 사유** — 무엇을 기대했는데 무엇이었는지
- **실패 시점 URL** — 어느 화면에서 멈췄는지
- **Screenshot 썸네일** — 클릭하면 확대됩니다. 실패한 순간의 화면입니다
- **Trace / HTML / Log 링크** — 자동화 담당자가 원인을 파고들 때 씁니다

버그로 보이면 **Screenshot 과 실패 시점 URL** 을 담당자에게 알려주세요. 그 두 개면
대부분 재현이 됩니다.

> ### 보낼 때 주의 — 폴더째 압축해서 보내세요
>
> `report.html` 은 외부 라이브러리를 쓰지 않아 파일 하나만으로도 화면이 열립니다.
> 다만 **Screenshot 썸네일과 Trace / HTML / Log 링크는 같은 실행 폴더 안의 파일을
> 가리킵니다.** `report.html` 만 떼어 보내면 그림이 깨지고 링크가 죽습니다.
>
> **`artifacts/20260906_133000/` 폴더 전체를 압축**해서 보내고, 받은 쪽은 풀어서
> `report/report.html` 을 여세요.

<!-- ✂ ---------- 여기까지 ---------- ✂ -->

---

## 5. 실패 원인 파악하기 (자동화 담당자용)

실패하면 아무 설정 없이 아래가 자동으로 남습니다.

```text
artifacts/20260906_133000/
├─ screenshots/TC001_test_login_chromium.png     실패 순간 화면
├─ traces/     TC001_test_login_chromium.zip     되감아 보는 기록
├─ html/       TC001_test_login_chromium.html    그 시점 페이지
├─ logs/       TC001_test_login_chromium.log     그 테스트 로그
└─ logs/       run.log                           실행 전체 로그
```

파일 이름이 `TC ID + 테스트명 + 브라우저` 라서 어느 테스트 것인지 바로 알 수 있습니다.

제일 강력한 것은 **Trace** 입니다. 클릭 하나하나의 화면·네트워크·콘솔을 타임라인으로
되감아 볼 수 있습니다.

```bash
playwright show-trace artifacts/20260906_133000/traces/TC001_test_login_chromium.zip
```

눈으로 보고 싶으면:

```bash
pytest tests/... --headed --slowmo 500
```

### 결과 폴더는 자동으로 정리됩니다

`artifacts/` 는 회당 수십 MB 씩 쌓입니다. 그래서 실행을 시작할 때 **보관 기간이 지난
폴더를 지웁니다** (기본 14일, 기간이 지나도 최근 5개는 남김).

```bash
# .env 에서 바꿀 수 있습니다
ARTIFACTS_KEEP_DAYS=30
ARTIFACTS_KEEP_MIN_RUNS=5
```

**남겨야 할 결과는 폴더째 다른 곳에 복사해두세요.** `artifacts/` 는 Git 에 올라가지
않습니다.

---

## 6. 자주 겪는 문제

| 증상 | 해결 |
|---|---|
| `playwright: command not found` | 가상환경을 활성화하지 않았습니다. `.venv\Scripts\activate` (Windows) / `source .venv/bin/activate` |
| `Executable doesn't exist ...` | `playwright install` 을 안 했습니다 (2장 3번) |
| 설치 중 `WinError 206` | Windows 경로 260자 제한입니다. 프로젝트를 `C:\work\...` 같은 짧은 경로로 옮기세요 |
| 콘솔에 한글이 깨짐 | `set PYTHONUTF8=1` (PowerShell 은 `$env:PYTHONUTF8=1`). 리포트 파일은 항상 UTF-8 이라 영향 없습니다 |
| 로그인 테스트만 전부 실패 | `.env` 의 비밀번호를 확인하세요. 계정 잠김·만료도 자주 있는 원인입니다 |
| 전부 실패 / 접속 자체가 안 됨 | 대상 사이트가 열려 있는지, 사내망·VPN 이 필요한지 확인하세요 |
| 가끔만 실패 | 그 테스트의 Trace 를 담당자에게 보내주세요. 테스트 쪽 문제일 수 있습니다 |
| `'qa' 는 invalid choice` | `--env` 는 `dev` / `staging` / `prod` 만 됩니다 |
| `.env` 값이 안 먹는 것 같음 | CLI 옵션이 `.env` 보다 강합니다. `.env` 는 `config/*.yaml` 보다 강합니다 |

---

## 7. 문의

| | |
|---|---|
| 담당자 | {{담당자}} |
| 실행 주기 | {{실행 주기}} |
| 계정 발급 | {{계정 발급}} |

문의할 때 **실행 폴더(`artifacts/<실행시각>/`)를 압축해서 첨부**해주시면 가장 빠릅니다.
