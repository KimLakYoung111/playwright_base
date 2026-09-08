# 리포트 보강 구현 계획 (Marker·Flaky·느린 테스트·인쇄 + 실행 메타)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 고객사에 전달하는 `report.html` 에 이미 수집 중인 데이터(Marker·재시도·수행시간)를
그리고, 인쇄본을 쓸 수 있게 만들고, "어느 앱 빌드를 무슨 명령으로 테스트했는지" 를 남긴다.

**Architecture:** 두 단계로 나눈다. **Step A(Task 1~4)** 는 `reporting/templates/report.html`
한 파일만 고쳐 `result.json` 을 전혀 건드리지 않는다 — 기존 소비자(Test Runner UI, 사내
Dashboard, `ci_summary`)에 위험이 0 이다. **Step B(Task 5~8)** 는 새 모듈
`utils/runmeta.py` 로 실행 메타를 모아 `result.json` schema 를 1.0 → 1.1 로 올린다.
기존 필드는 하나도 없애지 않고 추가만 한다.

**Tech Stack:** Python 3.12+, pytest, pytest-xdist, Jinja2, Playwright.

**설계 문서:** `docs/superpowers/specs/2026-09-09-report-enhancement-design.md`

## Global Constraints

- **Windows 콘솔은 cp949 라 한글이 깨진다.** 한글 판정이 필요한 검사는
  `PYTHONIOENCODING=utf-8` 을 주고 **파일로 받아서** 읽는다.
  커밋 메시지도 heredoc 대신 파일에 쓰고 `git commit -F <파일>` 로 넣는다.
- **`result.json` 스키마 규칙: 기존 필드는 없애지 않고 추가만 한다.**
  (`reporting/result_schema.md` 의 규칙)
- Base 자체 회귀 테스트는 `tests/unit/` 아래에 두고 파일 맨 위에
  `pytestmark = pytest.mark.base_unit` 을 붙인다. `pytest.ini` 의 `addopts` 가
  `-m "not failure_demo and not base_unit"` 이라 기본 실행에서 빠진다.
- **민감정보는 `utils.logger.mask_secrets()` 로 가린다.** `RunConfig.secrets()` 를
  직접 부르지 않는다 — `conftest.py:134` 가 이미 `sensitive_filter.register(*run_config.secrets())`
  로 전역 등록해 두었고, `result_collector` 도 `mask_secrets` 를 쓴다.
- **`base_url` 은 마스킹하지 않는다.** 리포트 헤더가 "Target URL" 로 이미 의도적으로
  노출한다. 가릴 대상은 명령줄에 섞일 수 있는 비밀번호·토큰이다.
- **이 저장소는 Public 이다.** 고객사 URL·계정을 커밋에 넣지 않는다.
- 모든 작업 후 게이트 3종이 통과해야 한다:
  `pytest` (30 passed) / `pytest -m failure_demo` (3 failed, 1 skipped) /
  `pytest -m base_unit`.

---

## File Structure

| 파일 | 책임 | Task |
|---|---|---|
| `reporting/templates/report.html` (수정) | 화면 표시 전부 | 1,2,3,4,8 |
| `tests/unit/test_report_render.py` (신규) | 템플릿 렌더 회귀 | 1,2,3,4,8 |
| `utils/runmeta.py` (신규) | git·실행자·명령줄·병렬 수 수집. **부수효과 없는 순수 조회** | 5 |
| `tests/unit/test_runmeta.py` (신규) | `runmeta` 회귀 | 5 |
| `utils/config.py` (수정) | `app_version`, `show_triggered_by` 설정값 | 6 |
| `config/default.yaml` (수정) | 위 두 값의 기본값 | 6 |
| `tests/unit/test_config_report.py` (신규) | 설정 회귀 | 6 |
| `reporting/result_collector.py` (수정) | `run` 블록에 메타 병합, schema 1.1 | 7 |
| `conftest.py` (수정, 135행) | 수집한 메타를 collector 에 주입 | 7 |
| `reporting/ci_summary.py` (수정) | Slack/CI 요약에 버전·커밋 한 줄 | 8 |
| `reporting/result_schema.md` (수정) | 1.1 필드 문서화 | 8 |

`utils/runmeta.py` 를 따로 두는 이유: `result_collector.py` 는 이미 270줄이고
"pytest report 객체 → 표준 구조" 라는 책임이 분명하다. `subprocess` 로 git 을 부르는
일은 성격이 달라 섞지 않는다. 테스트도 브라우저·pytest 없이 단독으로 돈다.

---

## Task 1: Marker 별 집계 표

`markers[]` 는 `result_collector.markers()` 가 이미 채우고 `render_html` 이
`**data` 로 템플릿에 넘기는데, 템플릿이 그리지 않고 있다. Category 표와 같은 마크업으로
바로 아래에 넣는다.

**Files:**
- Modify: `reporting/templates/report.html:222` (Category `</section>` 바로 뒤)
- Test: `tests/unit/test_report_render.py` (신규)

**Interfaces:**
- Consumes: `render_html(collector, path)` — `reporting/report_generator.py:90`.
  `collector` 는 `to_dict()` 하나만 있으면 된다.
- Produces: 테스트 헬퍼 `_FakeCollector`, `_data()`, `_test_row()` — Task 2·3·4·8 이
  같은 파일에서 이어 쓴다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_report_render.py` 를 새로 만든다.

```python
"""report.html 템플릿 렌더 회귀 테스트.

Browser 도 pytest 실행도 없이, ``render_html`` 에 최소 데이터를 넣어
HTML 문자열만 확인합니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from reporting import report_generator

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit


class _FakeCollector:
    """``render_html`` 은 ``to_dict()`` 만 부릅니다. 그 하나만 흉내 냅니다."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


def _test_row(**overrides: Any) -> dict[str, Any]:
    """``result.json`` 의 tests[] 한 줄. 필요한 것만 덮어씁니다."""
    row = {
        "test_id": "TC001",
        "name": "정상 로그인",
        "nodeid": "tests/login/test_login.py::test_login",
        "file": "tests/login/test_login.py",
        "function": "test_login",
        "category": "Login",
        "markers": ["smoke"],
        "status": "passed",
        "duration": 1.0,
        "started_at": "2026-09-09T10:00:00",
        "finished_at": "2026-09-09T10:00:01",
        "retries": 0,
        "error": None,
        "current_url": None,
        "browser": "chromium",
        "steps": [],
        "artifacts": {},
    }
    row.update(overrides)
    return row


def _data(**overrides: Any) -> dict[str, Any]:
    """``to_dict()`` 가 돌려주는 최소 구조."""
    data = {
        "schema_version": "1.0",
        "run": {
            "run_id": "20260909_100000",
            "project": "Example Automation",
            "environment": "staging",
            "browser": "chromium",
            "headless": True,
            "base_url": "https://example.com/",
            "started_at": "2026-09-09T10:00:00",
            "finished_at": "2026-09-09T10:00:10",
            "duration": 10.0,
            "retries_configured": 0,
            "python": "3.12.10",
            "playwright": "1.62.0",
            "platform": "Windows 10",
            "artifacts_dir": r"C:\artifacts\20260909_100000",
            "exit_status": 0,
        },
        "summary": {
            "total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0,
            "xfailed": 0, "xpassed": 0, "pass_rate": 100.0,
            "duration": 10.0, "retried": 0,
        },
        "categories": [{"name": "Login", "total": 1, "passed": 1, "failed": 0,
                        "skipped": 0, "pass_rate": 100.0}],
        "markers": [{"name": "smoke", "total": 1, "passed": 1, "failed": 0,
                     "skipped": 0, "pass_rate": 100.0}],
        "tests": [_test_row()],
    }
    data.update(overrides)
    return data


def _render(tmp_path: Path, **overrides: Any) -> str:
    target = report_generator.render_html(_FakeCollector(_data(**overrides)),
                                          tmp_path / "report.html")
    return target.read_text(encoding="utf-8")


def test_marker_section_is_rendered(tmp_path: Path) -> None:
    """markers[] 가 있으면 Marker 표가 그려진다."""
    html = _render(tmp_path, markers=[
        {"name": "smoke", "total": 3, "passed": 3, "failed": 0,
         "skipped": 0, "pass_rate": 100.0},
        {"name": "regression", "total": 2, "passed": 1, "failed": 1,
         "skipped": 0, "pass_rate": 50.0},
    ])
    assert "Marker 별 결과" in html
    assert "regression" in html


def test_marker_section_hidden_when_empty(tmp_path: Path) -> None:
    """markers[] 가 비면 섹션 자체를 그리지 않는다."""
    html = _render(tmp_path, markers=[])
    assert "Marker 별 결과" not in html
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: `test_marker_section_is_rendered` 가 FAIL
(`assert "Marker 별 결과" in html` — 템플릿에 아직 없음).
`test_marker_section_hidden_when_empty` 는 PASS (아직 아무것도 안 그리므로).

- [ ] **Step 3: 템플릿에 Marker 섹션을 넣는다**

`reporting/templates/report.html` 의 Category 섹션이 끝나는 `</section>` (222행) 바로
뒤, `{% if failed_tests %}` 앞에 넣는다.

```html
  {% if markers %}
  <section class="panel" style="margin-bottom:18px">
    <h2>Marker 별 결과</h2>
    <table>
      <thead><tr><th>Marker</th><th class="num">Total</th><th class="num">Passed</th><th class="num">Failed</th><th class="num">Skipped</th><th class="num">Pass Rate</th><th></th></tr></thead>
      <tbody>
      {% for mk in markers %}
        <tr>
          <td><span class="tag">{{ mk.name }}</span></td>
          <td class="num">{{ mk.total }}</td>
          <td class="num" style="color:var(--pass)">{{ mk.passed }}</td>
          <td class="num" style="color:{{ 'var(--fail)' if mk.failed else 'inherit' }}">{{ mk.failed }}</td>
          <td class="num">{{ mk.skipped }}</td>
          <td class="num">{{ mk.pass_rate }}%</td>
          <td><div class="minibar"><span style="width:{{ mk.pass_rate }}%"></span></div></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  {% endif %}
```

> 반복 변수를 `mk` 로 쓴다. `marker` 로 쓰면 읽는 사람이 `markers` 와 헷갈린다.

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: 2 passed

- [ ] **Step 5: 게이트를 돌린다**

```bash
git diff --name-only
```

기대: `reporting/templates/report.html` 한 줄만 (테스트 파일은 아직 untracked).
**이것이 `result.json` 을 안 건드렸다는 증거다.**

```bash
pytest
pytest -m base_unit
```

기대: `30 passed` / `10 passed` (기존 8 + 새 2)

- [ ] **Step 6: 커밋**

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): Marker 별 집계 표 추가

markers[] 는 이미 수집하고 있었는데 템플릿이 그리지 않았습니다.
Category 표와 같은 마크업으로 바로 아래에 넣었습니다.
result.json 은 건드리지 않았습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/templates/report.html tests/unit/test_report_render.py
git commit -F /tmp/cm.txt
```

---

## Task 2: Flaky (재시도) 목록

지금 요약 패널에 "재시도 N건" 이 나오지만 **어느 테스트인지 알 방법이 없다.**
`tests[].retries` 로 목록을 만들고, 요약의 그 글자를 앵커 링크로 바꾼다.

**Files:**
- Modify: `reporting/templates/report.html:171` (요약의 `summary.retried` 줄),
  Task 1 이 넣은 Marker 섹션 바로 뒤
- Test: `tests/unit/test_report_render.py` (Task 1 이 만든 파일에 추가)

**Interfaces:**
- Consumes: Task 1 의 `_render()`, `_test_row()`, `_data()`.
- Produces: HTML 앵커 `id="flaky"`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_report_render.py` 맨 아래에 추가한다.

```python
def test_flaky_section_lists_retried_tests(tmp_path: Path) -> None:
    """retries > 0 인 테스트만 Flaky 목록에 나온다."""
    html = _render(
        tmp_path,
        tests=[
            _test_row(test_id="TC001", retries=0),
            _test_row(test_id="TC002", name="흔들리는 결제", retries=2),
        ],
        summary={
            "total": 2, "passed": 2, "failed": 0, "skipped": 0, "error": 0,
            "xfailed": 0, "xpassed": 0, "pass_rate": 100.0,
            "duration": 10.0, "retried": 1,
        },
    )
    assert 'id="flaky"' in html
    # 요약의 "재시도 1건" 이 목록으로 가는 링크가 된다
    assert 'href="#flaky"' in html

    # 섹션 안쪽만 잘라서 본다. 아래 All Tests 표에는 TC001 이 정당하게 들어 있으므로
    # 문서 전체에 대고 "TC001 이 없다" 를 확인하면 엉뚱한 이유로 실패한다.
    start = html.find('id="flaky"')
    end = html.find("</section>", start)
    flaky_section = html[start:end]

    assert "흔들리는 결제" in flaky_section
    # retries=0 인 TC001 은 빠져야 한다. 이 줄이 없으면 "전체를 다 나열하는"
    # 깨진 구현도 통과한다.
    assert "TC001" not in flaky_section


def test_flaky_section_hidden_when_no_retries(tmp_path: Path) -> None:
    """재시도가 없으면 섹션을 그리지 않는다."""
    html = _render(tmp_path)
    assert 'id="flaky"' not in html
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: `test_flaky_section_lists_retried_tests` 가 FAIL (`assert 'id="flaky"' in html`)

- [ ] **Step 3: 요약의 재시도 글자를 링크로 바꾼다**

`reporting/templates/report.html:171` 을 찾는다. 현재:

```html
          {% if summary.retried %}<span style="color:var(--skip);font-size:12px">재시도 {{ summary.retried }}건</span>{% endif %}
```

이렇게 바꾼다:

```html
          {% if summary.retried %}<a href="#flaky" style="color:var(--skip);font-size:12px">재시도 {{ summary.retried }}건</a>{% endif %}
```

- [ ] **Step 4: Flaky 섹션을 넣는다**

Task 1 이 넣은 Marker 섹션의 `{% endif %}` 바로 뒤에 넣는다.

```html
  {% set flaky_tests = tests|selectattr("retries")|list %}
  {% if flaky_tests %}
  <section class="panel" id="flaky" style="margin-bottom:18px">
    <h2>재시도된 테스트 ({{ flaky_tests|length }})</h2>
    <div style="color:var(--muted);font-size:12px;margin:-6px 0 12px">
      한 번에 통과하지 못하고 재시도 끝에 결과가 정해진 테스트입니다.
      반복해서 올라오면 테스트나 대상 화면이 불안정하다는 신호입니다.
    </div>
    <table>
      <thead><tr><th>Test ID</th><th>Test Name</th><th>Category</th><th class="num">재시도</th><th>최종 결과</th></tr></thead>
      <tbody>
      {% for test in flaky_tests %}
        <tr>
          <td><strong>{{ test.test_id }}</strong></td>
          <td>{{ test.name }}</td>
          <td>{{ test.category }}</td>
          <td class="num">{{ test.retries }}</td>
          <td><span class="badge {{ test.status }}">{{ test.status|upper }}</span></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  {% endif %}
```

> `selectattr("retries")` 는 비교 연산자 없이 쓰면 **참인 값만** 고른다.
> `retries` 가 `0` 인 것은 빠지므로 이것으로 충분하다.

- [ ] **Step 5: 통과를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: 4 passed

- [ ] **Step 6: 게이트와 커밋**

```bash
pytest
pytest -m base_unit
```

기대: `30 passed` / `12 passed`

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): 재시도된 테스트 목록 추가

요약에 "재시도 N건" 건수만 있고 어느 테스트인지 알 방법이 없었습니다.
목록 섹션을 만들고 요약의 그 글자를 앵커 링크로 바꿨습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/templates/report.html tests/unit/test_report_render.py
git commit -F /tmp/cm.txt
```

---

## Task 3: 느린 테스트 Top 5

주 독자가 고객사라 평소엔 접어 둔다. 성능 회귀를 볼 때만 편다.

**Files:**
- Modify: `reporting/templates/report.html` (Task 2 의 Flaky 섹션 뒤)
- Test: `tests/unit/test_report_render.py` (추가)

**Interfaces:**
- Consumes: Task 1 의 `_render()`, `_test_row()`.
- Produces: 없음 (다음 Task 가 의존하는 이름 없음).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_slow_tests_are_sorted_and_capped(tmp_path: Path) -> None:
    """느린 순으로 5건까지만 보여준다."""
    rows = [_test_row(test_id=f"TC{i:03d}", name=f"테스트 {i}", duration=float(i))
            for i in range(1, 8)]
    html = _render(tmp_path, tests=rows)

    assert "느린 테스트" in html
    # 섹션 안쪽만 본다. </details> 로 끊지 않으면 뒤따르는 All Tests 표까지
    # 딸려 들어와 "잘렸는지" 를 확인할 수 없다.
    slow_block = html.split("느린 테스트", 1)[1].split("</details>", 1)[0]
    # 가장 느린 TC007(7.0초)은 나오고, 가장 빠른 테스트 1·2 는 잘린다
    assert "테스트 7" in slow_block
    assert "테스트 2" not in slow_block


def test_slow_tests_hidden_when_few(tmp_path: Path) -> None:
    """5건 이하면 순위가 의미 없으므로 섹션을 숨긴다."""
    html = _render(tmp_path)
    assert "느린 테스트" not in html
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: `test_slow_tests_are_sorted_and_capped` 가 FAIL (`assert "느린 테스트" in html`)

- [ ] **Step 3: 느린 테스트 섹션을 넣는다**

Task 2 의 Flaky 섹션 `{% endif %}` 바로 뒤.

```html
  {% if tests|length > 5 %}
  <section class="panel" style="margin-bottom:18px">
    <details>
      <summary style="cursor:pointer;font-size:14px;font-weight:600;color:var(--muted);
                      text-transform:uppercase;letter-spacing:.6px">
        느린 테스트 Top 5
      </summary>
      <table style="margin-top:14px">
        <thead><tr><th>Test ID</th><th>Test Name</th><th>Category</th><th class="num">수행시간</th></tr></thead>
        <tbody>
        {% for test in tests|sort(attribute="duration", reverse=true) %}
          {% if loop.index <= 5 %}
          <tr>
            <td><strong>{{ test.test_id }}</strong></td>
            <td>{{ test.name }}</td>
            <td>{{ test.category }}</td>
            <td class="num">{{ test.duration_text }}</td>
          </tr>
          {% endif %}
        {% endfor %}
        </tbody>
      </table>
    </details>
  </section>
  {% endif %}
```

> `duration_text` 는 `render_html`(`reporting/report_generator.py:99`)이 테스트마다
> 미리 넣어 주는 표시용 필드다. `result.json` 에는 안 들어간다.

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: 6 passed

- [ ] **Step 5: 게이트와 커밋**

```bash
pytest
pytest -m base_unit
```

기대: `30 passed` / `14 passed`

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): 느린 테스트 Top 5 (기본 접힘)

주 독자가 고객사라 평소엔 보이지 않게 details 로 접었습니다.
전체가 5건 이하면 순위가 의미 없어 섹션을 숨깁니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/templates/report.html tests/unit/test_report_render.py
git commit -F /tmp/cm.txt
```

---

## Task 4: 인쇄 / PDF 용 CSS

**인쇄본은 「요약 + 실패」만 담는다.** 전체 테스트 표 120건을 PDF 로 뽑으면 아무도
보지 않는다.

**Files:**
- Modify: `reporting/templates/report.html:126` (`.empty{...}` 다음, `</style>` 앞)
- Test: `tests/unit/test_report_render.py` (추가)

**Interfaces:**
- Consumes: Task 1 의 `_render()`.
- Produces: CSS 클래스 `.no-print` — 이 Task 안에서만 쓴다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_print_stylesheet_is_present(tmp_path: Path) -> None:
    """인쇄용 규칙이 들어 있고, 전체 테스트 표를 숨긴다."""
    html = _render(tmp_path)
    assert "@media print" in html
    print_block = html.split("@media print", 1)[1].split("</style>", 1)[0]
    # 전체 테스트 표와 필터 버튼은 인쇄에서 뺀다
    assert "#tests" in print_block
    assert ".controls" in print_block
    # 실패 카드가 페이지 중간에서 잘리지 않게 한다
    assert "break-inside" in print_block
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: FAIL (`assert "@media print" in html`)

- [ ] **Step 3: 인쇄 CSS 를 넣는다**

`reporting/templates/report.html` 의 `.empty{color:var(--muted);font-size:13px;padding:8px 0}`
바로 다음, `</style>` 앞에 넣는다.

```css
/* ---------- print / PDF ---------- */
/* 인쇄본은 "요약 + 실패" 만 담습니다.
   전체 테스트 표를 종이에 뽑으면 수십 장이 나오고 아무도 보지 않습니다. */
@media print{
  :root{
    --bg:#ffffff; --panel:#ffffff; --ink:#000000; --muted:#555555; --line:#cccccc;
    --pass-bg:#ffffff; --fail-bg:#ffffff; --skip-bg:#ffffff; --shadow:none;
  }
  body{background:#fff;color:#000}
  .wrap{max-width:none;padding:0}
  .panel,header.top{border:1px solid #ccc;box-shadow:none}
  /* 인쇄에서 뺄 것: 전체 테스트 표, 필터 버튼, 느린 테스트, 라이트박스 */
  #tests,.controls,details,#lb{display:none !important}
  /* 실패 카드가 페이지 중간에서 잘리지 않게 */
  .fail-card{break-inside:avoid;page-break-inside:avoid}
  /* 트레이스백이 길면 수십 장이 되므로 잘라서 보여줍니다 */
  pre.err{max-height:200px;overflow:hidden}
  a{color:#000;text-decoration:none}
}
```

> 전체 테스트 표를 숨기면 그 섹션의 `<h2>All Tests (N)</h2>` 만 남는다.
> 건수는 요약 카드에 이미 있으므로 제목만 남는 편이 오히려 "여기 표가 있는데
> 인쇄에서 뺐다" 는 신호가 되어 그대로 둔다.

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: 7 passed

- [ ] **Step 5: 눈으로 확인한다**

실제 실행 결과를 만들어 브라우저로 연다.

```bash
pytest -m failure_demo
```

`artifacts/latest_run.txt` 가 가리키는 폴더의 `report/report.html` 을 브라우저로 열고
**Ctrl+P 로 인쇄 미리보기**를 확인한다. 확인할 것:

- 전체 테스트 표와 필터 버튼이 안 보인다
- 실패 카드가 페이지 경계에서 잘리지 않는다
- 다크모드 브라우저에서도 인쇄 미리보기는 흰 바탕·검은 글씨다

- [ ] **Step 6: 게이트와 커밋**

```bash
git diff --name-only
```

기대: `reporting/templates/report.html`, `tests/unit/test_report_render.py` 둘뿐.
**Step A 전체에서 `result.json` 관련 파일이 하나도 안 나와야 한다.**

```bash
pytest
pytest -m base_unit
pytest -m failure_demo
```

기대: `30 passed` / `15 passed` / `3 failed, 1 skipped`

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): 인쇄/PDF 용 스타일 추가

인쇄본은 요약과 실패만 담습니다. 전체 테스트 표를 종이에 뽑으면
수십 장이 나오고 아무도 보지 않습니다. 다크모드 색을 인쇄에서 풀고
실패 카드가 페이지 중간에서 잘리지 않게 했습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/templates/report.html tests/unit/test_report_render.py
git commit -F /tmp/cm.txt
```

---

## Task 5: `utils/runmeta.py` — 실행 메타 수집

여기서부터 Step B 다. 아직 `result.json` 에 붙이지 않고 **모듈만 단독으로** 만든다.

**Files:**
- Create: `utils/runmeta.py`
- Test: `tests/unit/test_runmeta.py`

**Interfaces:**
- Consumes: `utils.config.PROJECT_ROOT`, `utils.logger.mask_secrets`.
- Produces: Task 7 이 쓰는 함수 4개.
  - `git_info(cwd: Path | None = None) -> dict[str, Any] | None`
    — `{"branch": str | None, "commit": str, "dirty": bool}` 또는 `None`
  - `triggered_by(enabled: bool = True) -> str | None`
  - `command_line() -> str`
  - `worker_count(pytest_config: Any) -> int`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_runmeta.py` 를 새로 만든다.

```python
"""실행 메타 수집(``utils.runmeta``) 단위 테스트.

git 이 없는 환경(고객사가 zip 으로 복사해 쓰는 경우)에서도 죽지 않는지가
이 모듈의 핵심 요구사항입니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from utils import runmeta

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit


def test_git_info_returns_none_when_git_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """git 실행 파일이 없어도 예외 없이 None 을 준다."""
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert runmeta.git_info() is None


def test_git_info_returns_none_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """.git 이 없어 git 이 실패해도 None 을 준다."""
    class _Failed:
        returncode = 128
        # stdout 을 일부러 비우지 않는다. 비워두면 returncode 검사를 빼먹은 구현도
        # 빈 문자열 덕분에 통과해 버려서, 이 테스트가 아무것도 지키지 못한다.
        stdout = "5d1ed8b"
        stderr = "fatal: not a git repository"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Failed())
    assert runmeta.git_info() is None


def test_git_info_reports_dirty_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    """커밋 안 된 변경이 있으면 dirty 가 True 다."""
    answers = {
        ("rev-parse", "--short", "HEAD"): "5d1ed8b",
        ("rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("status", "--porcelain"): " M README.md",
    }

    class _Ok:
        returncode = 0

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.stderr = ""

    def _fake_run(cmd: list[str], **kwargs: Any) -> Any:
        return _Ok(answers[tuple(cmd[1:])])

    monkeypatch.setattr(subprocess, "run", _fake_run)
    info = runmeta.git_info()
    assert info == {"branch": "main", "commit": "5d1ed8b", "dirty": True}


def test_command_line_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """명령줄에 섞인 비밀번호·토큰은 가려진다."""
    from utils.logger import sensitive_filter

    sensitive_filter.register("s3cret-token")
    monkeypatch.setattr(sys, "argv",
                        ["/long/path/to/pytest", "-m", "smoke", "--token=s3cret-token"])

    line = runmeta.command_line()

    assert "s3cret-token" not in line
    # sys.argv[0] 의 전체 경로는 버리고 pytest 로 시작한다
    assert line.startswith("pytest -m smoke")


def test_triggered_by_can_be_disabled() -> None:
    """개인정보가 걸리면 끌 수 있다."""
    assert runmeta.triggered_by(enabled=False) is None


def test_triggered_by_prefers_ci_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 가 알려주는 실행자를 먼저 쓴다."""
    monkeypatch.setenv("GITHUB_ACTOR", "ci-bot")
    assert runmeta.triggered_by() == "ci-bot"


def test_worker_count_defaults_to_one() -> None:
    """xdist 없이 순차 실행이면 1 이다."""
    class _NoXdist:
        class option:
            pass

    assert runmeta.worker_count(_NoXdist()) == 1


def test_worker_count_reads_xdist_option() -> None:
    """-n 4 로 돌리면 4 다."""
    class _Xdist:
        class option:
            numprocesses = 4

    assert runmeta.worker_count(_Xdist()) == 4
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_runmeta.py -m base_unit -v
```

기대: 수집 단계에서 FAIL — `ModuleNotFoundError: No module named 'utils.runmeta'`

- [ ] **Step 3: 모듈을 만든다**

`utils/runmeta.py`:

```python
"""실행 메타 수집 (git / 실행자 / 명령줄 / 병렬 수).

``result.json`` 의 ``run`` 블록에 들어갑니다.

이 모듈의 함수는 **어떤 경우에도 예외를 올리지 않습니다.** 값을 못 구하면
``None`` 을 돌려줍니다. 고객사가 이 Base 를 zip 으로 복사해 쓰면 ``.git`` 이
아예 없는데, 그것 때문에 테스트가 죽으면 안 되기 때문입니다.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from utils.config import PROJECT_ROOT
from utils.logger import mask_secrets

#: git 명령 하나에 허용할 시간(초). 넘으면 포기합니다.
#: 네트워크를 안 쓰는 명령만 부르므로 짧게 잡아도 충분합니다.
GIT_TIMEOUT = 3

#: CI 가 알려주는 실행자 이름. 앞에서부터 먼저 찾은 것을 씁니다.
CI_ACTOR_ENV = ("GITHUB_ACTOR", "GITLAB_USER_LOGIN", "BUILD_USER_ID")


def _git(*args: str, cwd: Path | None = None) -> str | None:
    """git 명령 하나를 돌려 표준출력을 돌려줍니다. 실패하면 None."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except Exception:
        # git 이 없거나, 타임아웃이거나, 권한이 없거나 — 이유를 가리지 않습니다.
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").strip()


def git_info(cwd: Path | None = None) -> dict[str, Any] | None:
    """``{'branch', 'commit', 'dirty'}`` 또는 None.

    ``.git`` 이 없거나 git 이 설치돼 있지 않으면 None 입니다.
    """
    commit = _git("rev-parse", "--short", "HEAD", cwd=cwd)
    if not commit:
        return None
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    status = _git("status", "--porcelain", cwd=cwd)
    return {
        "branch": branch or None,
        "commit": commit,
        "dirty": bool(status),
    }


def triggered_by(enabled: bool = True) -> str | None:
    """실행자 이름. ``enabled=False`` 면 None (개인정보 우려로 끌 수 있음)."""
    if not enabled:
        return None
    for key in CI_ACTOR_ENV:
        value = os.environ.get(key)
        if value:
            return value
    try:
        return getpass.getuser()
    except Exception:
        return None


def command_line() -> str:
    """실행 명령.

    ``sys.argv[0]`` 은 실행 파일의 전체 경로라 사용자 이름이 섞입니다.
    버리고 ``pytest`` 로 바꿉니다. 명령줄에 섞인 비밀번호·토큰은 가립니다.
    """
    return mask_secrets(" ".join(["pytest", *sys.argv[1:]]))


def worker_count(pytest_config: Any) -> int:
    """xdist 병렬 수. 순차 실행이면 1."""
    value = getattr(getattr(pytest_config, "option", None), "numprocesses", None)
    try:
        return int(value) if value else 1
    except (TypeError, ValueError):
        return 1
```

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_runmeta.py -m base_unit -v
```

기대: 8 passed

- [ ] **Step 5: 게이트와 커밋**

```bash
pytest
pytest -m base_unit
```

기대: `30 passed` / `23 passed` (15 + 8)

```bash
cat > /tmp/cm.txt <<'EOF'
feat: 실행 메타 수집 모듈(utils/runmeta.py) 추가

git 브랜치/커밋/dirty, 실행자, 명령줄, 병렬 수를 모읍니다.
git 이 없어도(고객사가 zip 으로 복사해 쓰는 경우) 예외 없이 None 을
돌려주는 것이 이 모듈의 핵심 요구사항입니다.
아직 result.json 에 붙이지 않았습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add utils/runmeta.py tests/unit/test_runmeta.py
git commit -F /tmp/cm.txt
```

---

## Task 6: 설정 추가 (`app_version`, `show_triggered_by`)

**Files:**
- Modify: `config/default.yaml` (`project_name` 다음)
- Modify: `utils/config.py` — `RunConfig` 필드 2개(68행 `test_id_attribute` 부근),
  `load_config` 의 반환부(258행 부근)
- Modify: `.env.example`
- Test: `tests/unit/test_config_report.py` (신규)

**Interfaces:**
- Consumes: 없음.
- Produces: Task 7·8 이 쓰는 `RunConfig.app_version: str`,
  `RunConfig.show_triggered_by: bool`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_config_report.py`:

```python
"""리포트용 설정값(``app_version``, ``show_triggered_by``) 단위 테스트.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import pytest

from utils.config import load_config

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit


def test_app_version_defaults_to_empty() -> None:
    """기본값은 빈 문자열이다. 고객사마다 버전 체계가 달라 강제하지 않는다."""
    config = load_config(env="staging")
    assert config.app_version == ""


def test_app_version_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 는 APP_VERSION 환경변수로 준다."""
    monkeypatch.setenv("APP_VERSION", "v2.14.3 (build 8821)")
    config = load_config(env="staging")
    assert config.app_version == "v2.14.3 (build 8821)"


def test_show_triggered_by_defaults_to_true() -> None:
    config = load_config(env="staging")
    assert config.show_triggered_by is True


def test_show_triggered_by_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """개인정보가 걸리면 환경변수로 끌 수 있다."""
    monkeypatch.setenv("SHOW_TRIGGERED_BY", "false")
    config = load_config(env="staging")
    assert config.show_triggered_by is False
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_config_report.py -m base_unit -v
```

기대: 4개 전부 FAIL — `AttributeError: 'RunConfig' object has no attribute 'app_version'`

- [ ] **Step 3: `config/default.yaml` 에 기본값을 넣는다**

`project_name: "Example Automation"` 바로 다음에 넣는다.

```yaml
# 테스트 대상 앱의 버전. 자동화 코드의 버전과 다릅니다.
#  CI 에서 APP_VERSION 환경변수로 주는 것을 권장합니다.
#  비워두면 리포트에 표시하지 않습니다. 형식은 자유입니다.
app_version: ""

# 리포트 표시 옵션
report:
  # 실행자 이름을 result.json / 리포트에 남길지.
  # 개인정보가 걸리는 고객사면 false 로 두세요.
  show_triggered_by: true
```

- [ ] **Step 4: `RunConfig` 에 필드를 넣는다**

`utils/config.py` 의 `test_id_attribute: str = "data-testid"` (68행) 다음에 넣는다.

```python
    # 테스트 대상 앱의 버전 (주입값). 비어 있으면 리포트에 표시하지 않습니다.
    app_version: str = ""
    # 실행자 이름을 리포트에 남길지 (개인정보 우려로 끌 수 있음)
    show_triggered_by: bool = True
```

- [ ] **Step 5: `load_config` 에서 읽는다**

`utils/config.py` 의 `load_config` 안, `artifacts_cfg = merged.get("artifacts") or {}`
다음 줄에 추가한다.

```python
    report_cfg = merged.get("report") or {}
```

그리고 `RunConfig(...)` 반환부에서 `test_id_attribute=...` 다음에 두 줄을 넣는다.

```python
        app_version=_env_str("APP_VERSION", merged.get("app_version", "")),
        show_triggered_by=_env_bool("SHOW_TRIGGERED_BY",
                                    bool(report_cfg.get("show_triggered_by", True))),
```

- [ ] **Step 6: `.env.example` 에 안내를 넣는다**

파일 맨 아래에 추가한다.

```bash
# 테스트 대상 앱의 버전. 리포트에 표시됩니다. (선택)
# APP_VERSION=v2.14.3

# 실행자 이름을 리포트에 남기지 않으려면 false (선택)
# SHOW_TRIGGERED_BY=true
```

- [ ] **Step 7: 통과를 확인한다**

```bash
pytest tests/unit/test_config_report.py -m base_unit -v
```

기대: 4 passed

- [ ] **Step 8: 게이트와 커밋**

```bash
pytest
pytest -m base_unit
```

기대: `30 passed` / `27 passed`

```bash
cat > /tmp/cm.txt <<'EOF'
feat(config): app_version, report.show_triggered_by 설정 추가

app_version 은 테스트 대상 앱의 버전입니다. 자동화 코드 버전과 다릅니다.
고객사마다 버전 체계가 달라 형식을 강제하지 않고, 비어 있으면
리포트에 표시하지 않습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add config/default.yaml utils/config.py .env.example tests/unit/test_config_report.py
git commit -F /tmp/cm.txt
```

---

## Task 7: `result.json` 에 붙이기 (schema 1.0 → 1.1)

**Files:**
- Modify: `reporting/result_collector.py` — `SCHEMA_VERSION`(19행),
  `ResultCollector.__init__`(58행 부근), `to_dict()`(끝)
- Modify: `conftest.py:135` (collector 생성부)
- Test: `tests/unit/test_result_meta.py` (신규)

**Interfaces:**
- Consumes: Task 5 의 `runmeta.git_info()`, `runmeta.triggered_by(enabled)`,
  `runmeta.command_line()`, `runmeta.worker_count(pytest_config)`;
  Task 6 의 `RunConfig.app_version`, `RunConfig.show_triggered_by`.
- Produces: `ResultCollector(run_config, run_paths, run_meta=None)` 의 3번째 인자와
  `to_dict()["run"]` 의 새 키 5개 (`app_version`, `git`, `triggered_by`,
  `command`, `workers`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_result_meta.py`:

```python
"""result.json 의 실행 메타(schema 1.1) 단위 테스트.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from reporting.result_collector import ResultCollector
from utils.config import load_config

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit

#: schema 1.0 이 보장하던 run 필드. 하나라도 사라지면 소비자가 깨집니다.
SCHEMA_10_RUN_FIELDS = (
    "run_id", "project", "environment", "browser", "headless", "base_url",
    "started_at", "finished_at", "duration", "retries_configured",
    "python", "playwright", "platform", "artifacts_dir", "exit_status",
)


class _FakePaths:
    """``ResultCollector`` 가 쓰는 것은 run_id 와 root 뿐입니다."""

    run_id = "20260909_100000"
    root = Path("artifacts") / "20260909_100000"


def _collector(run_meta: dict[str, Any] | None = None) -> ResultCollector:
    return ResultCollector(load_config(env="staging"), _FakePaths(), run_meta)


def test_schema_version_is_1_1() -> None:
    assert _collector().to_dict()["schema_version"] == "1.1"


def test_schema_10_fields_all_survive() -> None:
    """기존 필드는 없애지 않고 추가만 한다 (result_schema.md 의 규칙)."""
    run = _collector().to_dict()["run"]
    missing = [f for f in SCHEMA_10_RUN_FIELDS if f not in run]
    assert missing == []


def test_run_meta_is_merged() -> None:
    """conftest 가 넘긴 메타가 run 블록에 들어간다."""
    run = _collector({
        "git": {"branch": "main", "commit": "5d1ed8b", "dirty": False},
        "triggered_by": "ci-bot",
        "command": "pytest -m smoke -n 4",
        "workers": 4,
    }).to_dict()["run"]

    assert run["git"] == {"branch": "main", "commit": "5d1ed8b", "dirty": False}
    assert run["triggered_by"] == "ci-bot"
    assert run["command"] == "pytest -m smoke -n 4"
    assert run["workers"] == 4


def test_meta_keys_exist_even_without_run_meta() -> None:
    """메타를 못 모았어도 키는 있고 값이 null 이다. 소비자가 KeyError 를 안 만난다."""
    run = _collector().to_dict()["run"]

    assert run["git"] is None
    assert run["triggered_by"] is None
    assert run["app_version"] is None
    assert run["workers"] == 1


def test_empty_app_version_becomes_null() -> None:
    """설정이 빈 문자열이면 result.json 에는 null 로 넣는다."""
    config = load_config(env="staging")
    config.app_version = ""
    run = ResultCollector(config, _FakePaths(), None).to_dict()["run"]
    assert run["app_version"] is None


def test_app_version_is_passed_through() -> None:
    config = load_config(env="staging")
    config.app_version = "v2.14.3 (build 8821)"
    run = ResultCollector(config, _FakePaths(), None).to_dict()["run"]
    assert run["app_version"] == "v2.14.3 (build 8821)"
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_result_meta.py -m base_unit -v
```

기대: `test_schema_version_is_1_1` 이 FAIL (`assert '1.0' == '1.1'`),
`ResultCollector` 가 3번째 인자를 안 받아 나머지도 FAIL (`TypeError`).

- [ ] **Step 3: `ResultCollector` 를 고친다**

`reporting/result_collector.py:19` 을 바꾼다.

```python
SCHEMA_VERSION = "1.1"
```

`__init__` 시그니처와 본문 첫 줄을 바꾼다.

```python
    def __init__(self, run_config: Any, run_paths: Any,
                 run_meta: dict[str, Any] | None = None) -> None:
        self.config = run_config
        self.paths = run_paths
        #: conftest 가 실행 시작 때 한 번 모아 넘기는 실행 메타 (git/실행자/명령줄/병렬 수).
        #: 못 모았으면 빈 dict 이고, to_dict() 가 빠진 키를 None 으로 채웁니다.
        self.run_meta = run_meta or {}
        self.started_at = datetime.now()
```

(`self.finished_at` 이하 나머지는 그대로 둔다.)

`to_dict()` 의 `run` 블록에서 `"exit_status": self.exit_status,` 다음에 5줄을 넣는다.

```python
                # --- schema 1.1 에서 추가된 실행 메타 ---
                # 값을 못 구했어도 키는 남깁니다. 소비자가 KeyError 를 만나지 않게.
                "app_version": cfg.app_version or None,
                "git": self.run_meta.get("git"),
                "triggered_by": self.run_meta.get("triggered_by"),
                "command": self.run_meta.get("command"),
                "workers": self.run_meta.get("workers", 1),
```

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_result_meta.py -m base_unit -v
```

기대: 6 passed

- [ ] **Step 5: `conftest.py` 에서 메타를 주입한다**

`conftest.py:23` 의 import 옆에 추가한다.

```python
from utils import runmeta
```

`conftest.py:135` 을 바꾼다. **`sensitive_filter.register(...)` 다음이어야 한다** —
`command_line()` 이 마스킹을 쓰기 때문이다.

바꾸기 전:
```python
    config._pwbase_collector = ResultCollector(run_config, paths)  # type: ignore[attr-defined]
```

바꾼 뒤:
```python
    # 실행 메타는 실행당 한 번만 모읍니다. git 이 없어도 예외가 나지 않습니다.
    run_meta = {
        "git": runmeta.git_info(),
        "triggered_by": runmeta.triggered_by(run_config.show_triggered_by),
        "command": runmeta.command_line(),
        "workers": runmeta.worker_count(config),
    }
    config._pwbase_collector = ResultCollector(run_config, paths, run_meta)  # type: ignore[attr-defined]
```

- [ ] **Step 6: 실제 실행으로 확인한다**

```bash
pytest -m smoke
```

그 뒤 만들어진 `result.json` 을 본다 (한글이 섞이므로 **파일로 받아서** 읽는다 —
Global Constraints 참고).

```bash
PYTHONIOENCODING=utf-8 python -c "import json,pathlib; p=pathlib.Path(pathlib.Path('artifacts/latest_run.txt').read_text(encoding='utf-8').strip())/'report'/'result.json'; d=json.loads(p.read_text(encoding='utf-8')); print(json.dumps({'schema_version':d['schema_version'],**{k:d['run'][k] for k in ('app_version','git','triggered_by','command','workers')}}, ensure_ascii=False, indent=2))" > /tmp/meta.txt
cat /tmp/meta.txt
```

기대: `schema_version` 이 `"1.1"`, `git.commit` 이 실제 커밋 해시,
`command` 가 `pytest -m smoke`, `workers` 가 `1`.

- [ ] **Step 7: 게이트와 커밋**

```bash
pytest
pytest -m base_unit
pytest -n 2
```

기대: `30 passed` / `33 passed` (27 + 6) / `30 passed`

> `-n 2` 를 꼭 돌린다. 메타를 컨트롤러에서만 모으므로 xdist 에서 깨지지 않는지
> 확인해야 한다.

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): result.json 에 실행 메타 추가 (schema 1.0 -> 1.1)

run 블록에 app_version, git{branch,commit,dirty}, triggered_by,
command, workers 를 넣습니다. 기존 필드는 하나도 없애지 않았습니다.
값을 못 구했어도 키는 남겨 소비자가 KeyError 를 만나지 않게 했습니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/result_collector.py conftest.py tests/unit/test_result_meta.py
git commit -F /tmp/cm.txt
```

---

## Task 8: 화면에 보여주고 문서를 갱신한다

**Files:**
- Modify: `reporting/templates/report.html:134-143` (헤더 `metagrid`)
- Modify: `reporting/ci_summary.py` (`to_markdown`)
- Modify: `reporting/result_schema.md`
- Test: `tests/unit/test_report_render.py` (추가)

**Interfaces:**
- Consumes: Task 7 의 `run.app_version`, `run.git`, `run.triggered_by`,
  `run.command`, `run.workers`.
- Produces: 없음 (마지막 Task).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_report_render.py` 맨 아래에 추가한다.

```python
def _run_with_meta(**overrides: Any) -> dict[str, Any]:
    """schema 1.1 메타가 채워진 run 블록."""
    run = dict(_data()["run"])
    run.update({
        "app_version": "v2.14.3 (build 8821)",
        "git": {"branch": "main", "commit": "5d1ed8b", "dirty": False},
        "triggered_by": "klyhja",
        "command": "pytest -m smoke -n 4 --env=staging",
        "workers": 4,
    })
    run.update(overrides)
    return run


def test_header_shows_run_meta(tmp_path: Path) -> None:
    """앱 버전·커밋·실행자·명령줄·병렬 수가 헤더에 나온다."""
    html = _render(tmp_path, run=_run_with_meta())

    assert "v2.14.3 (build 8821)" in html
    assert "5d1ed8b" in html
    assert "klyhja" in html
    assert "pytest -m smoke -n 4 --env=staging" in html
    assert "4 workers" in html


def test_header_hides_missing_meta(tmp_path: Path) -> None:
    """값이 null 이면 그 줄 자체를 그리지 않는다 (빈 칸을 남기지 않음)."""
    html = _render(tmp_path, run=_run_with_meta(
        app_version=None, git=None, triggered_by=None))

    assert "App Version" not in html
    assert "실행자" not in html


def test_header_marks_dirty_worktree(tmp_path: Path) -> None:
    """커밋 안 된 변경이 있으면 표시한다. 재현이 안 될 수 있다는 신호다."""
    html = _render(tmp_path, run=_run_with_meta(
        git={"branch": "main", "commit": "5d1ed8b", "dirty": True}))
    assert "변경 있음" in html
```

- [ ] **Step 2: 실패를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: `test_header_shows_run_meta` 가 FAIL (`assert "v2.14.3 (build 8821)" in html`)

- [ ] **Step 3: 헤더에 넣는다**

`reporting/templates/report.html` 의 `metagrid` 안, `Environment` 줄 다음에 App
Version 과 Automation 을 넣고, `Platform` 줄 뒤에 나머지를 넣는다.

`<div><span class="k">Environment</span>...</div>` 다음에:

```html
      {% if run.app_version %}
      <div><span class="k">App Version</span><span class="v">{{ run.app_version }}</span></div>
      {% endif %}
      {% if run.git %}
      <div><span class="k">Automation</span><span class="v">{{ run.git.branch or "-" }} @ {{ run.git.commit }}{% if run.git.dirty %} <span style="color:var(--skip)">(변경 있음)</span>{% endif %}</span></div>
      {% endif %}
```

`Platform` 줄 다음에:

```html
      {% if run.triggered_by %}
      <div><span class="k">실행자</span><span class="v">{{ run.triggered_by }}</span></div>
      {% endif %}
      {% if run.command %}
      <div><span class="k">실행 명령</span><span class="v" style="font-family:ui-monospace,Consolas,monospace;font-size:12px">{{ run.command }}</span></div>
      {% endif %}
      {% if run.workers and run.workers > 1 %}
      <div><span class="k">병렬</span><span class="v">{{ run.workers }} workers</span></div>
      {% endif %}
```

> `workers` 가 1 이면 순차 실행이라 굳이 보여주지 않는다.

- [ ] **Step 4: 통과를 확인한다**

```bash
pytest tests/unit/test_report_render.py -m base_unit -v
```

기대: 10 passed

- [ ] **Step 5: `ci_summary.py` 에 한 줄 넣는다**

`reporting/ci_summary.py` 의 `to_markdown` 에서 제목 줄 다음, 빈 줄 앞에 넣는다.
현재:

```python
    lines = [
        f"## {icon} {run['project']} · {run['environment'].upper()} · {run['browser']}",
        "",
```

이렇게 바꾼다:

```python
    # schema 1.1 부터. 옛 result.json 을 읽어도 죽지 않게 .get 을 쓴다.
    version_bits = []
    if run.get("app_version"):
        version_bits.append(f"App `{run['app_version']}`")
    if run.get("git"):
        version_bits.append(f"Automation `{run['git']['branch']} @ {run['git']['commit']}`")

    lines = [
        f"## {icon} {run['project']} · {run['environment'].upper()} · {run['browser']}",
        "",
    ]
    if version_bits:
        lines += [" · ".join(version_bits), ""]
    lines += [
```

그리고 원래 `lines` 리스트에 있던 표 3줄은 `lines += [` 뒤로 옮겨 그대로 둔다.

- [ ] **Step 6: `ci_summary` 를 실제로 돌려 본다**

```bash
PYTHONIOENCODING=utf-8 python -m reporting.ci_summary > /tmp/summary.txt
cat /tmp/summary.txt
```

기대: 제목 아래에 ``App `...` · Automation `main @ ...` `` 줄이 보인다
(`app_version` 을 안 줬으면 Automation 만).

- [ ] **Step 7: `result_schema.md` 를 갱신한다**

`reporting/result_schema.md` 의 첫 줄 제목을 `# result.json 스키마 (schema_version 1.1)`
로 바꾸고, jsonc 블록의 `"schema_version": "1.0"` 을 `"1.1"` 로 바꾼다.
`"exit_status": 1` 다음에 추가한다.

```jsonc
    // --- schema 1.1 에서 추가 ---
    "app_version": "v2.14.3 (build 8821)",  // 테스트 대상 앱 버전(주입). 없으면 null
    "git": {                                // 자동 수집. .git 이 없으면 null
      "branch": "main",
      "commit": "5d1ed8b",
      "dirty": false                        // 커밋 안 된 변경이 있으면 true
    },
    "triggered_by": "klyhja",               // 실행자. show_triggered_by=false 면 null
    "command": "pytest -m smoke -n 4",      // 실행 명령 (비밀번호·토큰은 가려짐)
    "workers": 4                            // xdist 병렬 수. 순차면 1
```

문서 아래 "Trend Report 를 만들 때 쓰는 필드" 표에 두 줄을 추가한다.

```markdown
| 앱 버전별 성공률 | `run.app_version` + `summary` |
| 커밋별 회귀 추적 | `run.git.commit` + `summary.pass_rate` |
```

- [ ] **Step 8: 마지막 게이트 전체**

```bash
pytest
pytest -m failure_demo
pytest -m base_unit
pytest -n 2
```

기대: `30 passed` / `3 failed, 1 skipped` / `36 passed` / `30 passed`

> **`base_unit` 36 의 내역:** 8(기존 `test_paths_retention`) + 10(`test_report_render`)
> + 8(`test_runmeta`) + 4(`test_config_report`) + 6(`test_result_meta`).
> 숫자가 다르면 어느 Task 의 테스트가 빠졌는지 먼저 확인한다.

그리고 `pytest -m failure_demo` 로 만든 리포트를 브라우저로 열어 헤더에 새 줄들이
보이는지, Ctrl+P 인쇄 미리보기가 여전히 멀쩡한지 눈으로 확인한다.

- [ ] **Step 9: 커밋**

```bash
cat > /tmp/cm.txt <<'EOF'
feat(report): 실행 메타를 헤더/CI 요약에 표시하고 스키마 문서 갱신

앱 버전, 자동화 커밋(변경 있으면 표시), 실행자, 실행 명령, 병렬 수를
헤더에 넣었습니다. 값이 null 이면 줄 자체를 그리지 않습니다.
ci_summary 는 옛 result.json 도 읽을 수 있게 .get 을 씁니다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
git add reporting/templates/report.html reporting/ci_summary.py \
        reporting/result_schema.md tests/unit/test_report_render.py
git commit -F /tmp/cm.txt
```

---

## 마무리

- [ ] **`/code-review high` 를 돌린다.** 핸드오프 기록상 Base 본체를 고칠 때마다
  실제 버그를 잡아냈다 (1회차 15건, 4회차 4건). 지적마다 회귀 테스트를 붙인다.
- [ ] **`pytest -m base_unit` 개수를 핸드오프에 기록한다.** 다음 세션이 "8이 아니면
  건드린 것" 이라는 기준을 쓰고 있으므로 새 숫자로 갱신해야 한다.
- [ ] PR 을 올린다. 본문에 Step A / Step B 를 나눠 적고, **영상(video)을 왜 뺐는지**와
  재검토 조건 3가지를 설계 문서 링크와 함께 남긴다.

## 되돌리는 법

- **Step A (Task 1~4)** — 해당 커밋만 revert. `result.json` 을 안 건드렸으므로
  다른 영향이 없다.
- **Step B (Task 5~8)** — revert 후 `schema_version` 이 `"1.0"` 으로 돌아오는지 확인한다.
  소비자는 추가 필드를 무시하면 되므로 되돌리지 않고 두어도 안전하다.
- **실행자 이름만 끄고 싶을 때** — `config/default.yaml` 의
  `report.show_triggered_by: false` (또는 `SHOW_TRIGGERED_BY=false`).
