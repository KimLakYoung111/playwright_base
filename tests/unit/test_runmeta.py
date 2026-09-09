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
pytestmark = [pytest.mark.base_unit, pytest.mark.category("RunMeta")]

#: ``git status --porcelain=v2 --branch`` 가 주는 머리말. commit 은 전체 SHA 입니다.
V2_HEADER = (
    "# branch.oid 5d1ed8b1122334455667788990011223344556677\n"
    "# branch.head main\n"
    "# branch.upstream origin/main\n"
    "# branch.ab +0 -0\n"
)


class _Ok:
    """returncode 0 인 CompletedProcess 흉내."""

    returncode = 0

    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.stderr = ""


class _Failed:
    """returncode 가 0 이 아닌 CompletedProcess 흉내.

    stdout 을 일부러 비우지 않는다. 비워두면 returncode 검사를 빼먹은 구현도
    빈 문자열 덕분에 통과해 버려서, 이 테스트가 아무것도 지키지 못한다.
    """

    returncode = 128
    stdout = "5d1ed8b"
    stderr = "fatal: not a git repository"


def _fake_git(answers: dict[tuple[str, ...], Any], calls: list[list[str]] | None = None):
    """git 인자 → 결과 매핑으로 ``subprocess.run`` 을 대신합니다.

    매핑에 없는 명령은 ``_Failed`` 입니다 (옛 git 이 모르는 옵션을 흉내).
    """
    def _run(cmd: list[str], **kwargs: Any) -> Any:
        if calls is not None:
            calls.append(cmd)
        return answers.get(tuple(cmd[1:]), _Failed())

    return _run


@pytest.fixture
def clean_sensitive_filter():
    """``sensitive_filter`` 는 프로세스 전역 싱글턴이고 unregister 가 없다.

    등록한 리터럴을 되돌리지 않으면 이 파일 이후의 모든 테스트에서 그 문자열이
    로그·에러 메시지·result.json 트레이스백에서 조용히 ``***`` 로 바뀐다.
    """
    from utils.logger import sensitive_filter

    saved = set(sensitive_filter._literals)
    yield sensitive_filter
    sensitive_filter._literals = saved


# ---------------------------------------------------------------------------
# git_info
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT101")
def test_git_info_returns_none_when_git_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """git 실행 파일이 없어도 예외 없이 None 을 준다."""
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert runmeta.git_info() is None


@pytest.mark.tc_id("UNIT102")
def test_git_info_returns_none_when_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """.git 이 없어 git 이 실패하면 (v2 도 fallback 도) None 이다."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Failed())
    assert runmeta.git_info() is None


@pytest.mark.tc_id("UNIT103")
def test_git_info_reads_everything_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """브랜치·커밋·변경 여부를 git 호출 한 번으로 받는다.

    호출 하나가 최대 GIT_TIMEOUT 초를 먹으므로, 세 번 부르면 느린 작업
    폴더에서 테스트 수집 전에 그만큼 멈춰 선다.
    """
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_git(
        {("status", "--porcelain=v2", "--branch"): _Ok(V2_HEADER + "1 .M N... README.md\n")},
        calls,
    ))

    info = runmeta.git_info()

    assert info == {"branch": "main", "commit": "5d1ed8b", "dirty": True}
    assert len(calls) == 1


@pytest.mark.tc_id("UNIT104")
def test_git_info_reports_clean_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    """변경된 파일 줄이 없으면 dirty 는 False 다."""
    monkeypatch.setattr(subprocess, "run", _fake_git(
        {("status", "--porcelain=v2", "--branch"): _Ok(V2_HEADER)}
    ))
    assert runmeta.git_info()["dirty"] is False


@pytest.mark.tc_id("UNIT105")
def test_git_info_treats_untracked_file_as_dirty(monkeypatch: pytest.MonkeyPatch) -> None:
    """추적 안 되는 파일도 "커밋과 다름" 이다. 그 파일이 테스트일 수 있다."""
    monkeypatch.setattr(subprocess, "run", _fake_git(
        {("status", "--porcelain=v2", "--branch"): _Ok(V2_HEADER + "? new_test.py\n")}
    ))
    assert runmeta.git_info()["dirty"] is True


@pytest.mark.tc_id("UNIT106")
def test_git_info_reports_detached_head_as_no_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """detached HEAD 면 브랜치가 없다. "(detached)" 를 이름처럼 적지 않는다."""
    detached = V2_HEADER.replace("# branch.head main", "# branch.head (detached)")
    monkeypatch.setattr(subprocess, "run", _fake_git(
        {("status", "--porcelain=v2", "--branch"): _Ok(detached)}
    ))
    assert runmeta.git_info()["branch"] is None


@pytest.mark.tc_id("UNIT107")
def test_git_info_returns_none_for_repository_without_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """커밋이 하나도 없는 저장소는 적을 커밋이 없다."""
    initial = V2_HEADER.replace(
        "# branch.oid 5d1ed8b1122334455667788990011223344556677",
        "# branch.oid (initial)",
    )
    monkeypatch.setattr(subprocess, "run", _fake_git(
        {("status", "--porcelain=v2", "--branch"): _Ok(initial)}
    ))
    assert runmeta.git_info() is None


@pytest.mark.tc_id("UNIT108")
def test_git_info_falls_back_when_porcelain_v2_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """git 2.13.1 보다 낮으면 --porcelain=v2 를 모른다. 옛 방식으로 되돌린다."""
    monkeypatch.setattr(subprocess, "run", _fake_git({
        # ("status", "--porcelain=v2", "--branch") 는 매핑에 없으므로 실패한다
        ("rev-parse", "--short", "HEAD"): _Ok("5d1ed8b"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _Ok("main"),
        ("status", "--porcelain"): _Ok(" M README.md"),
    }))

    assert runmeta.git_info() == {"branch": "main", "commit": "5d1ed8b", "dirty": True}


@pytest.mark.tc_id("UNIT109")
def test_dirty_is_unknown_when_status_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """status 를 못 읽었으면 dirty 는 None 이다. False 가 아니다.

    False 로 적으면 "자동화 코드가 이 커밋과 정확히 일치한다" 를 리포트가
    거짓으로 단정한다. 재현성을 위해 넣은 필드가 정반대로 작동한다.
    """
    monkeypatch.setattr(subprocess, "run", _fake_git({
        ("rev-parse", "--short", "HEAD"): _Ok("5d1ed8b"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _Ok("main"),
        # ("status", "--porcelain") 은 매핑에 없으므로 실패한다
    }))

    assert runmeta.git_info()["dirty"] is None


@pytest.mark.tc_id("UNIT110")
def test_git_output_is_decoded_as_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """git 출력은 UTF-8 로 읽는다. 로케일(Windows 한국어 = cp949)에 맡기지 않는다.

    맡기면 한글 브랜치명이 깨져 고객사 리포트에 박히거나, UnicodeDecodeError
    가 ``except Exception`` 에 먹혀 브랜치가 조용히 사라진다.
    """
    seen: dict[str, Any] = {}
    korean = V2_HEADER.replace("# branch.head main", "# branch.head feature/로그인개선")

    def _run(cmd: list[str], **kwargs: Any) -> Any:
        seen.update(kwargs)
        return _Ok(korean)

    monkeypatch.setattr(subprocess, "run", _run)

    assert runmeta.git_info()["branch"] == "feature/로그인개선"
    assert seen.get("encoding") == "utf-8"
    assert seen.get("errors") == "replace"


# ---------------------------------------------------------------------------
# command_line
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT111")
def test_command_line_masks_registered_secret(
    monkeypatch: pytest.MonkeyPatch, clean_sensitive_filter,
) -> None:
    """명령줄에 섞인 비밀번호·토큰은 가려진다.

    ``--token=값`` 형태는 로거의 key=value 패턴이 register() 없이도 잡아낸다.
    그래서 여기서는 key=value 형태가 아닌 맨 값(위치 인자)을 쓴다 —
    이래야 register() 로 등록한 리터럴 매칭 경로를 실제로 검증하게 된다.
    """
    clean_sensitive_filter.register("s3cret-token")
    monkeypatch.setattr(sys, "argv",
                        ["/long/path/to/pytest", "-m", "smoke", "s3cret-token"])

    line = runmeta.command_line()

    assert "s3cret-token" not in line
    # sys.argv[0] 의 전체 경로는 버리고 pytest 로 시작한다
    assert line.startswith("pytest -m smoke")


@pytest.mark.tc_id("UNIT112")
def test_command_line_masks_url_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL 에 박은 비밀번호도 가린다.

    ``--base-url=https://qa:pw@host`` 는 key=value 패턴에 안 걸리고 register()
    로 등록된 값도 아니다. 그대로 두면 고객사에 전달하는 result.json 과
    report.html 에 자격증명이 그대로 실린다.
    """
    monkeypatch.setattr(sys, "argv",
                        ["pytest", "--base-url=https://qa:Hunter2@stage.client.com"])

    line = runmeta.command_line()

    assert "Hunter2" not in line
    # 호스트와 사용자명은 남겨야 어느 환경을 돌렸는지 알아볼 수 있다
    assert "https://qa:***@stage.client.com" in line


@pytest.mark.tc_id("UNIT113")
def test_command_line_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """sys.argv 에 문자열이 아닌 값이 섞여 join 이 깨져도 예외 없이 문자열을 준다."""
    monkeypatch.setattr(sys, "argv", ["pytest", 123])

    line = runmeta.command_line()

    assert isinstance(line, str)


# ---------------------------------------------------------------------------
# triggered_by / worker_count
# ---------------------------------------------------------------------------

@pytest.mark.tc_id("UNIT114")
def test_triggered_by_can_be_disabled() -> None:
    """개인정보가 걸리면 끌 수 있다."""
    assert runmeta.triggered_by(enabled=False) is None


@pytest.mark.tc_id("UNIT115")
def test_triggered_by_prefers_ci_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI 가 알려주는 실행자를 먼저 쓴다."""
    monkeypatch.setenv("GITHUB_ACTOR", "ci-bot")
    assert runmeta.triggered_by() == "ci-bot"


@pytest.mark.tc_id("UNIT116")
def test_worker_count_defaults_to_one() -> None:
    """xdist 없이 순차 실행이면 1 이다."""
    class _NoXdist:
        class option:
            pass

    assert runmeta.worker_count(_NoXdist()) == 1


@pytest.mark.tc_id("UNIT117")
def test_worker_count_reads_xdist_option() -> None:
    """-n 4 로 돌리면 4 다."""
    class _Xdist:
        class option:
            numprocesses = 4

    assert runmeta.worker_count(_Xdist()) == 4
