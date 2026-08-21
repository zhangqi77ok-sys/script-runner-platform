import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path
import ast


class ExecutionError(RuntimeError):
    pass


RUNTIME_DEPENDENCIES = {"PIL": "Pillow"}
RUNTIME_IMAGE = "script-platform/python-pillow:3.12"


def detect_runtime_dependencies(source: Path) -> list[str]:
    imports = set()
    for file in source.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    return [RUNTIME_DEPENDENCIES[name] for name in sorted(imports) if name in RUNTIME_DEPENDENCIES]


def run_in_docker(source: Path, entrypoint: str, timeout: int, log_file: Path,
                  network_enabled: bool = False, arguments: tuple[str, ...] = (),
                  environment: dict[str, str] | None = None) -> int:
    if shutil.which("docker") is None:
        raise ExecutionError("未检测到 Docker，无法启动任务沙盒")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="script-task-") as workdir:
        workspace = Path(workdir) / "workspace" / "project" / "scripts" / "zentao-bug-summary"
        shutil.copytree(source, workspace)
        network = "bridge" if network_enabled else "none"
        requirements = (source / "requirements.txt").exists()
        install = "pip install --no-cache-dir -r /workspace/project/scripts/zentao-bug-summary/requirements.txt && " if requirements else ""
        script_args = " ".join(shlex.quote(item) for item in arguments)
        env_args = []
        for key, value in (environment or {}).items():
            env_args.extend(["-e", f"{key}={value}"])
        command = ["docker", "run", "--rm", f"--network={network}",
                   "--cpus=1", "--memory=512m", "--pids-limit=128",
                   *env_args, "-v", f"{workspace.parent.parent.resolve()}:/workspace/project:rw", RUNTIME_IMAGE,
                   "sh", "-c", f"{install}cd /workspace/project/scripts/zentao-bug-summary && python {shlex.quote(entrypoint)} {script_args}"]
        try:
            with log_file.open("w", encoding="utf-8") as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                        timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ExecutionError(f"任务超过 {timeout} 秒，已终止") from exc
        return result.returncode
