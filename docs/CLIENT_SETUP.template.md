# 환경 구성 — 고객사 전달용 템플릿

> ## ⚠ 이 블록은 전달 전에 지우세요
>
> 이 파일은 **Base 에 있는 템플릿**입니다. 고객사 프로젝트 저장소로 복사한 뒤
> `docs/SETUP.md` 로 이름을 바꾸고, `{{ }}` 로 표시된 빈칸을 채우고,
> **이 블록을 지운 것**이 고객사에 전달할 문서입니다.
> (원본을 `.template.md` 로 남겨두는 이유는 Base 가 갱신됐을 때 대조하기 위해서입니다.)
>
> ```bash
> cp docs/CLIENT_SETUP.template.md docs/SETUP.md
> grep -n "{{" docs/SETUP.md      # 남은 빈칸 확인
> ```
>
> **채울 빈칸**
>
> | 빈칸 | 무엇을 넣나 |
> |---|---|
> | `{{프로젝트명}}` | `config/default.yaml` 의 `project_name` 과 같게 (사람이 읽는 이름) |
> | `{{대상 사이트}}` | 무엇을 테스트하는지 한 줄 |
> | `{{저장소 URL}}` | 고객사가 clone 할 주소 |
> | `{{저장소 폴더명}}` | **`git clone` 이 만드는 폴더 이름**입니다. 저장소 URL 의 마지막 조각에서 `.git` 을 뗀 것이고, 공백이 들어가는 `{{프로젝트명}}` 과 다릅니다 |
> | `{{환경명}}` | 주로 쓰는 환경 (`dev` / `staging` / `prod`) |
> | `{{계정 발급}}` | `.env` 에 넣을 계정을 어디서 받나 |
> | `{{담당자}}` | 이름 · 연락처 · 회신 채널 |
>
> **이 문서는 「한 번만 하는 일」만 담습니다.** 매번 하는 일(어떤 명령으로 돌리고
> 결과를 어디서 보나)은 `docs/RUN.md` 에 있습니다. 두 문서를 같이 전달하세요.

---

# {{프로젝트명}} 자동화 테스트 — 환경 구성

{{대상 사이트}} 를 자동으로 검증하기 위한 **최초 1회 설치 안내**입니다.
설치가 끝나면 `docs/RUN.md` 로 넘어가세요.

| | |
|---|---|
| 대상 | {{대상 사이트}} |
| 기본 환경 | `{{환경명}}` |
| 계정 발급 | {{계정 발급}} |
| 문의 | {{담당자}} |

---

## 1. 준비물

| | 비고 |
|---|---|
| Python **3.12 이상** | `python --version` 으로 확인 |
| Git | 저장소를 받을 때만 |
| 대상 사이트 접근 | 사내망·VPN 이 필요하면 미리 확인하세요 |
| 테스트 계정 | {{계정 발급}} |
| 디스크 여유 | **약 1.4 GB** (브라우저 3종 1.2 GB + 패키지 150 MB) |

브라우저는 따로 설치하지 않아도 됩니다. 3장에서 자동화 전용 브라우저를 내려받습니다.
**PC 에 설치된 Chrome 과는 별개**이고, 기존 브라우저에 영향을 주지 않습니다.

---

## 2. 저장소 받기

```bash
git clone {{저장소 URL}}
cd {{저장소 폴더명}}
```

> 폴더 이름은 저장소 주소의 마지막 조각입니다. `git clone` 이 무엇을 만들었는지는
> 바로 위 출력에 찍히고, `ls` (Windows 는 `dir`) 로도 확인할 수 있습니다.

---

## 3. 설치

아래를 위에서부터 그대로 실행합니다.

```bash
# 1) 가상환경 만들기
python -m venv .venv

# 2) 가상환경 활성화
#    Windows
.venv\Scripts\activate
#    macOS / Linux
source .venv/bin/activate

# 3) 패키지 설치 (검증된 버전 조합)
pip install -r requirements.lock

# 4) 자동화용 브라우저 설치 — 용량이 큽니다 (3종 합쳐 약 1.2 GB)
playwright install
```

> **Chrome 계열만 쓸 예정이면 `playwright install chromium` 으로 충분합니다**
> (약 700 MB, 500 MB 절약). 나중에 다른 브라우저로 돌리려면 그때
> `playwright install firefox` 처럼 추가로 받으면 됩니다.

> **가상환경 활성화는 최초 1회가 아닙니다.** 터미널을 새로 열 때마다 2번을 다시
> 해야 합니다. 프롬프트 앞에 `(.venv)` 가 보이면 활성화된 상태입니다.

### `requirements.lock` 과 `requirements.txt`

| 파일 | 언제 |
|---|---|
| `requirements.lock` | **평소에 이것을 쓰세요.** 버전이 고정돼 있어 어제와 오늘이 같습니다 |
| `requirements.txt` | 버전 범위만 적힌 파일입니다. 자동화 담당자가 갱신할 때 씁니다 |

---

## 4. 계정 설정 (`.env`)

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

만든 `.env` 를 열어 **환경과 계정 비밀번호만** 채웁니다.

```bash
ENV={{환경명}}
USER_PASSWORD=발급받은_비밀번호
```

**나머지 항목은 주석 처리된 채로 두세요.** 주석을 풀면 그 값이 환경별 설정
(`config/{{환경명}}.yaml`)을 덮어써, 환경을 바꿔도 값이 따라오지 않습니다.

설정값의 우선순위는 아래와 같습니다. 오른쪽이 셉니다.

```text
config/default.yaml  <  config/<환경>.yaml  <  .env  <  실행할 때 준 옵션
```

> `.env` 는 Git 에 올라가지 않습니다. **비밀번호를 다른 파일에 적지 마세요.**

---

## 5. 설치 확인

```bash
pytest -m smoke
```

핵심 기능만 짧게 도는 검증입니다. 마지막에 이런 요약이 나오면 성공입니다.

```text
Total   : 4
Passed  : 4
Failed  : 0
Pass Rate : 100.0%
```

여기까지 됐으면 **`docs/RUN.md` 로 넘어가세요.**

---

## 6. 설치가 안 될 때

| 증상 | 해결 |
|---|---|
| `python: command not found` | Python 이 설치되지 않았거나 PATH 에 없습니다. `python3` 로도 해보세요 |
| `pytest` / `playwright: command not found` | 가상환경을 활성화하지 않았습니다 (3장 2번). 프롬프트에 `(.venv)` 가 있는지 보세요 |
| `Executable doesn't exist ...` | `playwright install` 을 안 했습니다 (3장 4번) |
| 설치 중 `WinError 206` | Windows 경로 260자 제한입니다. 프로젝트를 `C:\work\...` 같은 짧은 경로로 옮기세요 |
| `playwright install` 이 매우 느림 | 수백 MB 를 내려받습니다. 사내망이면 프록시 설정이 필요할 수 있습니다 |
| 콘솔에 한글이 깨짐 | `set PYTHONUTF8=1` (PowerShell 은 `$env:PYTHONUTF8=1`). **리포트 파일은 항상 UTF-8 이라 영향 없습니다** |
| `pytest -m smoke` 가 전부 실패 | 대상 사이트가 열려 있는지, 사내망·VPN 이 필요한지 확인하세요 |
| 로그인만 전부 실패 | `.env` 의 비밀번호를 확인하세요. 계정 잠김·만료도 자주 있는 원인입니다 |

그래도 안 되면 **터미널에 나온 오류 메시지 전체**를 {{담당자}} 에게 보내주세요.
