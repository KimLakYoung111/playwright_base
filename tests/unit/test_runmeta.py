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
    """명령줄에 섞인 비밀번호·토큰은 가려진다.

    ``--token=값`` 형태는 로거의 key=value 패턴이 register() 없이도 잡아낸다.
    그래서 여기서는 key=value 형태가 아닌 맨 값(위치 인자)을 쓴다 —
    이래야 register() 로 등록한 리터럴 매칭 경로를 실제로 검증하게 된다.
    """
    from utils.logger import sensitive_filter

    sensitive_filter.register("s3cret-token")
    monkeypatch.setattr(sys, "argv",
                        ["/long/path/to/pytest", "-m", "smoke", "s3cret-token"])

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
