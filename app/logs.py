from pathlib import Path


MAX_LOG_SIZE = 5 * 1024 * 1024


def read_log(root: Path, relative_path: str) -> str:
    """读取日志根目录内的文本，并拒绝路径穿越。"""
    root_path = root.resolve()
    log_path = (root_path / relative_path).resolve()
    if log_path != root_path and root_path not in log_path.parents:
        raise ValueError("日志路径不能超出日志根目录")
    if not log_path.is_file():
        raise FileNotFoundError("日志文件不存在")
    if log_path.stat().st_size > MAX_LOG_SIZE:
        raise ValueError("日志文件超过读取限制")
    return log_path.read_text(encoding="utf-8", errors="replace")
