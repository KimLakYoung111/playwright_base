"""실행별 Artifact 폴더 관리.

실행할 때마다 ``artifacts/<YYYYmmdd_HHMMSS>/`` 를 새로 만들고 그 아래에
screenshots / traces / html / logs / report 를 둡니다.
이전 실행 결과를 절대 덮어쓰지 않습니다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from utils.config import PROJECT_ROOT

ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"

#: xdist 워커가 컨트롤러와 같은 실행 폴더를 쓰도록 전달하는 환경변수
RUN_DIR_ENV = "PW_BASE_RUN_DIR"

_SLUG_RE = re.compile(r"[^0-9A-Za-z가-힣_.-]+")


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
