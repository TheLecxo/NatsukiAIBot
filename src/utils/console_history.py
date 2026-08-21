import html
import json
import re
import sys
from datetime import datetime

from config import LOG_FILE
from config import DATA_DIR
from src.memory.long_memory import LongTermMemory

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None


_TELEGRAM_TAG_RE = re.compile(r"</?(?:tg-emoji|tg-spoiler|blockquote|b|i|u|s|code|pre|a)(?:\s[^>]*)?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_ARABIC_TEXT_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")


def clean_text(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = _TELEGRAM_TAG_RE.sub("", text)
    return _ANY_TAG_RE.sub("", text).strip()


def format_terminal_text(text):
    """Prepare Arabic-script text for left-to-right Windows terminals."""
    if not text or not _ARABIC_TEXT_RE.search(text) or not arabic_reshaper or not get_display:
        return text
    return get_display(arabic_reshaper.reshape(text))


def format_timestamp(value):
    if not value:
        return "Unknown time"
    try:
        return datetime.fromisoformat(str(value)).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    except (TypeError, ValueError, OSError):
        return str(value)


def combine_histories(*histories):
    """Keep stored messages and recover bot replies that exist only in the log."""
    history = []
    known = {(item.get("role"), item.get("timestamp"), item.get("text")) for item in history}
    for source in histories:
        for item in source or []:
            key = (item.get("role"), item.get("timestamp"), item.get("text"))
            if key not in known:
                history.append(item)
                known.add(key)
    return sorted(history, key=lambda item: str(item.get("timestamp") or ""))


def load_history_archive(user_id):
    archive_path = DATA_DIR / "chat_history_archive.jsonl"
    if not archive_path.exists():
        return []
    history = []
    try:
        lines = archive_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(entry.get("user_id")) == str(user_id):
            history.append(entry)
    return history


def load_history_from_log(user_id):
    if not LOG_FILE.exists():
        return []

    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    target_id = str(user_id)
    history = []
    for line in lines:
        if not line.strip():
            continue

        timestamp = line[:19] if len(line) >= 19 and line[4] == "-" and line[7] == "-" else "Unknown"
        user_match = re.search(
            rf"Message from\s*{re.escape(target_id)}\s*(?:\(@?[^\)]*\))?\s*:\s*(.*)$",
            line,
        )
        if user_match:
            text = user_match.group(1).strip()
            if text:
                history.append({"role": "user", "text": text, "timestamp": timestamp})
            continue

        bot_match = re.search(
            rf"Response sent to\s*{re.escape(target_id)}\s*(?:\(@?[^\)]*\))?\s*:\s*(.*)$",
            line,
        )
        if bot_match:
            text = bot_match.group(1).strip()
            if text:
                history.append({"role": "bot", "text": text, "timestamp": timestamp})

    return history


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.utils.console_history USER_ID")
        input("Press Enter to close...")
        return

    user_id = sys.argv[1]
    memory = LongTermMemory()
    user = memory.get_user(user_id)
    history = combine_histories(
        user.get("chat_history"),
        load_history_from_log(user_id),
        load_history_archive(user_id),
    )

    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", newline="\n")
    print("NATSUKI | CHAT HISTORY")
    print("=" * 100)
    print(f"Account name: {user.get('name') or 'Unknown'}")
    username = str(user.get("username") or "unknown")
    print(f"Username: {username if username.startswith('@') else '@' + username}")
    print(f"User ID: {user_id}")
    print("=" * 100)

    if not history:
        print("No chat history found for this user.")
    else:
        for entry in history:
            role = "User" if entry.get("role") == "user" else "@NatsukiAiBot"
            text = clean_text(entry.get("text"))
            if text:
                print(f"[{format_timestamp(entry.get('timestamp'))}] {role}: {format_terminal_text(text)}")
                print("-" * 100)

    input("Press Enter to close...")


if __name__ == "__main__":
    main()
