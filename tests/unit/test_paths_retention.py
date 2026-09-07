"""오래된 artifacts 폴더 정리(``prune_old_runs``) 단위 테스트.

Browser 를 띄우지 않는 순수 단위 테스트입니다.
``ARTIFACTS_ROOT`` 를 임시 폴더로 갈아끼우고 ``now=`` 로 시간을 주입하므로
실제 ``artifacts/`` 폴더는 건드리지 않습니다.

Base 프레임워크 자체의 회귀 테스트라 고객사용 리포트에 섞이면 안 됩니다.
그래서 ``base_unit`` marker 로 기본 실행에서 빠져 있습니다.

    pytest -m base_unit
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytest

from utils import paths

#: 파일 전체가 Base 자체 회귀 테스트입니다 (pytest.ini 의 addopts 에서 기본 제외).
pytestmark = pytest.mark.base_unit

#: 기준 시각. 폴더 이름의 타임스탬프와 비교되므로 테스트마다 고정합니다.
NOW = datetime(2026, 1, 20, 12, 0, 0)


def _make_run_dir(root: Path, name: str) -> Path:
    """실행 폴더 하나를 흉내 냅니다.

    안에 파일이 있어야 "폴더째 지워졌는지" 를 제대로 확인할 수 있습니다.
    """
    run_dir = root / name / "logs"
    run_dir.mkdir(parents=True)
    (run_dir / "run.log").write_text("dummy", encoding="utf-8")
    return root / name


@pytest.fixture
def artifacts_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``utils.paths`` 가 바라보는 artifacts 루트를 임시 폴더로 바꿉니다."""
    monkeypatch.setattr(paths, "ARTIFACTS_ROOT", tmp_path)
    monkeypatch.delenv(paths.RUN_DIR_ENV, raising=False)
    return tmp_path


@pytest.mark.tc_id("UNIT001")
@pytest.mark.category("Artifacts")
def test_keep_days_zero_removes_nothing(artifacts_root: Path) -> None:
    """keep_days 가 0 이면 아무리 오래된 폴더도 그대로 둔다"""
    old = _make_run_dir(artifacts_root, "20200101_010101")

    removed = paths.prune_old_runs(0, keep_min_runs=0, now=NOW)

    assert removed == []
    assert old.exists()


@pytest.mark.tc_id("UNIT002")
@pytest.mark.category("Artifacts")
def test_old_runs_are_removed_and_recent_kept(artifacts_root: Path) -> None:
    """보관 기간이 지난 폴더만 지우고 최근 폴더는 남긴다"""
    old = [_make_run_dir(artifacts_root, name)
           for name in ("20251201_090000", "20251215_090000")]
    recent = [_make_run_dir(artifacts_root, name)
              for name in ("20260118_090000", "20260119_090000_1")]

    removed = paths.prune_old_runs(14, keep_min_runs=0, now=NOW)

    assert sorted(p.name for p in removed) == ["20251201_090000", "20251215_090000"]
    assert not any(p.exists() for p in old)
    assert all(p.exists() for p in recent)


@pytest.mark.tc_id("UNIT003")
@pytest.mark.category("Artifacts")
def test_keep_min_runs_protects_old_runs(artifacts_root: Path) -> None:
    """기간이 지났어도 최근 keep_min_runs 개는 남긴다"""
    names = ["20250101_090000", "20250102_090000", "20250103_090000"]
    for name in names:
        _make_run_dir(artifacts_root, name)

    removed = paths.prune_old_runs(14, keep_min_runs=2, now=NOW)

    assert [p.name for p in removed] == ["20250101_090000"]
    assert (artifacts_root / "20250102_090000").exists()
    assert (artifacts_root / "20250103_090000").exists()


@pytest.mark.tc_id("UNIT004")
@pytest.mark.category("Artifacts")
def test_non_run_entries_are_untouched(artifacts_root: Path) -> None:
    """실행 폴더 형식이 아닌 폴더/파일은 건드리지 않는다"""
    old = _make_run_dir(artifacts_root, "20250101_090000")
    notes = artifacts_root / "my_notes"
    (notes / "sub").mkdir(parents=True)
    latest = artifacts_root / "latest_run.txt"
    latest.write_text("something", encoding="utf-8")
    (artifacts_root / ".gitkeep").write_text("", encoding="utf-8")

    removed = paths.prune_old_runs(14, keep_min_runs=0, now=NOW)

    assert [p.name for p in removed] == ["20250101_090000"]
    assert not old.exists()
    assert notes.exists()
    assert latest.exists()
    assert (artifacts_root / ".gitkeep").exists()


@pytest.mark.tc_id("UNIT005")
@pytest.mark.category("Artifacts")
def test_current_run_dir_is_never_removed(artifacts_root: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """이번 실행 폴더는 나이와 상관없이 지우지 않는다"""
    current = _make_run_dir(artifacts_root, "20250101_090000")
    other = _make_run_dir(artifacts_root, "20250102_090000")
    monkeypatch.setenv(paths.RUN_DIR_ENV, str(current))

    removed = paths.prune_old_runs(14, keep_min_runs=0, now=NOW)

    assert [p.name for p in removed] == ["20250102_090000"]
    assert current.exists()
    assert not other.exists()


@pytest.mark.tc_id("UNIT006")
@pytest.mark.category("Artifacts")
def test_current_run_does_not_consume_keep_slot(artifacts_root: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """이번 실행 폴더가 keep_min_runs 보호 슬롯을 먹지 않는다

    conftest 가 실행 폴더를 만든 뒤에 정리를 부르므로, 이번 실행을 후보에서 빼지 않으면
    "최근 5개 보존" 이 실제로는 4개만 지켜집니다.
    """
    old = [_make_run_dir(artifacts_root, f"2025010{n}_090000") for n in range(1, 6)]
    current = _make_run_dir(artifacts_root, "20260120_120000")
    monkeypatch.setenv(paths.RUN_DIR_ENV, str(current))

    removed = paths.prune_old_runs(14, keep_min_runs=5, now=NOW)

    assert removed == []
    assert all(p.exists() for p in old), "약속한 5개가 그대로 남아야 한다"


@pytest.mark.tc_id("UNIT007")
@pytest.mark.category("Artifacts")
def test_same_second_suffix_is_compared_as_number(artifacts_root: Path) -> None:
    """같은 초에 시작한 실행의 _2 / _10 접미사를 숫자로 비교한다

    이름 문자열로 정렬하면 "_10" 이 "_2" 보다 앞서서 최신이 뒤로 밀립니다.
    """
    older = _make_run_dir(artifacts_root, "20250101_090000_2")
    newer = _make_run_dir(artifacts_root, "20250101_090000_10")

    removed = paths.prune_old_runs(14, keep_min_runs=1, now=NOW)

    assert [p.name for p in removed] == ["20250101_090000_2"]
    assert newer.exists(), "보호 슬롯은 더 나중에 만들어진 _10 이 가져가야 한다"
    assert not older.exists()


@pytest.mark.tc_id("UNIT008")
@pytest.mark.category("Artifacts")
def test_undeletable_run_is_reported_not_silently_skipped(
    artifacts_root: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """지우지 못한 폴더는 삭제 목록에 넣지 않고 경고를 남긴다

    Windows 에서 리포트나 Trace 를 열어둔 채면 파일이 잠깁니다. 그때 폴더가 일부만
    지워지는데, 조용히 넘어가면 사용자가 알아챌 방법이 없습니다.
    """
    stuck = _make_run_dir(artifacts_root, "20250101_090000")
    monkeypatch.setattr(paths.shutil, "rmtree", lambda *a, **kw: None)
    # setup_logging 이 automation 로거의 propagate 를 끄기 때문에 caplog(루트 핸들러)가
    # 기본 상태로는 이 경고를 못 받습니다. 이 테스트 동안만 되돌립니다.
    monkeypatch.setattr(logging.getLogger("automation"), "propagate", True)

    with caplog.at_level(logging.WARNING, logger="automation.paths"):
        removed = paths.prune_old_runs(14, keep_min_runs=0, now=NOW)

    assert removed == [], "못 지운 폴더를 지웠다고 보고하면 안 된다"
    assert stuck.exists()
    assert "20250101_090000" in caplog.text
