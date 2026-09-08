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
