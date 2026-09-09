# 실행방법 — 고객사 전달용 템플릿

> ## ⚠ 이 블록은 전달 전에 지우세요
>
> 이 파일은 **Base 에 있는 템플릿**입니다. 고객사 프로젝트 저장소로 복사한 뒤
> `docs/RUN.md` 로 이름을 바꾸고, `{{ }}` 로 표시된 빈칸을 채우고,
> **이 블록을 지운 것**이 고객사에 전달할 문서입니다.
> (원본을 `.template.md` 로 남겨두는 이유는 Base 가 갱신됐을 때 대조하기 위해서입니다.)
>
> ```bash
> cp docs/CLIENT_RUN.template.md docs/RUN.md
> grep -n "{{" docs/RUN.md      # 남은 빈칸 확인
> ```
>
> **채울 빈칸**
>
> | 빈칸 | 무엇을 넣나 |
> |---|---|
> | `{{프로젝트명}}` | `config/default.yaml` 의 `project_name` 과 같게 |
> | `{{환경명}}` | 주로 쓰는 환경 (`dev` / `staging` / `prod`) |
> | `{{업무 marker 표}}` | 아래 「업무 영역별」 표를 **이 프로젝트에 실제로 있는 marker 로** 바꾸세요. `pytest.ini` 의 업무 영역 marker 를 고객사 용어로 적습니다 |
> | `{{실행 주기}}` | 누가 언제 돌리나 |
> | `{{담당자}}` | 이름 · 연락처 · 회신 채널 |
>
> **없는 marker 를 문서에 남겨두면 오류가 나지 않습니다.** `pytest -m 없는marker` 는
> `no tests collected` 로 조용히 끝납니다(종료코드 5). 고객사는 "돌렸는데 아무 일도
> 안 일어난다" 로 겪게 되므로, 표를 반드시 실제 marker 로 맞추세요.
>
> **이 문서는 「매번 하는 일」만 담습니다.** 최초 1회 설치는 `docs/SETUP.md` 에
> 있습니다. 두 문서를 같이 전달하세요.

---

# {{프로젝트명}} 자동화 테스트 — 실행방법

설치가 끝난 뒤 **테스트를 돌리는 방법**입니다. 아직 설치를 안 했다면
`docs/SETUP.md` 를 먼저 보세요.

| | |
|---|---|
| 기본 환경 | `{{환경명}}` |
| 실행 주기 | {{실행 주기}} |
| 문의 | {{담당자}} |

---

## 1. 먼저 — 가상환경 활성화

**터미널을 새로 열 때마다 필요합니다.** 이걸 빠뜨리는 것이 가장 흔한 실수입니다.

```bash
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

프롬프트 앞에 `(.venv)` 가 보이면 준비된 것입니다.

---

## 2. 실행

```bash
pytest
```

이게 전부입니다. 옵션 없이 돌리면 `{{환경명}}` 환경에서 전체 테스트가 돕니다.

---

## 3. 무엇을 돌릴지 고르기

| 하고 싶은 것 | 명령 |
|---|---|
| 전체 | `pytest` |
| 핵심 기능만 빠르게 | `pytest -m smoke` |
| 회귀 전체 | `pytest -m regression` |
| 업무 흐름 시나리오 | `pytest -m e2e` |
| 업무 영역별 | `pytest -m {{업무 marker 표}}` |
| 특정 파일만 | `pytest tests/smoke/test_login.py` |

> 여러 개를 조합할 수 있습니다. `pytest -m "smoke and login"` 은 둘 다 붙은 것만,
> `pytest -m "smoke or login"` 은 둘 중 하나라도 붙은 것을 돌립니다.

---

## 4. 어떻게 돌릴지 고르기

| 하고 싶은 것 | 명령 | 비고 |
|---|---|---|
| 브라우저를 눈으로 보며 | `pytest --headed` | 무엇을 하는지 보입니다 |
| 천천히 보며 | `pytest --headed --slowmo 500` | 동작마다 0.5초 쉽니다 |
| 다른 환경에서 | `pytest --env=prod` | `dev` / `staging` / `prod` 만 됩니다 |
| 다른 브라우저로 | `pytest --browser=firefox` | `chromium` / `firefox` / `webkit` |
| 빠르게 (병렬) | `pytest -n 4` | 아래 주의를 보세요 |

### 병렬 실행(`-n`) 주의

`-n` 값은 **PC 물리 코어 수의 절반**을 권합니다. 그 이상은 서로 CPU 를 뺏느라
오히려 느려지고, 원래 통과하던 테스트가 가끔 실패하기 시작합니다.
메모리도 워커 1개당 약 300 MB 를 더 씁니다.

### 옵션이 서로 부딪히면

오른쪽이 셉니다. **명령에 직접 준 옵션이 항상 이깁니다.**

```text
config/default.yaml  <  config/<환경>.yaml  <  .env  <  실행할 때 준 옵션
```

---

## 5. 끝나면

콘솔에 요약이 나오고, 마지막에 리포트 경로가 찍힙니다.

```text
Total   : 21
Passed  : 21
Failed  : 0
Pass Rate : 100.0%

Custom Report:
  ...\artifacts\20260906_142212\report\report.html
```

**전부 Passed 인 것이 정상입니다.**

리포트는 브라우저로 열기만 하면 됩니다. 마지막 실행 폴더 이름은
`artifacts/latest_run.txt` 에도 적혀 있습니다.

```bash
# Windows
start artifacts\20260906_142212\report\report.html
# macOS
open artifacts/20260906_142212/report/report.html
```

> **결과를 남에게 보낼 때는 `artifacts/<실행시각>/` 폴더 전체를 압축**해서 보내세요.
> `report.html` 안의 스크린샷과 링크가 같은 폴더의 파일을 가리키기 때문에,
> 파일 하나만 떼어 보내면 그림이 깨지고 링크가 죽습니다.

> `artifacts/` 는 실행할 때마다 쌓이므로 **보관 기간이 지난 폴더는 자동으로
> 지워집니다** (기본 14일, 기간이 지나도 최근 5개는 남김).
> **남겨야 할 결과는 폴더째 다른 곳에 복사해두세요.**

---

## 6. 실행이 안 될 때

| 증상 | 해결 |
|---|---|
| `pytest: command not found` | 가상환경을 활성화하지 않았습니다 (1장) |
| `argument --env: invalid choice: 'qa'` | `--env` 는 `dev` / `staging` / `prod` 만 됩니다 |
| `no tests collected` — 아무것도 안 돌고 끝남 | `-m` 에 없는 marker 를 줬습니다. **오류가 아니라 조용히 0건**이니 3장 표의 이름과 철자를 확인하세요 |
| 전부 실패 / 접속 자체가 안 됨 | 대상 사이트가 열려 있는지, 사내망·VPN 이 필요한지 확인하세요 |
| 로그인 관련만 전부 실패 | `.env` 의 비밀번호를 확인하세요. 계정 잠김·만료도 자주 있는 원인입니다 |
| `.env` 에 넣은 값이 안 먹음 | 명령에 준 옵션이 `.env` 보다 셉니다 (4장 우선순위) |
| 가끔만 실패 | 그 실행 폴더를 압축해 {{담당자}} 에게 보내주세요. 테스트 쪽 문제일 수 있습니다 |
| 콘솔에 한글이 깨짐 | `set PYTHONUTF8=1` (PowerShell 은 `$env:PYTHONUTF8=1`). 리포트 파일은 영향 없습니다 |

문의할 때 **실행 폴더(`artifacts/<실행시각>/`)를 압축해서 첨부**해주시면 가장 빠릅니다.
