"""브라우저 실행·Context 인자와 업무 API 골라내기 (루트 conftest) 단위 테스트.

브라우저를 띄우는 실행(``--headed``)은 기본으로 config 뷰포트에 고정합니다. 뷰포트에 따라 DOM 이 통째로
달라지는 사이트가 있어 headless 와 같은 화면이어야 합니다. config ``headed_window: maximized`` 를 켜면
뷰포트를 고정하지 않고 창을 최대화합니다 (고정하면 새 탭마다 창이 움직이는 사이트용). ``--device`` 는 늘 그대로 둡니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from utils import testmeta
from utils.config import RunConfig

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = [pytest.mark.base_unit, pytest.mark.category("Config")]


@pytest.fixture(scope="module")
def root_conftest(pytestconfig: pytest.Config) -> ModuleType:
    """이미 올라와 있는 루트 conftest 모듈 (다시 import 하지 않습니다)."""
    path = pytestconfig.rootpath / "conftest.py"
    return next(plugin for plugin in pytestconfig.pluginmanager.get_plugins()
                if getattr(plugin, "__file__", None) and Path(plugin.__file__).samefile(path))


def _call(fixture, *args):
    """fixture 의 원래 함수를 부릅니다. pytest 가 이 방법을 없애면 여기서 바로 깨집니다."""
    return fixture._get_wrapped_function()(*args)


@pytest.mark.tc_id("UNIT814")
def test_headed_run_uses_window_size(root_conftest: ModuleType) -> None:
    """headed_window: maximized 면 뷰포트를 고정하지 않고(no_viewport) 창을 최대화한다."""
    config = RunConfig(headless=False, headed_window="maximized")
    context_args = _call(root_conftest.browser_context_args, {}, config, "data-testid")
    assert context_args["no_viewport"] is True
    assert "viewport" not in context_args

    launch_args = _call(root_conftest.browser_type_launch_args, {"headless": False}, config)
    assert "--start-maximized" in launch_args["args"]


@pytest.mark.tc_id("UNIT815")
def test_headless_run_keeps_configured_viewport(root_conftest: ModuleType) -> None:
    """headless 는 설정 뷰포트를 그대로 쓰고 창 인자를 붙이지 않는다."""
    config = RunConfig(headless=True, viewport_width=1280, viewport_height=720)
    context_args = _call(root_conftest.browser_context_args, {}, config, "data-testid")
    assert context_args["viewport"] == {"width": 1280, "height": 720}
    assert "no_viewport" not in context_args

    launch_args = _call(root_conftest.browser_type_launch_args, {}, config)
    assert "--start-maximized" not in launch_args.get("args", [])


@pytest.mark.tc_id("UNIT816")
def test_headed_run_keeps_device_viewport(root_conftest: ModuleType) -> None:
    """--device 로 받은 뷰포트는 maximized 여도 지키지 않으면 모바일 화면이 깨진다."""
    device = {"viewport": {"width": 390, "height": 844}, "is_mobile": True}
    config = RunConfig(headless=False, headed_window="maximized")
    context_args = _call(root_conftest.browser_context_args, device, config, "data-testid")
    assert context_args["viewport"] == {"width": 390, "height": 844}
    assert "no_viewport" not in context_args


@pytest.mark.tc_id("UNIT818")
def test_headed_run_keeps_configured_viewport_by_default(root_conftest: ModuleType) -> None:
    """기본(fixed)은 --headed 여도 config 뷰포트 그대로다. headless 와 DOM 이 같아야 한다."""
    config = RunConfig(headless=False, viewport_width=1280, viewport_height=720)
    context_args = _call(root_conftest.browser_context_args, {}, config, "data-testid")
    assert context_args["viewport"] == {"width": 1280, "height": 720}
    assert "no_viewport" not in context_args

    launch_args = _call(root_conftest.browser_type_launch_args, {"headless": False}, config)
    assert "--start-maximized" not in launch_args.get("args", [])


class _Req:
    """``_track_request`` 가 읽는 것만 있는 가짜 요청."""

    def __init__(self, url: str, resource_type: str = "xhr") -> None:
        self.url, self.resource_type, self.method = url, resource_type, "GET"
        self.frame = SimpleNamespace(page=None)


@pytest.mark.tc_id("UNIT817")
def test_only_configured_api_paths_are_tracked(root_conftest: ModuleType) -> None:
    """report.api_paths 가 경로에 든 XHR·fetch 만 기록한다. 이미지·JS 와 다른 경로는 뺀다."""
    node = SimpleNamespace(stash={})
    calls: dict = {}
    requests = [
        _Req("https://shop.example/svc/orders?page=1"),
        _Req("https://shop.example/svc/logo.png", resource_type="image"),
        _Req("https://shop.example/api/v1/orders"),
    ]
    meta = testmeta.TestMeta(test_id="T", title="t", category="c")
    node.stash[testmeta.META_KEY] = meta
    for req in requests:
        root_conftest._track_request(calls, {}, req, node, ("/svc/",))
    assert [call["path"] for call in calls.values()] == ["/svc/orders"]
