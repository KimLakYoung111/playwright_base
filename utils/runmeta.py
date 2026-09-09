"""실행 메타 수집 (git / 실행자 / 명령줄 / 병렬 수).

``result.json`` 의 ``run`` 블록에 들어갑니다.

이 모듈의 함수는 **어떤 경우에도 예외를 올리지 않습니다.** 값을 못 구하면
``None`` (``command_line()`` 은 빈 문자열) 을 돌려줍니다. 고객사가 이 Base 를
zip 으로 복사해 쓰면 ``.git`` 이 아예 없는데, 그것 때문에 테스트가 죽으면 안
되기 때문입니다. ``pytest_configure`` 안에서 가드 없이 호출되므로, 이 보장이
깨지면 테스트가 한 건도 실행되지 못한 채 전체 실행이 죽습니다.
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
            # text=True 만 두면 파이썬이 로케일 인코딩으로 디코드합니다.
            # Windows 한국어 환경은 cp949 라, git 이 UTF-8 로 뱉는 한글 브랜치명
            # (feature/로그인개선) 이 깨지거나 UnicodeDecodeError 로 통째로
            # 사라집니다. git 출력은 항상 UTF-8 이므로 못 박습니다.
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
        )
    except Exception:
        # git 이 없거나, 타임아웃이거나, 권한이 없거나 — 이유를 가리지 않습니다.
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").strip()


def _parse_status_v2(output: str) -> dict[str, Any] | None:
    """``git status --porcelain=v2 --branch`` 출력에서 브랜치/커밋/변경 여부를 읽습니다.

    형식이 예상과 다르면 None 을 돌려주고, 호출한 쪽이 옛 방식으로 되돌아갑니다.
    """
    commit = branch = None
    dirty = False
    for line in output.splitlines():
        if not line.startswith("#"):
            # ``#`` 로 시작하지 않는 줄은 전부 변경된 파일입니다
            # (수정 `1`/`2`, 충돌 `u`, untracked `?`, ignored `!`).
            dirty = True
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        if parts[1] == "branch.oid":
            commit = parts[2]
        elif parts[1] == "branch.head":
            branch = parts[2]
    if not commit or commit == "(initial)":
        # 커밋이 하나도 없는 저장소. rev-parse HEAD 도 실패하던 경우와 같습니다.
        return None
    return {
        "branch": None if branch in (None, "(detached)") else branch,
        # ``rev-parse --short`` 와 달리 v2 는 전체 SHA 를 줍니다. 리포트에 쓰는
        # 값이라 관례대로 7자로 자릅니다.
        "commit": commit[:7],
        "dirty": dirty,
    }


def git_info(cwd: Path | None = None) -> dict[str, Any] | None:
    """``{'branch', 'commit', 'dirty'}`` 또는 None.

    ``.git`` 이 없거나 git 이 설치돼 있지 않으면 None 입니다.
    ``dirty`` 는 판단하지 못했을 때 **None** 입니다 — False(=커밋과 일치) 로
    적으면 리포트가 없는 사실을 단정하게 됩니다.

    브랜치·커밋·변경 여부를 ``status --porcelain=v2 --branch`` 한 번으로 받습니다.
    git 호출 하나가 최대 ``GIT_TIMEOUT`` 초를 먹으므로, 세 번 부르면 느린
    작업 폴더에서 테스트 수집 전에 그만큼 멈춰 섭니다.
    """
    combined = _git("status", "--porcelain=v2", "--branch", cwd=cwd)
    if combined is not None:
        parsed = _parse_status_v2(combined)
        if parsed is not None:
            return parsed

    # git 이 2.13.1 보다 낮으면 --porcelain=v2 를 모릅니다. 옛 방식으로 되돌립니다.
    commit = _git("rev-parse", "--short", "HEAD", cwd=cwd)
    if not commit:
        return None
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    status = _git("status", "--porcelain", cwd=cwd)
    return {
        "branch": None if not branch or branch == "HEAD" else branch,
        "commit": commit,
        # status 가 None 이면 명령이 실패한 것이지 깨끗한 것이 아닙니다.
        "dirty": None if status is None else bool(status),
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
    못 구하면(sys.argv 이상 등) 예외를 올리지 않고 빈 문자열을 돌려줍니다.
    """
    try:
        return mask_secrets(" ".join(["pytest", *sys.argv[1:]]))
    except Exception:
        return ""


def worker_count(pytest_config: Any) -> int:
    """xdist 병렬 수. 순차 실행이면 1."""
    value = getattr(getattr(pytest_config, "option", None), "numprocesses", None)
    try:
        return int(value) if value else 1
    except (TypeError, ValueError):
        return 1
