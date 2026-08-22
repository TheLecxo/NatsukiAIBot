import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

from config import OPENAI_API_KEY
from src.utils.runtime_monitor import read_runtime_files
from src.utils.terminal_launcher import open_history_terminal


def clear_screen():
    os.system("cls")


def fetch_health():
    result = {
        "internet": "Unavailable",
        "region": "Unavailable",
        "ip": "Unavailable",
        "credits": "Unavailable",
    }
    try:
        started = time.perf_counter()
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=5) as response:
            response.read(1)
        result["internet"] = f"{round((time.perf_counter() - started) * 1000)} ms"
    except (OSError, urllib.error.URLError):
        result["internet"] = "Offline"

    for endpoint in ("https://ipinfo.io/json", "https://ipapi.co/json/", "https://ipwho.is/"):
        try:
            with urllib.request.urlopen(endpoint, timeout=5) as response:
                location = json.load(response)
            if location.get("success") is False:
                continue
            result["ip"] = location.get("ip", "Unavailable")
            result["region"] = ", ".join(
                filter(
                    None,
                    [
                        location.get("city"),
                        location.get("region") or location.get("region_name"),
                        location.get("country_name") or location.get("country"),
                    ],
                )
            ) or "Unavailable"
            if result["ip"] != "Unavailable":
                break
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            continue

    api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
    if api_key.startswith("sk-or-"):
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.load(response).get("data", {})
            limit = data.get("limit")
            usage = data.get("usage", 0)
            if limit is not None:
                result["credits"] = f"${float(limit) - float(usage):.4f} remaining"
            else:
                result["credits"] = f"${float(usage):.4f} used"
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            pass
    return result


def render_users(status):
    print("NATSUKI | ACTIVE USERS")
    print(f"Session started: {status.get('started_at', 'Unknown')}")
    print("-" * 110)
    users = sorted(status.get("users", {}).values(), key=lambda item: item.get("number", 0))
    if not users:
        print("Waiting for Telegram users...")
        return
    for user in users:
        print(
            f"[{user.get('number')}] {user.get('name')} - @{user.get('username')} - "
            f"{user.get('user_id')} - {user.get('start_chat_time')} - "
            f"usage: {user.get('usage_count', 0)} - "
            f"[{user.get('current_mood', 'Unknown')}]"
        )
    #print("\nType: readmsg USER_ID or readmsg NUMBER to open the full Persian chat history.")


def read_user_command(command_queue):
    while True:
        try:
            command_queue.put(input().strip())
        except (EOFError, KeyboardInterrupt):
            return


def render_events(status, events):
    print("NATSUKI | BOT EVENTS")
    print(f"State: {status.get('bot_state', 'Unknown')} | Last update: {status.get('updated_at', 'Unknown')}")
    print("-" * 110)
    for event in events:
        print(f"[{event.get('time')}] {event.get('level')} | {event.get('action')} | {event.get('detail')}")
    if not events:
        print("No events recorded yet.")

def render_errors(status, events):
    print("NATSUKI | LIVE ERRORS")
    print(f"State: {status.get('bot_state', 'Unknown')} | Last update: {status.get('updated_at', 'Unknown')}")
    print("-" * 110)
    errors = [event for event in events if str(event.get("level", "")).upper() == "ERROR"]
    for event in errors:
        print(f"[{event.get('time')}] {event.get('action')} | {event.get('detail')}")
    if not errors:
        print("No errors recorded yet.")


def render_health(status):
    health = fetch_health()
    print("NATSUKI | SERVICE HEALTH")
    print(f"Checked: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print("-" * 110)
    print(f"Bot state       : {status.get('bot_state', 'Unknown')}")
    print(f"Internet/API RTT: {health['internet']}")
    print(f"API traffic     : {status.get('api_traffic', 0)} requests")
    print(f"OpenRouter credit: {health['credits']}")
    print(f"Active IP       : {health['ip']}")
    print(f"Region          : {health['region']}")


def main():
    view = sys.argv[1] if len(sys.argv) > 1 else "events"
    title = os.getenv("NATSUKI_CONSOLE_TITLE", "Natsuki Dashboard")
    os.system(f"title {title}")
    command_queue = queue.Queue()
    if view == "users":
        threading.Thread(target=read_user_command, args=(command_queue,), daemon=True).start()
    while True:
        clear_screen()
        status, events = read_runtime_files()
        if view == "users":
            render_users(status)
            try:
                command = command_queue.get_nowait()
            except queue.Empty:
                command = ""
            if command:
                parts = command.split()
                if len(parts) == 2 and parts[0].lower() == "readmsg":
                    target = parts[1]
                    if target.isdigit():
                        if not any(str(user.get("user_id")) == target for user in status.get("users", {}).values()):
                            try:
                                target = next(
                                    str(user.get("user_id"))
                                    for user in status.get("users", {}).values()
                                    if str(user.get("number")) == target
                                )
                            except StopIteration:
                                target = ""
                        if target:
                            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                            _, result = open_history_terminal(
                                target,
                                target,
                                base_dir,
                                sys.executable,
                            )
                            print(result)
                        else:
                            print("User not found.")
                    else:
                        print("Usage: readmsg USER_ID or readmsg NUMBER")
                else:
                    print("Usage: readmsg USER_ID or readmsg NUMBER")
        elif view == "health":
            render_health(status)
        elif view == "errors":
            render_errors(status, events)
        else:
            render_events(status, events)
        print("\nRefreshing every 2 seconds. Close this window to stop this dashboard.")
        if status.get("bot_state") in {"stopped", "error"}:
            print("Runtime finished. This dashboard will close.")
            break
        time.sleep(2)


if __name__ == "__main__":
    main()