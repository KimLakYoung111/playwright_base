# 설계: 리포트 보강 (Marker·Flaky·느린 테스트·인쇄 + 실행 메타)

작성일 2026-09-09 · 대상 `reporting/` · 상태 **승인됨, 미구현**

---

## 배경

`artifacts/<run_id>/report/report.html` 는 고객사에 폴더째 전달하는 산출물입니다
(3회차 운영 규칙). 지금 담고 있는 것은 헤더 메타, 요약 카드, 도넛, Category 표,
실패 카드(스텝·트레이스백·스크린샷·아티팩트 링크), 전체 테스트 표입니다.

코드를 훑어 보니 **이미 수집하고 있는데 화면에 안 그리는 데이터**가 있고,
고객사 개발팀이 반드시 묻는 "어느 빌드를 테스트했나" 에는 답할 방법이 없습니다.

## 주 독자 (이 결정이 나머지를 좌우함)

**고객사 비개발자(기획·QA·관리자) + 고객사 개발팀** 둘 다입니다.
우리 내부는 주 독자가 아닙니다.

리포트 하나가 성격이 다른 두 독자를 동시에 만족시켜야 하므로,
**화면(비개발자)과 추적성(개발팀)을 한 페이지에 층으로 쌓되, 인쇄본에서는
비개발자용만 남기는** 방향으로 갑니다.

## 범위

| 단계 | 내용 | `result.json` |
|---|---|---|
| **A** | Marker 집계 표, Flaky 목록, 느린 테스트 Top 5, 인쇄용 CSS | **불변** |
| **B** | 앱 버전·git·실행자·명령줄·병렬 수 | schema 1.0 → **1.1** |

A 와 B 는 **커밋을 나눕니다.** A 는 `result.json` 을 건드리지 않아 기존 소비자
(Test Runner UI, 사내 Dashboard, `ci_summary`)에 위험이 0 이고, 눈에 보이는 개선이
먼저 나옵니다. B 에서 스키마를 한 번만 올립니다.

### 범위에 넣지 않은 것

- **영상(video)** — 보류. 사유와 재검토 조건은 맨 아래.
- 실행 이력 / 지난 실행 대비 추세 — 이력 저장 설계가 따로 필요.
- 실패 원인 그룹핑, 콘솔·네트워크 오류 캡처, TC 명세 연결 — 각각 별건.

---

## Step A — 템플릿만 고치기

**바뀌는 파일: `reporting/templates/report.html` 하나.**
데이터가 이미 `result.json` 에 다 있으므로 수집 코드는 건드리지 않습니다.

### A-1. Marker 별 집계 표

`markers[]` 는 `result_collector` 가 이미 채우는데 템플릿이 그리지 않고 있습니다.
Category 표 바로 아래에 **같은 마크업**으로 넣습니다 (열: Marker / Total / Passed /
Failed / Skipped / Pass Rate / 미니바).

`markers[]` 가 비면 섹션을 통째로 숨깁니다.

### A-2. Flaky (재시도) 목록

`tests[]` 중 `retries > 0` 인 것만 모읍니다. 열은 Test ID / Test Name / Category /
재시도 횟수 / 최종 결과.

요약 패널의 "재시도 N건" 글자(`report.html` 의 `summary.retried` 자리)를
이 섹션으로 가는 앵커 링크로 바꿉니다. 지금은 건수만 있고 **어느 테스트인지 알 방법이
없습니다.**

재시도가 0 이면 섹션을 숨깁니다.

### A-3. 느린 테스트 Top 5

`duration` 내림차순 5건. `<details>` 로 감싸 **기본 접힘**입니다.
주 독자가 고객사라 평소엔 안 보이는 편이 낫고, 성능 회귀를 볼 때만 폅니다.

전체가 5건 이하면 섹션을 숨깁니다.

### A-4. 인쇄 / PDF 용 CSS

`@media print` 를 추가합니다. 현재 `@media` 규칙은 다크모드와 반응형뿐입니다.

**인쇄본은 「요약 + 실패」만 담습니다.** 전체 테스트 표 120건을 PDF 로 뽑으면
아무도 보지 않습니다. 구체적으로:

- 전체 테스트 표(`#tests`) 와 필터 버튼(`.controls`), 느린 테스트 섹션을 숨김
- 다크모드 색을 인쇄에서 강제 해제 (흰 바탕·검은 글씨)
- 실패 카드에 `break-inside: avoid` — 카드 중간에서 페이지가 잘리지 않게
- 트레이스백(`pre.err`)은 최대 높이를 두고 넘치면 자름 (인쇄에서 수십 장 방지)
- 스크린샷 썸네일은 유지 (비개발자가 인쇄본에서 제일 먼저 보는 것)

### Step A 검증 기준

```bash
git diff --name-only        # reporting/templates/report.html 한 줄만 나와야 함
pytest                      # 30 passed, 12 deselected
pytest -m failure_demo      # 3 failed, 1 skipped  (의도된 실패)
pytest -m base_unit         # 8 passed
```

`git diff --name-only` 가 한 파일만 보이는 것이 **`result.json` 불변의 증거**입니다.
그 뒤 브라우저로 `report.html` 을 열어 새 섹션 3개와 인쇄 미리보기를 눈으로 확인합니다.

---

## Step B — 실행 메타 수집 (schema 1.0 → 1.1)

**바뀌는 파일: `reporting/result_collector.py`, `utils/config.py`,
`config/default.yaml`, `reporting/result_schema.md`, `reporting/templates/report.html`,
`tests/unit/test_paths_retention.py` 옆에 새 테스트 파일.**

### B-1. 추가 필드

`result.json` 최상위 `schema_version` 을 `"1.1"` 로 올리고 `run` 에 추가합니다.
**기존 필드는 하나도 없애지 않습니다** (스키마 문서의 규칙).

```jsonc
"run": {
  // ...기존 필드 그대로...
  "app_version": "v2.14.3 (build 8821)",  // 주입. 없으면 null
  "git": {                                 // 자동. .git 이 없으면 null
    "branch": "main",
    "commit": "5d1ed8b",
    "dirty": false                         // 커밋 안 된 변경이 있으면 true
  },
  "triggered_by": "klyhja",                // 실행자. 끌 수 있음
  "command": "pytest -m smoke -n 4 --env=staging",
  "workers": 4                             // 병렬 수. 순차 실행이면 1
}
```

### B-2. 앱 버전 주입 경로

`config/default.yaml` 에 빈 값을 두고 환경변수가 덮어씁니다.
`utils/config.py` 의 `_env_str` 패턴을 그대로 씁니다.

```yaml
# 테스트 대상 앱의 버전. 자동화 코드 버전과 다릅니다.
# CI 에서 APP_VERSION 환경변수로 주는 것을 권장합니다.
app_version: ""
```

`RunConfig.app_version: str = ""` 을 추가하고, 빈 문자열이면 `result.json` 에 `null`,
리포트에는 `-` 로 표시합니다. 고객사마다 버전 체계가 달라서 **형식을 강제하지 않습니다.**

### B-3. git 정보 수집

`subprocess` 로 세 가지를 읽습니다.

| 값 | 명령 |
|---|---|
| `branch` | `git rev-parse --abbrev-ref HEAD` |
| `commit` | `git rev-parse --short HEAD` |
| `dirty` | `git status --porcelain` 의 출력이 비었는지 |

**어떤 이유로든 실패하면 `git` 전체를 `null` 로 두고 조용히 넘어갑니다.**
고객사가 이 Base 를 zip 으로 복사해 쓰면 `.git` 이 아예 없습니다. git 이 없다고
테스트가 죽으면 안 됩니다. 타임아웃도 짧게 겁니다.

수집 시점은 실행 시작 1회입니다 (테스트마다 부르지 않음).

### B-4. 실행자 · 명령줄 · 병렬 수

- **`triggered_by`** — CI 환경변수(`GITHUB_ACTOR` 등)를 먼저 보고, 없으면
  `getpass.getuser()`. 개인정보라 끌 수 있게 설정을 둡니다.

  ```yaml
  report:
    show_triggered_by: true   # false 면 result.json 에 null
  ```

- **`command`** — `sys.argv[1:]` 를 조립합니다. `sys.argv[0]` 은 실행 파일의 전체
  경로라 사용자 이름이 섞이므로 버리고 `pytest` 로 시작하게 만듭니다.

- **`workers`** — pytest-xdist 의 `config.option.numprocesses` 를 읽고, 없거나
  `None` 이면 `1`.

### B-5. 비밀 마스킹

`command` 문자열에 `RunConfig.secrets()` 의 값이 들어 있으면 `***` 로 바꿉니다.
`secrets()` 는 이미 있는 메서드라 새로 만들지 않습니다.

**`base_url` 은 마스킹하지 않습니다.** 리포트 헤더가 이미 "Target URL" 로 링크까지
걸어 의도적으로 보여주고 있어서, 명령줄에서만 가리면 앞뒤가 맞지 않습니다.
가려야 할 것은 명령줄에 섞여 들어올 수 있는 **비밀번호·토큰**입니다.

> 이 저장소는 Public 입니다. 고객사 URL·계정을 커밋하지 않는다는 기존 원칙은
> 그대로입니다. 이 절은 **생성되는 리포트 파일** 에 대한 것입니다.

### B-6. 리포트 표시

헤더 `metagrid` 에 3줄을 더합니다. 값이 `null` 이면 그 줄을 아예 그리지 않습니다.

```
Environment   STAGING
App Version   v2.14.3 (build 8821)
Automation    main @ 5d1ed8b (변경 있음)
Browser       Chromium (headless)
Target URL    https://...
실행자         klyhja
실행 명령      pytest -m smoke -n 4 --env=staging
병렬          4 workers
```

`ci_summary.py` 도 앱 버전과 커밋을 한 줄 넣습니다 — Slack·CI 요약에서 제일 먼저
필요한 값입니다.

### Step B 검증 기준

```bash
pytest -m base_unit         # 8 → 12 passed (아래 4개 추가)
pytest                      # 30 passed, 12 deselected
pytest -m failure_demo      # 3 failed, 1 skipped
```

새 단위 테스트 4개 (marker `base_unit`):

1. `.git` 이 없는 임시 디렉터리에서 `git` 이 `null` 이고 예외가 안 난다
2. `app_version` 이 빈 문자열이면 `null`
3. `command` 에서 `secrets()` 값이 `***` 로 바뀐다
4. `workers` 가 xdist 없을 때 `1`

그리고 **`schema_version` 이 `"1.1"` 이고 1.0 의 모든 필드가 그대로 있는지**
확인합니다.

---

## 되돌리는 법

- **Step A** — 템플릿 커밋만 revert. `result.json` 을 안 건드렸으므로 다른 영향 없음.
- **Step B** — 커밋 revert 후 `schema_version` 이 `"1.0"` 으로 돌아오는지 확인.
  소비자는 추가 필드만 무시하면 되므로 되돌리지 않고 두어도 안전합니다.
- **실행자 이름만 끄고 싶을 때** — `config/default.yaml` 의
  `report.show_triggered_by: false`.

---

## 영상(video): 보류

Playwright 영상은 `evidence.video: on-failure` 로 기존 모드 어휘에 자연스럽게 붙고
용량도 1분에 1~3 MB 수준이라 부담이 크지 않습니다. 그런데도 뺐습니다.

**이유.** `utils/evidence.py:97` 이 tracing 을 `screenshots=True, snapshots=True,
sources=True` 로 켜고 있어서 Trace 안에 이미 화면 프레임·DOM·네트워크·콘솔이 다
들어 있습니다. 원인 규명에서 영상은 Trace 를 이길 수 없습니다 (영상엔 콘솔도
네트워크도 없음). 영상이 이기는 곳은 **여는 문턱** 하나인데, 그마저 실패 카드의
**스텝 목록 + 전체 페이지 스크린샷**이 대체로 덮습니다.

시연도 근거가 되지 못합니다. 시연에서는 headed 로 라이브 실행을 보여주므로
녹화본이 필요 없습니다.

**구현 위험은 A·B 와 차원이 다릅니다.** 영상 파일은 **Context 가 닫혀야 완성**됩니다.
지금 `page` fixture(`conftest.py:216`)가 tracing 을 끝내는 시점에는 파일이 아직
없어서, Context 종료 뒤에 도는 처리를 따로 만들어야 합니다.

### 재검토 조건 (하나라도 실제로 겪으면)

1. 스크린샷 한 장으로 설명이 안 되는 **애니메이션·화면 전환 중 실패**가 반복될 때
2. 고객사가 "재현이 안 된다"며 증거를 계속 요구할 때
3. 비개발자에게 실패를 비동기로 전달해야 하는 일이 잦아질 때

> 추측으로 판단하지 말고, A·B 를 넣은 리포트를 고객사에 **실제로 한 번 내보낸 뒤**
> 위 조건이 나오는지 보고 정합니다.

---

## 참고

- 한글 판정이 필요한 검사는 `PYTHONIOENCODING=utf-8` 로 **파일에 받아서** 읽을 것
  (Windows 콘솔 cp949). 커밋 메시지도 `git commit -F <파일>`.
- Base 본체를 고치므로 마무리에 `/code-review` 를 붙입니다.
