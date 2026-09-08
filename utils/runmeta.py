"""실행 메타 수집 (git / 실행자 / 명령줄 / 병렬 수).

``result.json`` 의 ``run`` 블록에 들어갑니다.

``git_info()`` / ``triggered_by()`` / ``worker_count()`` 는 **어떤 경우에도 예외를
올리지 않습니다.** 값을 못 구하면 ``None`` 을 돌려줍니다. 고객사가 이 Base 를
zip 으로 복사해 쓰면 ``.git`` 이 아예 없는데, 그것 때문에 테스트가 죽으면 안
되기 때문입니다. (``command_line()`` 은 ``sys.argv`` 를 그대로 합치는 단순한
함수라 이 보장에서 제외합니다.)
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
