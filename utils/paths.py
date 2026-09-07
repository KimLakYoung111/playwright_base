"""실행별 Artifact 폴더 관리.

실행할 때마다 ``artifacts/<YYYYmmdd_HHMMSS>/`` 를 새로 만들고 그 아래에
screenshots / traces / html / logs / report 를 둡니다.
이전 실행 결과를 절대 덮어쓰지 않습니다.
쌓이기만 하면 디스크가 차므로 ``prune_old_runs()`` 로 보관 기간이 지난
실행 폴더를 정리합니다 (실행 시작 시 conftest 가 호출).
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from utils.config import PROJECT_ROOT
from utils.logger import get_logger

logger = get_logger("paths")

ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

#: xdist 워커가 컨트롤러와 같은 실행 폴더를 쓰도록 전달하는 환경변수
RUN_DIR_ENV = "PW_BASE_RUN_DIR"

_SLUG_RE = re.compile(r"[^0-9A-Za-z가-힣_.-]+")

#: ``_reserve_run_dir`` 이 만드는 실행 폴더 이름 (YYYYmmdd_HHMMSS / 충돌 시 _1, _2 ...).
#: 정리 대상을 이 형식으로 한정해 사용자가 artifacts/ 에 둔 다른 폴더를 지키기 위함입니다.
_RUN_DIR_RE = re.compile(r"^\d{8}_\d{6}(?:_(?P<seq>\d+))?$")


def slugify(text: str, max_length: int = 60) -> str:
    """파일명으로 안전한 문자열을 만듭니다 (한글은 유지)."""
    slug = _SLUG_RE.sub("_", (text or "").strip()).strip("_")
    return (slug or "unnamed")[:max_length]


@dataclass(frozen=True)
class RunPaths:
    """한 번의 실행이 사용하는 폴더 모음."""

    root: Path

    @property
    def run_id(self) -> str:
        return self.root.name

    @property
    def screenshots(self) -> Path:
        return self.root / "screenshots"

    @property
    def traces(self) -> Path:
        return self.root / "traces"

    @property
    def html(self) -> Path:
        return self.root / "html"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def report(self) -> Path:
        return self.root / "report"

    @property
    def custom_report(self) -> Path:
        return self.report / "report.html"

    @property
    def pytest_report(self) -> Path:
        return self.report / "pytest_report.html"

    @property
    def result_json(self) -> Path:
        return self.report / "result.json"

    @property
    def run_log(self) -> Path:
        return self.logs / "run.log"

    def create(self) -> RunPaths:
        for directory in (self.screenshots, self.traces, self.html, self.logs, self.report):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def relative(self, path: Path | str | None) -> str | None:
        """리포트에 넣을 상대경로. 폴더째 옮겨도 링크가 깨지지 않습니다."""
        if path is None:
            return None
        path = Path(path)
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def _reserve_run_dir(timestamp: str) -> Path:
    """폴더를 실제로 만들면서 자리를 잡습니다.

    ``exists()`` 로 확인한 뒤 만들면 같은 초에 시작한 두 실행이 같은 폴더를 잡을 수
    있습니다(경쟁 상태). ``mkdir(exist_ok=False)`` 는 OS 가 원자적으로 처리하므로
    먼저 만든 쪽만 성공하고 나머지는 다음 번호로 넘어갑니다.
    """
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    for suffix in range(0, 1000):
        name = timestamp if suffix == 0 else f"{timestamp}_{suffix}"
        candidate = ARTIFACTS_ROOT / name
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"실행 폴더를 만들지 못했습니다: {ARTIFACTS_ROOT / timestamp}")


def resolve_run_paths(create: bool = True) -> RunPaths:
    """이번 실행의 폴더를 결정합니다.

    xdist 워커는 컨트롤러가 만든 폴더를 환경변수로 물려받아 그대로 사용합니다.
    ``create=False`` 면 경로만 계산하고 폴더는 만들지 않습니다(--collect-only 등).
    """
    existing = os.getenv(RUN_DIR_ENV)
    if existing:
        paths = RunPaths(Path(existing))
        return paths.create() if create else paths

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not create:
        # 경로만 계산하고 폴더는 만들지 않습니다 (--collect-only 등).
        return RunPaths(ARTIFACTS_ROOT / timestamp)

    paths = RunPaths(_reserve_run_dir(timestamp)).create()
    os.environ[RUN_DIR_ENV] = str(paths.root)

    # Test Runner UI / CI 스크립트가 마지막 실행을 쉽게 찾도록 남겨둡니다.
    try:
        (ARTIFACTS_ROOT / "latest_run.txt").write_text(str(paths.root), encoding="utf-8")
    except OSError:
        pass
    return paths


def prune_old_runs(keep_days: int, keep_min_runs: int = 5, *,
                   now: datetime | None = None) -> list[Path]:
    """보관 기간이 지난 실행 폴더를 지우고 지운 경로를 돌려줍니다.

    실행 한 번에 수십 MB 가 쌓이므로 지우지 않으면 디스크가 찹니다.
    다만 지우는 쪽이 잘못되면 증거가 통째로 사라지므로 범위를 좁게 잡았습니다.

    - ``keep_days`` 가 0 이하면 아무것도 하지 않습니다 (CI 처럼 매번 새 머신이면 불필요).
    - ``artifacts/`` 바로 아래 **디렉터리** 중 ``_RUN_DIR_RE`` 와 이름이 맞는 것만 봅니다.
      ``latest_run.txt`` 같은 파일이나 사용자가 따로 만든 폴더는 건드리지 않습니다.
    - 나이는 **폴더 이름의 타임스탬프**로만 계산합니다. mtime 은 파일을 열어보거나
      백업 도구가 건드리기만 해도 바뀌어서 믿을 수 없습니다.
    - 최신순 기준 최근 ``keep_min_runs`` 개는 나이와 상관없이 남깁니다.
      오래 쉬었다가 돌렸을 때 직전 실행 기록까지 통째로 날아가는 것을 막습니다.
      **이번 실행 폴더는 후보에서 아예 빼서** 보호 슬롯을 먹지 않게 합니다.
      (conftest 가 실행 폴더를 만든 뒤에 이 함수를 부르므로, 빼지 않으면
      ``keep_min_runs`` 가 약속보다 하나 적게 지켜집니다.)

    ``now`` 는 테스트에서 시간을 주입하기 위한 것입니다.
    """
    if keep_days <= 0:
        return []
    if not ARTIFACTS_ROOT.exists():
        return []

    now = now or datetime.now()
    max_age = timedelta(days=keep_days)

    current = os.getenv(RUN_DIR_ENV)
    current_root = Path(current).resolve() if current else None

    runs: list[tuple[datetime, int, Path]] = []
    for entry in ARTIFACTS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        matched = _RUN_DIR_RE.match(entry.name)
        if not matched:
            continue
        try:
            started = datetime.strptime(entry.name[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            # 이름이 유일한 판단 근거입니다. 읽을 수 없으면 그냥 남겨둡니다.
            continue
        if current_root is not None and entry.resolve() == current_root:
            continue
        runs.append((started, int(matched.group("seq") or 0), entry))

    # 같은 초에 시작한 실행은 _1, _2 ... 접미사로 갈립니다. 이름 문자열로 정렬하면
    # "_10" 이 "_2" 보다 앞서서 최신이 뒤로 밀리므로 접미사는 숫자로 비교합니다.
    runs.sort(key=lambda item: (item[0], item[1]), reverse=True)

    removed: list[Path] = []
    failed: list[Path] = []
    for started, _seq, entry in runs[max(keep_min_runs, 0):]:
        if now - started <= max_age:
            continue
        # Windows 는 리포트/Trace 를 열어둔 채면 파일이 잠깁니다.
        # 정리가 실패해도 테스트 실행은 막지 않되, 조용히 넘어가지는 않습니다.
        shutil.rmtree(entry, ignore_errors=True)
        if entry.exists():
            # ignore_errors 는 못 지운 파일만 건너뛰고 나머지는 지웁니다.
            # 알리지 않으면 리포트는 남았는데 링크된 Evidence 만 사라진 폴더가
            # 생기고 사용자가 알아챌 방법이 없습니다.
            failed.append(entry)
        else:
            removed.append(entry)

    if failed:
        logger.warning(
            "오래된 Artifacts %d개를 지우지 못했습니다 (파일이 열려 있을 수 있습니다): %s",
            len(failed), ", ".join(p.name for p in failed),
        )
    return removed
