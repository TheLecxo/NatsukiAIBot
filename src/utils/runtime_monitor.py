import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
STATUS_PATH = BASE_DIR / "data" / "runtime_status.json"
EVENTS_PATH = BASE_DIR / "data" / "runtime_events.jsonl"

_lock = threading.RLock()
_dashboard_processes = []


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_status():
    return {
        "started_at": _now(),
        "bot_state": "starting",
        "api_traffic": 0,
        "users": {},
        "last_event": None,
    }


def _read_status():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_status()


def _write_status(status):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = STATUS_PATH.with_name(
        f"{STATUS_PATH.stem}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    temporary_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        for attempt in range(5):
            try:
                os.replace(temporary_path, STATUS_PATH)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary_path.unlink(missing_ok=True)


def initialize_runtime():
    with _lock:
        _write_status(_default_status())
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVENTS_PATH.write_text("", encoding="utf-8")


def request_shutdown():
    """Mark a clean shutdown request for the dashboards and logs."""
    set_bot_state("stopping", "Shutdown requested from the main console")
    record_event("shutdown_requested", "The operator requested a complete shutdown")


def set_bot_state(state, detail=None):
    with _lock:
        status = _read_status()
        status["bot_state"] = state
        if detail:
            status["state_detail"] = str(detail)
        status["updated_at"] = _now()
        _write_status(status)


def record_user(user_id, name, username, event_type="message"):
    with _lock:
        status = _read_status()
        key = str(user_id)
        user = status.setdefault("users", {}).setdefault(
            key,
            {
                "number": len(status["users"]) + 1,
                "name": name or "Unknown",
                "username": username or "unknown",
                "user_id": key,
                "start_chat_time": _now(),
                "usage_count": 0,
            },
        )
        user["name"] = name or user.get("name") or "Unknown"
        user["username"] = username or user.get("username") or "unknown"
        user["usage_count"] = int(user.get("usage_count", 0)) + 1
        user["last_activity"] = _now()
        user["last_activity_type"] = event_type
        status["updated_at"] = _now()
        _write_status(status)

def update_user_mood(user_id, mood):
    with _lock:
        status = _read_status()
        user = status.setdefault("users", {}).get(str(user_id))
        if user is None:
            return
        user["current_mood"] = str(mood)
        user["mood_updated_at"] = _now()
        status["updated_at"] = _now()
        _write_status(status)


def record_api_call():
    with _lock:
        status = _read_status()
        status["api_traffic"] = int(status.get("api_traffic", 0)) + 1
        status["updated_at"] = _now()
        _write_status(status)


def record_event(action, detail="", level="INFO"):
    event = {
        "time": _now(),
        "level": level,
        "action": str(action),
        "detail": str(detail),
    }
    with _lock:
        status = _read_status()
        status["last_event"] = event
        status["updated_at"] = _now()
        _write_status(status)
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_runtime_files():
    with _lock:
        status = _read_status()
        try:
            events = [
                json.loads(line)
                for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ][-200:]
        except (OSError, json.JSONDecodeError):
            events = []
        return status, events


def start_dashboards():
    if sys.platform != "win32":
        return []

    for view, title in (
        ("users", "Natsuki - Active Users"),
        ("events", "Natsuki - Bot Events"),
        ("errors", "Natsuki - Errors"),
        ("health", "Natsuki - Service Health"),
    ):
        process = subprocess.Popen(
            [sys.executable, "-m", "src.utils.console_dashboard", view],
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env={**os.environ, "NATSUKI_CONSOLE_TITLE": title},
        )
        _dashboard_processes.append(process)
    return list(_dashboard_processes)


def stop_dashboards():
    for process in _dashboard_processes:
        if process.poll() is None:
            process.terminate()
    _dashboard_processes.clear()
