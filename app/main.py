from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect, initialize_db
from .executor import ExecutionError, run_in_docker
from .logs import read_log
from .packages import PackageError, copy_directory, extract_zip
from .storage import DATA_ROOT, initialize_storage, safe_child_path, stored_path
from .scheduler import TaskScheduler

app = FastAPI(title="Script Platform", version="1.0.0")
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
scheduler = TaskScheduler(lambda task_id: run_task(task_id))


def now():
    return datetime.now(timezone.utc).isoformat()


@app.on_event("startup")
def startup():
    initialize_storage()
    initialize_db()
    scheduler.start()


@app.get("/api/health")
def health():
    return {"status": "ok", "docker": shutil.which("docker") is not None}


@app.get("/api/scripts")
def scripts():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM scripts ORDER BY id DESC")]


@app.post("/api/scripts/import")
async def import_script(package: UploadFile = File(...)):
    if not package.filename or not package.filename.lower().endswith(".zip"):
        raise HTTPException(400, "只支持 ZIP 脚本包")
    content = await package.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(413, "脚本包不能超过 100MB")
    script_id = uuid.uuid4().hex
    package_root = safe_child_path(DATA_ROOT / "packages", f"{script_id}.zip")
    version_root = safe_child_path(DATA_ROOT / "versions", script_id)
    try:
        package_root.write_bytes(content)
        info = extract_zip(content, version_root)
    except (PackageError, OSError) as exc:
        if package_root.exists():
            package_root.unlink()
        if version_root.exists():
            shutil.rmtree(version_root)
        raise HTTPException(400, str(exc)) from exc
    with connect() as db:
        cursor = db.execute("INSERT INTO scripts(name,version,entrypoint,package_path,version_path,created_at) VALUES (?,?,?,?,?,?)",
                            (info.name, info.version, info.entrypoint, str(package_root.relative_to(DATA_ROOT)), str(version_root.relative_to(DATA_ROOT)), now()))
        db.commit()
        return {"id": cursor.lastrowid, "name": info.name, "version": info.version, "entrypoint": info.entrypoint}


@app.post("/api/scripts/import-directory")
def import_directory(path: str = Form(...)):
    source = Path(path).resolve()
    script_id = uuid.uuid4().hex
    version_root = safe_child_path(DATA_ROOT / "versions", script_id)
    try:
        info = copy_directory(source, version_root)
    except (PackageError, OSError) as exc:
        if version_root.exists():
            shutil.rmtree(version_root)
        raise HTTPException(400, str(exc)) from exc
    with connect() as db:
        cursor = db.execute("INSERT INTO scripts(name,version,entrypoint,package_path,version_path,created_at) VALUES (?,?,?,?,?,?)",
                            (info.name, info.version, info.entrypoint, str(source), str(version_root.relative_to(DATA_ROOT)), now()))
        db.commit()
        return {"id": cursor.lastrowid, "name": info.name, "version": info.version, "entrypoint": info.entrypoint}


@app.get("/api/tasks")
def tasks():
    with connect() as db:
        rows = db.execute("SELECT tasks.*, scripts.name script_name, scripts.version script_version FROM tasks JOIN scripts ON scripts.id=tasks.script_id ORDER BY tasks.id DESC").fetchall()
        return [dict(row) for row in rows]


@app.post("/api/tasks")
def create_task(name: str = Form(...), script_id: int = Form(...), schedule: str = Form(""), timeout_seconds: int = Form(600), network_enabled: bool = Form(False)):
    if not name.strip() or timeout_seconds < 1 or timeout_seconds > 86400:
        raise HTTPException(400, "任务名称和超时时间不合法")
    with connect() as db:
        if db.execute("SELECT 1 FROM scripts WHERE id=?", (script_id,)).fetchone() is None:
            raise HTTPException(404, "脚本不存在")
        cursor = db.execute("INSERT INTO tasks(name,script_id,schedule,timeout_seconds,network_enabled,created_at) VALUES (?,?,?,?,?,?)",
                            (name.strip(), script_id, schedule.strip(), timeout_seconds, int(network_enabled), now()))
        db.commit()
        return {"id": cursor.lastrowid}


@app.post("/api/tasks/{task_id}/run")
def run_task(task_id: int):
    with connect() as db:
        task = db.execute("SELECT tasks.*, scripts.version_path, scripts.entrypoint FROM tasks JOIN scripts ON scripts.id=tasks.script_id WHERE tasks.id=?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(404, "任务不存在")
        log_path = DATA_ROOT / "logs" / f"{uuid.uuid4().hex}.log"
        cursor = db.execute("INSERT INTO executions(task_id,status,started_at,log_path) VALUES (?,?,?,?)", (task_id, "RUNNING", now(), str(log_path.relative_to(DATA_ROOT))))
        db.commit()
        execution_id = cursor.lastrowid
    status, error, exit_code = "SUCCESS", None, 0
    try:
        exit_code = run_in_docker(stored_path(task["version_path"]), task["entrypoint"], task["timeout_seconds"], log_path, bool(task["network_enabled"]))
        status = "SUCCESS" if exit_code == 0 else "FAILED"
    except ExecutionError as exc:
        status, error, exit_code = "FAILED", str(exc), None
    with connect() as db:
        db.execute("UPDATE executions SET status=?,finished_at=?,exit_code=?,error=? WHERE id=?", (status, now(), exit_code, error, execution_id))
        db.commit()
    return {"id": execution_id, "status": status, "error": error}


@app.put("/api/tasks/{task_id}/enabled")
def set_task_enabled(task_id: int, enabled: bool = Form(...)):
    with connect() as db:
        cursor = db.execute("UPDATE tasks SET enabled=? WHERE id=?", (int(enabled), task_id))
        if cursor.rowcount == 0:
            raise HTTPException(404, "任务不存在")
        db.commit()
    scheduler.refresh()
    return {"id": task_id, "enabled": enabled}


@app.get("/api/executions")
def executions():
    with connect() as db:
        rows = db.execute("SELECT executions.*, tasks.name task_name FROM executions JOIN tasks ON tasks.id=executions.task_id ORDER BY executions.id DESC LIMIT 100").fetchall()
        return [dict(row) for row in rows]


@app.get("/api/executions/{execution_id}/log")
def execution_log(execution_id: int):
    """返回指定执行记录的日志内容，供执行记录页面查看。"""
    with connect() as db:
        execution = db.execute("SELECT id, log_path FROM executions WHERE id=?", (execution_id,)).fetchone()
    if execution is None:
        raise HTTPException(404, "执行记录不存在")
    try:
        log_path = stored_path(execution["log_path"])
        relative_path = log_path.resolve().relative_to((DATA_ROOT / "logs").resolve())
        content = read_log(DATA_ROOT / "logs", str(relative_path))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id": execution_id, "content": content}


if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


@app.get("/{path:path}")
def frontend(path: str):
    requested = FRONTEND / path
    if path and requested.exists() and requested.is_file():
        return FileResponse(requested)
    return FileResponse(FRONTEND / "index.html")
