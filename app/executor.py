import ast
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path


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
        raise ExecutionError("Docker CLI is not available")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    network = "bridge" if network_enabled else "none"
    requirements = (source / "requirements.txt").exists()
    install = "pip install --no-cache-dir -r /workspace/requirements.txt && " if requirements else ""
    script_args = " ".join(shlex.quote(item) for item in arguments)
    env_args = [item for key, value in (environment or {}).items() for item in ("-e", f"{key}={value}")]
    container = f"script-task-{uuid.uuid4().hex}"
    command = f"{install}cd /workspace && python {shlex.quote(entrypoint)} {script_args}"
    create = ["docker", "create", "--name", container, f"--network={network}",
              "--cpus=1", "--memory=512m", "--pids-limit=128", *env_args,
              RUNTIME_IMAGE, "sh", "-c", command]
    try:
        subprocess.run(create, check=True, capture_output=True, text=True)
        subprocess.run(["docker", "cp", str(source), f"{container}:/workspace"],
                       check=True, capture_output=True, text=True)
        with log_file.open("w", encoding="utf-8") as output:
            subprocess.run(["docker", "start", "-a", container], stdout=output,
                           stderr=subprocess.STDOUT, timeout=timeout, check=False)
        result = subprocess.run(["docker", "inspect", "-f", "{{.State.ExitCode}}", container],
                                capture_output=True, text=True, check=True)
        return int(result.stdout.strip())
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "kill", container], check=False, capture_output=True)
        raise ExecutionError(f"Task exceeded {timeout} seconds") from exc
    except subprocess.CalledProcessError as exc:
        raise ExecutionError(exc.stderr.strip() or "Docker sandbox failed to start") from exc
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False, capture_output=True)
