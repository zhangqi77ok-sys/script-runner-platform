from dataclasses import dataclass
import io
from pathlib import PurePosixPath
from pathlib import Path
import shutil
import ast
import zipfile

import yaml


class PackageError(ValueError):
    pass


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str
    entrypoint: str
    has_requirements: bool


def inspect_zip(content: bytes) -> PackageInfo:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise PackageError(f"压缩包包含非法路径: {name}")
        files = {name.rstrip("/") for name in names if not name.endswith("/")}
        manifest = {}
        if "manifest.yaml" in files:
            try:
                manifest = yaml.safe_load(archive.read("manifest.yaml")) or {}
            except yaml.YAMLError as exc:
                raise PackageError(f"manifest.yaml 解析失败: {exc}") from exc
        entrypoint = str(manifest.get("entrypoint") or "")
        if entrypoint and entrypoint not in files:
            raise PackageError(f"入口文件不存在: {entrypoint}")
        if not entrypoint:
            candidates = [name for name in files if name.endswith(".py") and "/" not in name]
            if len(candidates) != 1:
                raise PackageError("无法唯一确定 Python 入口文件")
            entrypoint = candidates[0]
        if not entrypoint.endswith(".py"):
            raise PackageError("入口文件必须是 Python 文件")
        name = str(manifest.get("name") or PurePosixPath(entrypoint).stem)
        version = str(manifest.get("version") or "1.0.0")
        return PackageInfo(name, version, entrypoint, "requirements.txt" in files)


def extract_zip(content: bytes, destination):
    info = inspect_zip(content)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        archive.extractall(destination)
    return info


def inspect_directory(source: Path) -> PackageInfo:
    if not source.is_dir():
        raise PackageError("脚本目录不存在")
    candidates = [item for item in source.glob("*.py") if item.is_file()]
    entrypoint = "zentao_bug_summary.py" if (source / "zentao_bug_summary.py").exists() else ""
    if not entrypoint and len(candidates) == 1:
        entrypoint = candidates[0].name
    if not entrypoint:
        raise PackageError("无法从脚本目录确定唯一入口文件")
    requirements = source / "requirements.txt"
    if not requirements.exists():
        imports = _imports_from_python(source)
        stdlib = {"__future__", "argparse", "ast", "base64", "dataclasses", "datetime", "email", "hashlib", "html", "http", "io", "json", "logging", "os", "pathlib", "re", "smtplib", "subprocess", "sys", "time", "typing", "urllib"}
        local_modules = {file.stem for file in source.glob("*.py")}
        runtime_modules = {"PIL"}
        external = sorted(imports - stdlib - local_modules - runtime_modules)
        if external:
            raise PackageError(f"脚本缺少 requirements.txt，检测到外部依赖: {', '.join(external)}")
    return PackageInfo(source.name, "1.0.0", entrypoint, (source / "requirements.txt").exists())


def _imports_from_python(source: Path) -> set[str]:
    imports = set()
    for file in source.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    return imports


def copy_directory(source: Path, destination: Path) -> PackageInfo:
    info = inspect_directory(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return info
