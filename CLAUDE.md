# CLAUDE.md

Playwright + pytest 자동화 저장소입니다. **Claude 가 지킬 규칙**만 여기 둡니다.
사람이 읽을 설명은 문서에 있고, 여기서는 링크만 겁니다 — 같은 내용을 두 군데 쓰면
반드시 어긋납니다.

| 필요한 것 | 어디 |
|---|---|
| 작업 흐름 (새 화면을 받았다, 뭐부터 하나) | [`docs/AUTOMATION_GUIDE.md`](docs/AUTOMATION_GUIDE.md) |
| 기능별 레퍼런스 | [`README.md`](README.md) |
| Claude 와 사람의 역할 분담 · MCP 사용법 | [가이드 9장](docs/AUTOMATION_GUIDE.md#9-claude-와-함께-쓰기) |
| TC 명세 양식 (사람이 TC 를 쓸 때) | [`docs/TC_TEMPLATE.md`](docs/TC_TEMPLATE.md) |
| 고객사에 전달할 실행 가이드 (양식) | [`docs/CLIENT_RUNBOOK.template.md`](docs/CLIENT_RUNBOOK.template.md) |

---

## 시작하기 전

**TC(무엇을 검증할지)는 사람이 정합니다.** "기대결과: 정상 동작" 같은 문장이면 아직
TC 가 아닙니다. 화면에서 눈으로 확인 가능한 것 하나로 좁혀달라고 요청하고 기다리세요.
TC 없이 테스트를 지어내지 마세요.
어떻게 써야 하냐고 물으면 **[`docs/TC_TEMPLATE.md`](docs/TC_TEMPLATE.md) 양식을 안내**하세요
(양식을 대신 채워주지는 마세요 — 기대결과를 지어내는 것과 같습니다).

Locator 는 추측하지 말고 **Playwright MCP 로 실제 화면에서 확보**합니다
(`browser_navigate` → `browser_snapshot` → `browser_evaluate`).
**조사 전에 `browser_resize` 로 `config` 의 `viewport`(기본 1920x1080)에 창을 맞추세요.**
뷰포트에 따라 DOM 이 통째로 달라지는 사이트가 있습니다 — 실제로 이것 때문에 한 번
실패했습니다 ([가이드 9장](docs/AUTOMATION_GUIDE.md#9-claude-와-함께-쓰기)).

---

## Locator

**위에서부터** 시도합니다. 근거와 예시는 [README 9장](README.md#9-locator-작성-기준).

1. `get_by_role()` → 2. `get_by_label()` → 3. `get_by_placeholder()` →
4. `get_by_text()` → 5. `get_by_test_id()` → 6. CSS

- **XPath 금지.** 인덱스(`nth(3)`) 금지. 자동 생성 클래스(`css-1a2b3c`) 금지.
- Locator 는 **Page Object 안에만** 둡니다. 테스트 코드에 쓰지 않습니다.
- 사이트가 `data-testid` 가 아닌 속성을 쓰면 `config/default.yaml` 의
  `test_id_attribute` 한 줄만 바꿉니다. 테스트 코드는 그대로 둡니다.
- 안정적인 Locator 를 만들 수 없으면 지어내지 말고 **개발팀에 `data-testid` 요청**을
  사용자에게 제안하세요.
- 커스텀 엘리먼트(`<qm-button>` 등)는 `get_by_role()` 로 안 잡히고 `to_be_disabled()` 도
  통하지 않습니다. `to_have_attribute("disabled", "true")` 로 판정하세요.

---

## 안티패턴 — 이렇게 쓰면 안 됩니다

상세 설명과 예시는 [가이드 4장](docs/AUTOMATION_GUIDE.md#4-안티패턴-도감).

| 금지 | 대신 |
|---|---|
| `time.sleep()` | `expect(...)` 의 자동 대기 |
| `assert x.is_visible()` | `expect(x).to_be_visible()` |
| 테스트 코드에 Locator | Page Object 안에 |
| XPath / `nth(3)` | 역할·텍스트로 좁히기 |
| 다른 테스트가 만든 데이터에 의존 | 테스트가 자기 데이터를 만들기 (API 권장) |
| URL·계정·타임아웃 하드코딩 | `config/*.yaml` + `.env` |
| `try/except` 로 실패 숨기기 | 그냥 실패하게 두기 |
| 클릭만 하고 끝나는 테스트 | 단정을 반드시 넣기 |
| 한 테스트에 검증 20개 | TC 하나 = 목적 하나 |
| Step 을 한 줄마다 쪼개기 | TC 명세서의 절차 한 줄 단위로 |

추가 규칙:

- 테스트 함수명은 **영문**, docstring 은 **한글** (docstring 이 리포트 제목이 됩니다).
- `@pytest.mark.tc_id(...)` 와 업무 영역 marker 를 붙입니다.
  새 marker 를 만들면 `pytest.ini` 에 등록해야 합니다 (`--strict-markers`).
- 비밀번호·토큰은 **`.env` 에만** 둡니다. yaml 에는 `password_env` 로 변수명만 씁니다.
- 커밋 전에 `page.pause()`, `print()`, 주석 처리한 코드를 지웁니다.

---

## 손대지 마세요

공통 기능입니다. Base 에서 고쳐 각 프로젝트로 내려보냅니다
([README 18장](README.md#18-새-고객사-프로젝트-시작하기)).

```text
conftest.py                 utils/
reporting/                  pages/base_page.py
api/api_client.py           components/base_component.py
tests/unit/
```

여기를 고쳐야만 문제가 풀린다고 판단되면 **고치지 말고 먼저 사용자에게 이유를
설명하고 물어보세요.** 승인받고 고쳤다면 그 변경에는 `/code-review` 를 권하세요.

---

## 커밋 전 게이트

**새로 쓴 테스트 — 3종을 전부 통과해야 합니다.**

```bash
pytest tests/<경로>::<테스트>     # 단독 (다른 테스트에 기대지 않는가)
pytest -n 2                      # 병렬 (데이터·계정을 공유하지 않는가)
# 연속 3회                        (Flaky 하지 않은가)
```

**저장소 전체 — 3종.**

```bash
pytest                     # 업무 테스트. 전부 통과해야 함
pytest -m failure_demo     # 의도된 실패. Evidence 파이프라인이 살아있는지 확인용
pytest -m base_unit        # Base 자체 회귀 테스트 (브라우저 없음, 1초 미만)
```

뒤의 둘은 기본 실행에서 빠져 있습니다 (`pytest.ini` 의 `addopts`).
`failure_demo` 는 빨간불이 되기 때문이고, `base_unit` 은 고객사용 리포트에
업무 테스트와 섞이면 안 되기 때문입니다.

`failure_demo` 는 **실패하는 것이 정상**입니다. 실패한 자리에 Screenshot / Trace /
Page HTML / Log 가 실제로 남았는지까지 확인하세요. 기대 실패 개수가 바뀌었으면
Evidence 배선이나 예제 사이트 쪽이 변한 것이므로 원인을 확인하고 보고하세요.

---

## 보고 규칙

**실행 결과를 요약하지 말고 터미널 출력을 그대로 붙이세요.**
"통과했습니다" 는 증거가 아닙니다. 파일 하나만 돌려보고 "검증 완료" 라고 보고했다가
전체 실행에서 깨진 사례가 있었습니다.

통과하지 못한 것이 있으면 숨기지 말고 그대로 적으세요. 건너뛴 단계가 있으면
건너뛰었다고 적으세요.

---

## 이 환경에서 겪은 것

- **Windows 콘솔에서 한글이 섞인 heredoc·`grep` 출력이 깨집니다.** 통과/실패를
  판정하는 검사는 ASCII 키워드로 하거나 파일에 쓰고 읽으세요. 깨진 출력을 보고
  "없다" 고 단정하지 마세요.
- **리포트 기능을 텍스트 추출로 판정하지 마세요.** `report.html` 에서 태그를 걷어내고
  읽다가 "썸네일이 없다" 고 잘못 판단한 적이 있습니다. 브라우저로 열거나 태그를 세세요.
- **Playwright MCP 브라우저는 `pytest` 와 별개입니다.** 세션·쿠키가 공유되지 않습니다.
  MCP 에서 됐다고 테스트가 통과하는 것이 아닙니다. 확인은 반드시 `pytest` 로 하세요.
