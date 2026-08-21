import json
import re
import sqlite3
from json import dumps
from datetime import datetime
from pathlib import Path

import config


DEFAULT_PREMIUM_EMOJIS = (
    ("EXITED", "5237764698245450016", "هیجان زده"),
    ("CONFIRM", "5238224229681350693", "مشتاق و حالت تایید"),
    ("EMBARRASSED", "5240300936563278060", "خجالت زده و ناراحت از کار فرد"),
    ("ANGERY", "5240021540350740642", "عصبانیت با خجالت"),
    ("REJECT", "5238041302729247271", "رد نکردن یا قبول نکردن"),
    ("LAUGHING", "5239948852324221211", "از ته دل خندیدن"),
)


class LongTermMemory:
    def __init__(self):
        self.db_path = Path(config.DATABASE_PATH)
        self.memory_file = Path(config.MEMORY_FILE)
        self.history_archive = self.db_path.parent / "chat_history_archive.jsonl"
        self.memory = {}

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._migrate_legacy_json_if_needed()
        self._load_memory()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self):
        """بستن اتصال دیتابیس"""
        try:
            if hasattr(self, "_conn") and self._conn is not None:
                self._conn.close()
                self._conn = None
        except Exception:
            pass

    def _init_db(self):
        """ایجاد جدول داده‌های کاربران"""
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    xp INTEGER NOT NULL DEFAULT 0,
                    friendship_level TEXT NOT NULL DEFAULT 'Novice',
                    created_at TEXT NOT NULL,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    banned INTEGER NOT NULL DEFAULT 0,
                    ban_date TEXT,
                    ban_duration TEXT,
                    ban_until TEXT,
                    name TEXT NOT NULL DEFAULT 'Unknown',
                    username TEXT NOT NULL DEFAULT 'unknown',
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    admin_since TEXT,
                    chat_history TEXT NOT NULL DEFAULT '[]',
                    mood_history TEXT NOT NULL DEFAULT '[]',
                    current_mood TEXT,
                    last_mood_update TEXT,
                    last_interaction TEXT,
                    age INTEGER,
                    extra_data TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS premium_emojis (
                    tag TEXT PRIMARY KEY,
                    emoji_id TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO premium_emojis (tag, emoji_id, description)
                VALUES (?, ?, ?)
                """,
                DEFAULT_PREMIUM_EMOJIS,
            )
            conn.commit()
        finally:
            conn.close()

    def _default_user_data(self, user_id):
        return {
            "user_id": str(user_id),
            "xp": 0,
            "friendship_level": "Novice",
            "created_at": datetime.now().isoformat(),
            "interaction_count": 0,
            "banned": False,
            "ban_date": None,
            "ban_duration": None,
            "ban_until": None,
            "name": "Unknown",
            "username": "unknown",
            "is_admin": False,
            "admin_since": None,
            "chat_history": [],
            "mood_history": [],
            "current_mood": None,
            "last_mood_update": None,
            "last_interaction": None,
            "age": None,
            "extra_data": {},
        }

    def _normalize_user_data(self, user_data):
        user = dict(user_data)
        user.setdefault("user_id", str(user.get("user_id") or user.get("uid") or "unknown"))
        user.setdefault("xp", 0)
        user.setdefault("friendship_level", "Novice")
        user.setdefault("created_at", datetime.now().isoformat())
        user.setdefault("interaction_count", 0)
        user.setdefault("banned", False)
        user.setdefault("ban_date", None)
        user.setdefault("ban_duration", None)
        user.setdefault("ban_until", None)
        user.setdefault("name", "Unknown")
        user.setdefault("username", "unknown")
        user.setdefault("is_admin", False)
        user.setdefault("admin_since", None)
        user.setdefault("chat_history", [])
        user.setdefault("mood_history", [])
        user.setdefault("current_mood", None)
        user.setdefault("last_mood_update", None)
        user.setdefault("last_interaction", None)
        user.setdefault("age", None)
        user.setdefault("extra_data", {})
        return user

    def _serialize_user(self, user_data):
        user = self._normalize_user_data(user_data)
        return {
            "user_id": str(user["user_id"]),
            "xp": int(user.get("xp", 0) or 0),
            "friendship_level": str(user.get("friendship_level", "Novice")),
            "created_at": str(user.get("created_at") or datetime.now().isoformat()),
            "interaction_count": int(user.get("interaction_count", 0) or 0),
            "banned": 1 if bool(user.get("banned", False)) else 0,
            "ban_date": user.get("ban_date"),
            "ban_duration": user.get("ban_duration"),
            "ban_until": user.get("ban_until"),
            "name": str(user.get("name", "Unknown")),
            "username": str(user.get("username", "unknown")),
            "is_admin": 1 if bool(user.get("is_admin", False)) else 0,
            "admin_since": user.get("admin_since"),
            "chat_history": json.dumps(user.get("chat_history", []), ensure_ascii=False),
            "mood_history": json.dumps(user.get("mood_history", []), ensure_ascii=False),
            "current_mood": user.get("current_mood"),
            "last_mood_update": user.get("last_mood_update"),
            "last_interaction": user.get("last_interaction"),
            "age": user.get("age"),
            "extra_data": json.dumps(user.get("extra_data", {}), ensure_ascii=False),
        }

    def _deserialize_user(self, row):
        user = dict(row)
        user["user_id"] = str(user.get("user_id"))
        user["banned"] = bool(user.get("banned", 0))
        user["is_admin"] = bool(user.get("is_admin", 0))
        user["xp"] = int(user.get("xp", 0) or 0)
        user["interaction_count"] = int(user.get("interaction_count", 0) or 0)
        user["chat_history"] = json.loads(user.get("chat_history") or "[]")
        user["mood_history"] = json.loads(user.get("mood_history") or "[]")
        user["extra_data"] = json.loads(user.get("extra_data") or "{}")
        return user

    def _load_memory(self):
        """بارگذاری حافظه از دیتابیس"""
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM users").fetchall()
        finally:
            conn.close()

        self.memory = {}
        for row in rows:
            user = self._deserialize_user(dict(row))
            self.memory[str(user["user_id"])] = user

    def _migrate_legacy_json_if_needed(self):
        """انتقال داده‌های قدیمی JSON به دیتابیس و حذف فایل قدیمی"""
        if not self.memory_file.exists() or self.memory_file.stat().st_size == 0:
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.memory_file.unlink(missing_ok=True)
            return

        if isinstance(legacy_data, dict):
            self.memory = {
                str(uid): self._normalize_user_data(user_data)
                for uid, user_data in legacy_data.items()
            }
            self.save()

        try:
            self.memory_file.unlink()
        except OSError:
            pass

    def save(self):
        """ذخیره حافظه در دیتابیس"""
        conn = self._connect()
        try:
            for uid, user_data in self.memory.items():
                user = self._normalize_user_data(user_data)
                user["user_id"] = str(uid)
                row = self._serialize_user(user)
                conn.execute(
                    """
                    INSERT INTO users (
                        user_id, xp, friendship_level, created_at, interaction_count,
                        banned, ban_date, ban_duration, ban_until, name, username,
                        is_admin, admin_since, chat_history, mood_history,
                        current_mood, last_mood_update, last_interaction, age, extra_data
                    ) VALUES (
                        :user_id, :xp, :friendship_level, :created_at, :interaction_count,
                        :banned, :ban_date, :ban_duration, :ban_until, :name, :username,
                        :is_admin, :admin_since, :chat_history, :mood_history,
                        :current_mood, :last_mood_update, :last_interaction, :age, :extra_data
                    )
                    ON CONFLICT(user_id) DO UPDATE SET
                        xp = excluded.xp,
                        friendship_level = excluded.friendship_level,
                        created_at = excluded.created_at,
                        interaction_count = excluded.interaction_count,
                        banned = excluded.banned,
                        ban_date = excluded.ban_date,
                        ban_duration = excluded.ban_duration,
                        ban_until = excluded.ban_until,
                        name = excluded.name,
                        username = excluded.username,
                        is_admin = excluded.is_admin,
                        admin_since = excluded.admin_since,
                        chat_history = excluded.chat_history,
                        mood_history = excluded.mood_history,
                        current_mood = excluded.current_mood,
                        last_mood_update = excluded.last_mood_update,
                        last_interaction = excluded.last_interaction,
                        age = excluded.age,
                        extra_data = excluded.extra_data
                    """,
                    row,
                )
            conn.commit()
        finally:
            conn.close()

    def sync_user_profile(self, user_id, first_name=None, username=None):
        """به‌روزرسانی نام و یوزرنیم کاربر"""
        user_data = self.get_user(user_id)
        if first_name and str(first_name).strip() and user_data.get("name") in {None, "", "Unknown"}:
            user_data["name"] = first_name
        if username and str(username).strip() and user_data.get("username") in {None, "", "unknown"}:
            user_data["username"] = username
        self.save()
        return user_data

    def get_user(self, user_id):
        """دریافت اطلاعات کاربر"""
        uid = str(user_id)
        if uid not in self.memory:
            self.memory[uid] = self._default_user_data(user_id)
            self.save()
        return self.memory[uid]

    def is_admin(self, user_id):
        """بررسی مدیر بودن کاربر"""
        return bool(self.get_user(user_id).get("is_admin", False))

    def get_admin_users(self):
        """دریافت لیست مدیرها"""
        return [user for user in self.get_all_users_sorted() if user.get("is_admin")]

    def set_admin(self, user_id, is_admin=True):
        """تنظیم وضعیت مدیر"""
        user_data = self.get_user(user_id)
        user_data["is_admin"] = bool(is_admin)
        if is_admin:
            user_data["admin_since"] = user_data.get("admin_since") or datetime.now().isoformat()
        else:
            user_data["admin_since"] = None
        self.save()
        return user_data

    def get_premium_emojis(self):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tag, emoji_id, description FROM premium_emojis ORDER BY tag"
            ).fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def get_premium_emoji(self, tag):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT tag, emoji_id, description FROM premium_emojis WHERE tag = ?",
                (str(tag).upper(),),
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def save_premium_emoji(self, tag, emoji_id, description):
        tag = str(tag).strip().upper()
        emoji_id = str(emoji_id).strip()
        description = str(description).strip()
        if not tag or not tag.replace("_", "").isalnum():
            raise ValueError("Tag must contain only letters, numbers, and underscores")
        if not emoji_id.isdigit():
            raise ValueError("Emoji ID must contain only numbers")
        if not description:
            raise ValueError("Description is required")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO premium_emojis (tag, emoji_id, description)
                VALUES (?, ?, ?)
                ON CONFLICT(tag) DO UPDATE SET
                    emoji_id = excluded.emoji_id,
                    description = excluded.description
                """,
                (tag, emoji_id, description),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_premium_emoji(tag)

    def delete_premium_emoji(self, tag):
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM premium_emojis WHERE tag = ?",
                (str(tag).strip().upper(),),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_all_users_sorted(self):
        """دریافت لیست کاربران به ترتیب زمانی اولین استفاده"""
        users = []
        for uid, user_data in self.memory.items():
            user_copy = dict(user_data)
            user_copy["user_id"] = int(uid) if uid.isdigit() else uid
            users.append(user_copy)

        return sorted(
            users,
            key=lambda item: item.get("created_at") or "1970-01-01T00:00:00"
        )

    def get_banned_users(self):
        """دریافت کاربران بن‌شده"""
        return [user for user in self.get_all_users_sorted() if user.get("banned")]

    def is_user_banned(self, user_id):
        """بررسی بن بودن کاربر"""
        user_data = self.get_user(user_id)
        if not user_data.get("banned"):
            return False

        ban_until = user_data.get("ban_until")
        if ban_until is None:
            return True

        try:
            return datetime.now() < datetime.fromisoformat(ban_until)
        except Exception:
            return True

    def set_user_ban(self, user_id, is_banned, duration_key=None):
        """تنظیم وضعیت بن کاربر"""
        user_data = self.get_user(user_id)
        user_data["banned"] = bool(is_banned)
        now = datetime.now()

        if is_banned:
            user_data["ban_date"] = now.isoformat()
            user_data["ban_duration"] = duration_key or "ForEver"

            if duration_key == "1h":
                user_data["ban_until"] = (now.__add__(__import__('datetime').timedelta(hours=1))).isoformat()
            elif duration_key == "1d":
                user_data["ban_until"] = (now.__add__(__import__('datetime').timedelta(days=1))).isoformat()
            elif duration_key == "1m":
                user_data["ban_until"] = (now.__add__(__import__('datetime').timedelta(days=30))).isoformat()
            else:
                user_data["ban_until"] = None
        else:
            user_data["ban_date"] = None
            user_data["ban_duration"] = None
            user_data["ban_until"] = None

        self.save()
        return user_data

    def add_chat_message(self, user_id, role, text):
        """افزودن پیام به تاریخچه‌ی چت کاربر"""
        user_data = self.get_user(user_id)
        history = user_data.setdefault("chat_history", [])
        entry = {
            "role": role,
            "text": str(text or "").strip(),
            "timestamp": datetime.now().isoformat()
        }
        history.append(entry)
        self.save()
        self.history_archive.parent.mkdir(parents=True, exist_ok=True)
        with self.history_archive.open("a", encoding="utf-8") as archive:
            archive.write(dumps({"user_id": str(user_id), **entry}, ensure_ascii=False) + "\n")
        return history

    def update_from_message(self, user_id, text, username=None, first_name=None):
        """به‌روزرسانی حافظه بر اساس پیام"""
        user_data = self.get_user(user_id)

        if username:
            user_data["username"] = username
        if first_name:
            user_data["name"] = first_name

        if text and str(text).strip():
            self.add_chat_message(user_id, "user", text)

        self._extract_personal_info(user_id, text)

        user_data["interaction_count"] = user_data.get("interaction_count", 0) + 1
        user_data["last_interaction"] = datetime.now().isoformat()

        self.save()
        return user_data

    def _extract_personal_info(self, user_id, text):
        """استخراج اطلاعات شخصی از متن"""
        uid = str(user_id)

        if "اسمم" in text or "اسم من" in text:
            parts = text.split("اسم")
            if len(parts) > 1:
                self.memory[uid]["name"] = parts[1].replace("م", "").replace("من", "").strip()

        match = re.search(r"my name is ([a-zA-Z]+)", text.lower())
        if match:
            self.memory[uid]["name"] = match.group(1)

        age_match = re.search(r"\d+", text)
        if "سن" in text and age_match:
            self.memory[uid]["age"] = int(age_match.group(0))