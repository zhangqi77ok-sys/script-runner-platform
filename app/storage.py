from pathlib import Path


DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def initialize_storage():
    for name in ("packages", "versions", "logs", "artifacts", "temp"):
        (DATA_ROOT / name).mkdir(parents=True, exist_ok=True)


def safe_child_path(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError("路径不能越过存储根目录")
    return candidate


def stored_path(value: str) -> Path:
    """将数据库路径解析到当前部署的数据目录。"""
    normalized = value.replace("\\", "/")
    marker = "/data/"
    if marker in normalized:
        return DATA_ROOT / normalized.split(marker, 1)[1]
    candidate = Path(value)
    return candidate if candidate.is_absolute() else DATA_ROOT / candidate
