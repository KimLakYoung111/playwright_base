"""테스트 하나의 메타정보(TC ID / 이름 / Category / Step / Evidence).

수집한 값은 리포트(Custom HTML, result.json)와 Evidence 파일명에 쓰입니다.
테스트 코드는 이 모듈을 몰라도 되고, marker 만 붙이면 됩니다.

    @pytest.mark.tc_id("TC001")
    @pytest.mark.category("Login")
    @pytest.mark.smoke
    def test_login(page):
        \"\"\"정상 로그인\"\"\"
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import pytest

from utils.paths import slugify

#: 리포트의 Marker 목록에 표시하지 않는 marker (메타/설정용)
HIDDEN_MARKERS = frozenset({
    "tc_id", "category", "title",
    "parametrize", "usefixtures", "filterwarnings",
    "browser_context_args",              # pytest-playwright 설정용
})

#: Category 로 쓰지 않는 marker (실행 유형 / 특성 / 플러그인 제공)
NON_CATEGORY_MARKERS = HIDDEN_MARKERS | frozenset({
    "smoke", "regression", "e2e", "failure_demo", "slow", "flaky",
    "skip", "skipif", "xfail",
    "only_browser", "skip_browser",      # pytest-playwright 제공
})

DEFAULT_CATEGORY = "Uncategorized"


@dataclass
class TestMeta:
    """테스트 실행 중 모이는 정보."""

    test_id: str
    title: str
    category: str
    function: str = ""
    param_id: str = ""                 # parametrize 원본 id (browser 포함)
    markers: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    current_url: str | None = None

    @property
    def slug(self) -> str:
        """Evidence 파일 이름 앞부분.

        예) TC901_test_missing_element_fails_chromium
        한글 제목 대신 함수명을 쓰기 때문에 길이가 짧고 OS/CI 어디서나 안전합니다.
        """
        parts = [slugify(self.test_id, 24), slugify(self.function or "test", 48)]
        if self.param_id:
            parts.append(slugify(self.param_id, 40))
        return "_".join(p for p in parts if p)


#: pytest item 에 TestMeta 를 붙여두는 키
META_KEY = pytest.StashKey[TestMeta]()

#: 각 단계(setup/call/teardown)의 report 를 item 에 보관하는 키
#: conftest 가 채우고, Evidence 를 남기는 fixture 들이 읽습니다.
PHASE_REPORTS_KEY = pytest.StashKey[dict]()


def has_failure(item: pytest.Item) -> bool:
    """이 테스트가 지금까지 한 번이라도 실패했는지."""
    return any(report.failed for report in item.stash.get(PHASE_REPORTS_KEY, {}).values())


def record_artifact(meta: TestMeta, kind: str, relative_path: str | None,
                    label: str = "") -> None:
    """Evidence 경로를 meta 에 기록합니다.

    한 테스트가 Page 를 여러 개 쓰면(예: 역할별 로그인 세션) 같은 종류의 파일이
    여러 개 나옵니다. 그럴 때 서로 덮어쓰지 않도록 키에 꼬리표를 붙입니다.

        screenshot          기본 page
        screenshot_admin    role_page("admin")
    """
    if not relative_path:
        return
    key = f"{kind}_{label}" if label else kind
    if key in meta.artifacts:
        index = 2
        while f"{key}_{index}" in meta.artifacts:
            index += 1
        key = f"{key}_{index}"
    meta.artifacts[key] = relative_path

#: 현재 실행 중인 테스트의 TestMeta (test_step 이 사용)
_current_meta: ContextVar[TestMeta | None] = ContextVar("_current_meta", default=None)


def set_current(meta: TestMeta | None) -> None:
    _current_meta.set(meta)


def current() -> TestMeta | None:
    return _current_meta.get()


# ----------------------------------------------------------------------
# marker 에서 메타정보 뽑기
# ----------------------------------------------------------------------
def _marker_arg(item: pytest.Item, name: str) -> str | None:
    marker = item.get_closest_marker(name)
    if marker and marker.args:
        return str(marker.args[0])
    return None


def _docstring_title(item: pytest.Item) -> str | None:
    doc = getattr(getattr(item, "function", None), "__doc__", None)
    if not doc:
        return None
    first_line = doc.strip().splitlines()[0].strip()
    return first_line or None


def build_meta(item: pytest.Item) -> TestMeta:
    """pytest item 에서 TestMeta 를 만듭니다."""
    markers = [m.name for m in item.iter_markers() if m.name not in HIDDEN_MARKERS]

    function = item.name.split("[")[0]
    param_id = item.name.split("[", 1)[1].rstrip("]") if "[" in item.name else ""

    test_id = _marker_arg(item, "tc_id") or function
    title = _marker_arg(item, "title") or _docstring_title(item) or function

    category = _marker_arg(item, "category")
    if not category:
        business = [m for m in markers if m not in NON_CATEGORY_MARKERS]
        category = business[0].title() if business else DEFAULT_CATEGORY

    # 제목에는 Browser 이름을 빼고 남는 파라미터만 붙입니다.
    # (Browser 는 리포트에 따로 열이 있어 중복 표시할 필요가 없습니다)
    callspec = getattr(item, "callspec", None)
    browser_name = callspec.params.get("browser_name") if callspec else None
    label = param_id
    if browser_name and label:
        tokens = label.split("-")
        if tokens[0] == browser_name:
            tokens = tokens[1:]
        label = "-".join(tokens)
    if label:
        title = f"{title} [{label}]"

    return TestMeta(test_id=test_id, title=title, category=category,
                    function=function, param_id=param_id, markers=markers)


def get_meta(item: pytest.Item) -> TestMeta:
    """item 에 붙은 TestMeta 를 가져옵니다. 없으면 만들어 붙입니다."""
    meta = item.stash.get(META_KEY, None)
    if meta is None:
        meta = build_meta(item)
        item.stash[META_KEY] = meta
    return meta


def reset_meta(item: pytest.Item) -> TestMeta:
    """TestMeta 를 새로 만들어 붙입니다.

    재시도(pytest-rerunfailures)는 **같은 item 객체**로 테스트를 다시 돌립니다.
    stash 에 남아 있던 이전 시도의 TestMeta 를 그대로 쓰면 Step 과 Evidence 가
    시도마다 쌓여서, 최종 통과한 테스트에 이전 시도의 실패 Step 이 남습니다.
    그래서 시도가 시작될 때마다 여기서 새로 만듭니다.
    """
    meta = build_meta(item)
    item.stash[META_KEY] = meta
    return meta
