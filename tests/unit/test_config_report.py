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


def test_app_version_defaults_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """기본값은 빈 문자열이다. 고객사마다 버전 체계가 달라 강제하지 않는다."""
    # delenv 는 .env 파일에 값이 있으면 load_dotenv(override=False) 가 다시
    # 채워 넣어 무력화된다. 빈 문자열로 설정해야 .env 값을 덮어써 기본값
    # 경로를 확실히 탄다 (_env_str 은 빈 값을 "없음" 으로 취급한다).
    monkeypatch.setenv("APP_VERSION", "")
    config = load_config(env="staging")
    assert config.app_version == ""


def test_app_version_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 는 APP_VERSION 환경변수로 준다."""
    monkeypatch.setenv("APP_VERSION", "v2.14.3 (build 8821)")
    config = load_config(env="staging")
    assert config.app_version == "v2.14.3 (build 8821)"


def test_show_triggered_by_defaults_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """delenv 는 .env 값에 덮어써지므로(override=False) 빈 문자열로 지운다."""
    monkeypatch.setenv("SHOW_TRIGGERED_BY", "")
    config = load_config(env="staging")
    assert config.show_triggered_by is True


def test_show_triggered_by_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """개인정보가 걸리면 환경변수로 끌 수 있다."""
    monkeypatch.setenv("SHOW_TRIGGERED_BY", "false")
    config = load_config(env="staging")
    assert config.show_triggered_by is False
