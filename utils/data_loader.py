"""테스트 데이터 로딩.

테스트 데이터는 코드가 아니라 ``data/`` 폴더에 둡니다.

    from utils.data_loader import load_data

    users = load_data("users.json")
    cases = load_data("test_cases.yaml")

CSV 도 바로 읽을 수 있고, Excel / DB / API 로 넓힐 때는
``load_data`` 와 같은 모양(리스트/딕셔너리 반환)의 함수를 하나 더 추가하면 됩니다.
"""

from __future__ import annotations

import copy
import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from utils.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"


def data_path(name: str) -> Path:
    """data/ 기준 경로. 절대경로를 주면 그대로 씁니다."""
    path = Path(name)
    return path if path.is_absolute() else DATA_DIR / name


@lru_cache(maxsize=64)
def _load_cached(resolved: str) -> Any:
    path = Path(resolved)
    if not path.exists():
        raise FileNotFoundError(f"테스트 데이터 파일이 없습니다: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fp:
            return list(csv.DictReader(fp))
    raise ValueError(f"지원하지 않는 데이터 형식입니다: {path.suffix} ({path})")


def load_data(name: str) -> Any:
    """JSON / YAML / CSV 데이터를 읽습니다.

    파일 읽기/파싱 결과는 캐시하지만 **호출할 때마다 복사본을 돌려줍니다.**
    캐시된 객체를 그대로 넘겨주면 한 테스트가 값을 바꿨을 때 이후 모든 테스트가
    오염되어 "테스트는 서로 독립적" 이라는 원칙이 깨집니다.
    """
    return copy.deepcopy(_load_cached(str(data_path(name).resolve())))


def pick(name: str, key: str, default: Any = None) -> Any:
    """중첩 데이터에서 한 값만 꺼냅니다. 예) pick("users.json", "valid.username")"""
    node = load_data(name)
    for part in key.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node
