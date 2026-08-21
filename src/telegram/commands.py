import re
import asyncio
import sys
import time
from html import escape
from io import BytesIO
from pathlib import Path

from config import LOG_FILE
from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.utils.console_history import clean_text, combine_histories, load_history_archive
from src.utils.terminal_launcher import open_history_terminal
from src.utils.runtime_monitor import update_user_mood

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_PERSIAN_TEXT = True
except Exception:
    HAS_PERSIAN_TEXT = False

OWNER_ID = 7915402928
ADMIN_PROMPT_CHATS = {}

_BUTTON_STYLE = {
    "back": "primary",
    "previous": "primary",
    "next": "primary",
    "yes": "success",
    "no": "danger",
    "ban": "danger",
    "users": "primary",
    "admin": "primary",
    "add": "success",
    "on": "success",
    "off": "danger",
    "duration": "primary",
}


def _html_text(text):
    """Keep supported Telegram tags and escape stray angle brackets in text."""
    text = str(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    allowed_tag = r"(?:b|i|u|s|code|pre|a|tg-emoji|tg-spoiler|blockquote)"
    return re.sub(
        rf"<(?!/?{allowed_tag}(?:\s|>|/))",
        "&lt;",
        text,
        flags=re.IGNORECASE,
    )


def _button_style(text):
    label = str(text)
    lower_label = label.lower()
    if "previous" in lower_label:
        return _BUTTON_STYLE["previous"]
    elif "next" in lower_label:
        return _BUTTON_STYLE["next"]
    elif "back" in lower_label:
        return _BUTTON_STYLE["back"]
    elif lower_label in {"yes", "no"}:
        return _BUTTON_STYLE[lower_label]
    elif "ban list" in lower_label or "ban" in lower_label:
        return _BUTTON_STYLE["ban"]
    elif "user" in lower_label:
        return _BUTTON_STYLE["users"]
    elif "admin" in lower_label:
        return _BUTTON_STYLE["admin"]
    elif "add" in lower_label:
        return _BUTTON_STYLE["add"]
    elif "turn on" in lower_label:
        return _BUTTON_STYLE["on"]
    elif "turn off" in lower_label:
        return _BUTTON_STYLE["off"]
    elif lower_label in {"1h", "1d", "1m", "forever"}:
        return _BUTTON_STYLE["duration"]
    return "primary"


def _prepare_markup(markup):
    if isinstance(markup, InlineKeyboardBuilder):
        for row in markup._markup:
            for button in row:
                button.icon_custom_emoji_id = "5206357006864113601"
                button.style = _button_style(button.text)
        return markup.as_markup()
    return markup


def _format_dashboard_metric(value):
    if value is None:
        return "N/A"
    return str(value)


async def _measure_bot_ping(bot):
    try:
        start = time.perf_counter()
        await bot.get_me()
        return f"{round((time.perf_counter() - start) * 1000)}ms"
    except Exception:
        return "N/A"


async def _get_dashboard_stats(bot):
    api_traffic = getattr(bot, "api_traffic", 0)
    ping = getattr(bot, "bot_ping_ms", None)
    if ping in (None, "N/A"):
        ping = await _measure_bot_ping(bot)
        setattr(bot, "bot_ping_ms", ping)
    return api_traffic, ping


def _is_core_active():
    return (Path("core") / "natsuki.chr").exists()


def _set_core_active(active):
    core_path = Path("core") / "natsuki.chr"
    core_path.parent.mkdir(parents=True, exist_ok=True)
    if active:
        core_path.touch(exist_ok=True)
    elif core_path.exists():
        core_path.unlink()


async def _reply_html(bot, message: types.Message, text, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    text = _html_text(text)
    if "reply_markup" in kwargs:
        kwargs["reply_markup"] = _prepare_markup(kwargs["reply_markup"])
    try:
        return await message.reply(text, **kwargs)
    except TelegramForbiddenError:
        return None
    except TelegramBadRequest as error:
        if "message to be replied not found" not in str(error).lower():
            raise
        try:
            return await bot.send_message(message.chat.id, text, **kwargs)
        except TelegramForbiddenError:
            return None


async def _send_html(bot, chat_id, text, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    text = _html_text(text)
    if "reply_markup" in kwargs:
        kwargs["reply_markup"] = _prepare_markup(kwargs["reply_markup"])
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramForbiddenError:
        return None


async def _edit_html(bot, chat_id, message_id, text, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    text = _html_text(text)
    if "reply_markup" in kwargs:
        kwargs["reply_markup"] = _prepare_markup(kwargs["reply_markup"])
    try:
        return await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            **kwargs,
        )
    except TelegramForbiddenError:
        return None


def _is_owner_or_admin(user_id, long_memory):
    user_id = int(user_id)
    return user_id == OWNER_ID or bool(long_memory.is_admin(user_id))


def _safe_username(user):
    username = user.get("username") or user.get("name") or "unknown"
    username = str(username)
    return escape(username if username.startswith("@") else f"@{username}")


def _format_user_row(user, index, mode="user"):
    user_id = escape(str(user.get("user_id", "Unknown")))
    username = _safe_username(user)
    account_name = escape(str(user.get("name") or "Unknown"))
    interaction_count = escape(str(user.get("interaction_count", 0)))
    first_use = escape(str(user.get("created_at") or "Unknown"))
    last_use = escape(str(user.get("last_interaction") or first_use))

    text = (
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Number {index}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Account name: {account_name}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Username: {username}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> UserId: {user_id}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Interaction count: {interaction_count}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> first use date: {first_use}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> last use date: {last_use}\n"
    )

    if mode == "admin":
        text += f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Set admin date: {escape(str(user.get('admin_since') or 'Unknown'))}\n"
    elif mode == "banlist":
        text += f"Ban date: {escape(str(user.get('ban_date') or 'Unknown'))}\n"
        text += f"How long: {escape(str(user.get('ban_duration') or 'Unknown'))}\n"

    return text


def _build_users_page_text(users, page_number=1, page_size=5, viewer_id=None):
    """ساخت متن صفحه‌ی کاربران با فرمت موردنظر"""
    start = (page_number - 1) * page_size
    end = start + page_size
    page_users = users[start:end]

    text = "User list:\n"
    if not page_users:
        return text + "No users found."

    for index, user in enumerate(page_users, start + 1):
        user_id = user.get("user_id", "Unknown")
        text += "\n" + _format_user_row(user, index, mode="user")
        text += f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Ban user: <code>/banuser {user_id}</code>\n"
        if viewer_id == OWNER_ID:
            text += f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Read message: <code>/readmsg {user_id}</code>\n"
        text += "-------------------------\n"

    return text


def _build_users_pagination_markup(page_number, total_pages, users=None, viewer_id=None):
    """ساخت دکمه‌های صفحه‌بندی"""
    markup = InlineKeyboardBuilder()
    buttons = []

    if page_number > 1:
        buttons.append(types.InlineKeyboardButton(text="Previous page", callback_data=f"users_page:{page_number - 1}"))
    if page_number < total_pages:
        buttons.append(types.InlineKeyboardButton(text="Next page", callback_data=f"users_page:{page_number + 1}"))

    if buttons:
        markup.row(*buttons)
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
    return markup


def _build_main_control_markup(user_id=None):
    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="Ban list", callback_data="open_banlist"),
        types.InlineKeyboardButton(text="users", callback_data="open_users")
    )
    toggle_label = "Turn off bot" if _is_core_active() else "Turn on bot"
    toggle_callback = "turn_off_bot" if _is_core_active() else "turn_on_bot"
    markup.row(types.InlineKeyboardButton(text=toggle_label, callback_data=toggle_callback))
    if user_id == OWNER_ID:
        markup.row(
            types.InlineKeyboardButton(text="Admin control", callback_data="open_admin_control"),
            types.InlineKeyboardButton(text="Premium emojis", callback_data="open_premium_emojis"),
        )
    return markup


def _build_admin_list_text(admins):
    text = "Admin control:\n"
    if not admins:
        return text + "No admins found."

    for index, user in enumerate(admins, 1):
        user_id = user.get("user_id", "Unknown")
        text += "\n" + _format_user_row(user, index, mode="admin")
        text += f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Delete admin: <code>/dltadmin {user_id}</code>\n"
        text += "-------------------------\n"
    return text


def _build_admin_list_markup(owner_only=False):
    markup = InlineKeyboardBuilder()
    buttons = [types.InlineKeyboardButton(text="Back", callback_data="back_to_main")]
    if owner_only:
        buttons.append(types.InlineKeyboardButton(text="Add admin", callback_data="open_admin_add"))
    markup.row(*buttons)
    return markup


def _build_premium_emoji_text(long_memory):
    emojis = long_memory.get_premium_emojis()
    text = "Premium emoji control:\n"
    if not emojis:
        return text + "No premium emojis found."
    for item in emojis:
        text += (
            f"\n<b>{escape(item['tag'])}</b> | "
            f"<code>{escape(item['emoji_id'])}</code> | "
            f"{escape(item['description'])}\n"
        )
    text += "\nAdd: <code>/addemoji TAG EMOJI_ID DESCRIPTION</code>\n"
    text += "Edit: <code>/editemoji TAG EMOJI_ID DESCRIPTION</code>"
    return text


def _build_premium_emoji_markup(long_memory):
    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="Add emoji", callback_data="add_emoji_prompt"),
        types.InlineKeyboardButton(text="Edit emoji", callback_data="edit_emoji_prompt"),
    )
    for item in long_memory.get_premium_emojis():
        markup.row(
            types.InlineKeyboardButton(
                text=f"Delete {item['tag']}",
                callback_data=f"delete_emoji:{item['tag']}",
            )
        )
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
    return markup


async def _show_premium_emoji_panel(bot, chat_id, long_memory, message_id=None):
    text = _build_premium_emoji_text(long_memory)
    markup = _build_premium_emoji_markup(long_memory)
    if message_id is None:
        await _send_html(bot, chat_id, text, reply_markup=markup)
    else:
        await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)


async def _show_premium_emoji_prompt(bot, chat_id, message_id, action):
    ADMIN_PROMPT_CHATS[chat_id] = {"message_id": message_id, "kind": action}
    text = (
        "Enter: <code>TAG EMOJI_ID DESCRIPTION</code>\n"
        "Example: <code>CONFIRM 5238224229681350693 excited confirmation</code>"
    )
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="open_premium_emojis"))
    await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)


async def handle_premium_emoji_command(bot, message: types.Message, long_memory):
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    await _show_premium_emoji_panel(bot, message.chat.id, long_memory)


async def handle_premium_emoji_write_command(bot, message: types.Message, long_memory, action):
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await _reply_html(bot, message, f"Usage: /{action} TAG EMOJI_ID DESCRIPTION")
        return
    try:
        item = long_memory.save_premium_emoji(parts[1], parts[2], parts[3])
    except ValueError as error:
        await _reply_html(bot, message, str(error))
        return
    await _reply_html(bot, message, f"Saved premium emoji <b>{escape(item['tag'])}</b>.")


async def _show_admin_list(bot, chat_id, message_id, long_memory, user_id=None):
    admins = long_memory.get_admin_users()
    text = _build_admin_list_text(admins)
    owner_only = bool(user_id == OWNER_ID)
    markup = _build_admin_list_markup(owner_only=owner_only)
    await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)


async def _show_admin_add_prompt(bot, chat_id, message_id=None):
    text = "New admin program:\nEnter the Admin Userid:"
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="open_admin_control"))
    ADMIN_PROMPT_CHATS[chat_id] = {"message_id": message_id or 0}
    if message_id is not None:
        await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)
    else:
        await _send_html(bot, chat_id, text, reply_markup=markup)


async def _handle_admin_prompt_input(bot, message: types.Message, long_memory):
    chat_data = ADMIN_PROMPT_CHATS.get(message.chat.id)
    if not chat_data:
        return False

    ADMIN_PROMPT_CHATS.pop(message.chat.id, None)
    raw = (message.text or "").strip()

    if chat_data.get("kind") in {"emoji_add", "emoji_edit"}:
        parts = raw.split(maxsplit=2)
        target_message_id = chat_data.get("message_id") or message.message_id
        if len(parts) < 3:
            await _edit_html(bot, message.chat.id, target_message_id, "Use: TAG EMOJI_ID DESCRIPTION")
            return True
        try:
            item = long_memory.save_premium_emoji(parts[0], parts[1], parts[2])
            await _edit_html(
                bot,
                message.chat.id,
                target_message_id,
                f"Saved premium emoji <b>{escape(item['tag'])}</b>.",
            )
            await asyncio.sleep(1)
            await _show_premium_emoji_panel(bot, message.chat.id, long_memory, target_message_id)
        except ValueError as error:
            await _edit_html(bot, message.chat.id, target_message_id, str(error))
        return True

    if not raw or not raw.lstrip("-").isdigit():
        target_message_id = chat_data.get("message_id") or message.message_id
        await _edit_html(bot, message.chat.id, target_message_id, "UserId must be a number.")
        await asyncio.sleep(2)
        await _show_admin_list(bot, message.chat.id, target_message_id, long_memory)
        return True

    target_user_id = int(raw)
    if target_user_id == OWNER_ID:
        target_message_id = chat_data.get("message_id") or message.message_id
        await _edit_html(bot, message.chat.id, target_message_id, "The owner is already an admin.")
        await asyncio.sleep(2)
        await _show_admin_list(bot, message.chat.id, target_message_id, long_memory)
        return True

    user = long_memory.get_user(target_user_id)
    if user.get("interaction_count", 0) <= 0:
        target_message_id = chat_data.get("message_id") or message.message_id
        await _edit_html(bot, message.chat.id, target_message_id, "This user has not started the bot yet.")
        await asyncio.sleep(2)
        await _show_admin_list(bot, message.chat.id, target_message_id, long_memory)
        return True

    if long_memory.is_admin(target_user_id):
        target_message_id = chat_data.get("message_id") or message.message_id
        await _edit_html(bot, message.chat.id, target_message_id, "This user is already an admin.")
        await asyncio.sleep(2)
        await _show_admin_list(bot, message.chat.id, target_message_id, long_memory)
        return True

    text = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to want add this user to admin?\n\n" + _format_user_row(user, 1, mode="user")
    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_admin_add:{target_user_id}"),
        types.InlineKeyboardButton(text="No", callback_data="open_admin_control")
    )
    await _edit_html(bot, message.chat.id, chat_data.get("message_id") or message.message_id, text, reply_markup=markup)
    return True


async def show_admin_add_confirmation(bot, chat_id, target_user_id, long_memory):
    user = long_memory.get_user(target_user_id)
    if not user:
        await _send_html(bot, chat_id, "User not found.")
        return

    if user.get("interaction_count", 0) <= 0:
        await _send_html(bot, chat_id, "This user has not started the bot yet.")
        return

    text = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to want add this user to admin?\n\n" + _format_user_row(user, 1, mode="user")
    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_admin_add:{target_user_id}"),
        types.InlineKeyboardButton(text="No", callback_data="open_admin_control")
    )
    await _send_html(bot, chat_id, text, reply_markup=markup)


async def _show_main_control_panel(bot, chat_id, message_id=None, user=None):
    api_traffic, bot_ping = await _get_dashboard_stats(bot)
    is_on = _is_core_active()
    status = "on" if is_on else "off"
    display_name = escape(f"@{user.username}" if user.username else user.first_name)
    text = (
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Hello {display_name}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">📡</tg-emoji> Bot is <b>{status}</b>!\n"
        "<tg-emoji emoji-id=\"5206357006864113601\">🎛️</tg-emoji> Control panel is on!\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> api Trafic: {api_traffic}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Bot Ping: {bot_ping}\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Bot statue: <b>{status}</b>\n"
        "<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Chose your options to use:\n"
    )
    markup = _build_main_control_markup(user_id=user.id)
    if message_id is not None:
        await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)
    else:
        await _send_html(bot, chat_id, text, reply_markup=markup)


async def _ensure_owner_admin(bot, message: types.Message, long_memory):
    user_id = message.from_user.id
    if not _is_owner_or_admin(user_id, long_memory):
        await _reply_html(bot, message, "<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> Access denied.")
        return False
    return True


async def _show_user_confirmation(bot, chat_id, target_user_id, long_memory, action="ban"):
    user = long_memory.get_user(target_user_id)
    if not user:
        await _send_html(bot, chat_id, "User not found.")
        return

    users = long_memory.get_all_users_sorted()
    target_index = next((i + 1 for i, item in enumerate(users) if str(item.get("user_id")) == str(target_user_id)), 1)
    text = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure you want to ban this user?\n" if action == "ban" else "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure you want delete this admin?\n"
    text += "\n" + _format_user_row(user, target_index, mode="user")

    markup = InlineKeyboardBuilder()
    yes_action = f"confirm_ban:{target_user_id}" if action == "ban" else f"confirm_dltadmin:{target_user_id}"
    no_action = f"cancel_ban:{target_user_id}" if action == "ban" else f"cancel_dltadmin:{target_user_id}"
    markup.row(types.InlineKeyboardButton(text="Yes", callback_data=yes_action))
    markup.row(types.InlineKeyboardButton(text="No", callback_data=no_action))
    await _send_html(bot, chat_id, text, reply_markup=markup)


async def _show_ban_duration_selector(bot, chat_id, target_user_id, message_id=None):
    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="1h", callback_data=f"ban_duration:{target_user_id}:1h"),
        types.InlineKeyboardButton(text="1d", callback_data=f"ban_duration:{target_user_id}:1d"),
        types.InlineKeyboardButton(text="1m", callback_data=f"ban_duration:{target_user_id}:1m"),
        types.InlineKeyboardButton(text="ForEver", callback_data=f"ban_duration:{target_user_id}:ForEver")
    )
    if message_id:
        await _edit_html(bot, chat_id, message_id, "How long?", reply_markup=markup)
    else:
        await _send_html(bot, chat_id, "How long?", reply_markup=markup)


async def handle_start_command(bot, message: types.Message, long_memory):
    """دستور /start"""
    user = message.from_user
    if _is_owner_or_admin(user.id, long_memory):
        await _show_main_control_panel(bot, message.chat.id, None, user=user)
        return

    welcome_msg = (
        "<tg-emoji emoji-id=\"5206357006864113601\">🌸</tg-emoji> <b>سلام! من ناتسوکی هستم!</b> <tg-emoji emoji-id=\"5206357006864113601\">🌸</tg-emoji>\n\n"
        "همون ناتسوکی از Doki Doki Literature Club!\n"
        "عاشق مانگا و پختن کاپ‌کیک هستم...\n\n"
        "<tg-emoji emoji-id=\"5206357006864113601\">📋</tg-emoji> <b>دستورات:</b>\n"
        "• /level - سطح دوستی\n"
        "• /mood - حالت فعلی\n"
        "• /features - قابلیت‌های ویژه\n\n"
        "حالا با من چت کن! فقط مواظب باش زیاد تعریف نکنی، خجالت می‌کشم! >///<"
    )
    await _reply_html(bot, message, welcome_msg)


async def handle_level_command(bot, message: types.Message, xp_system, special_features):
    """دستور /level"""
    user_id = message.from_user.id
    stats = xp_system.get_user_stats(user_id)
    features = special_features.get_features(stats["level"])

    response = (
        f"<tg-emoji emoji-id=\"5206357006864113601\">📊</tg-emoji> <b>وضعیت دوستی با ناتسوکی</b>\n\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">✨</tg-emoji> سطح: <b>{stats['level']}</b>\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">⭐</tg-emoji> XP: <b>{stats['xp']}</b>\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> تعاملات: <b>{stats['interactions']}</b>\n"
        f"<tg-emoji emoji-id=\"5206357006864113601\">🎁</tg-emoji> <b>قابلیت‌های ویژه:</b>\n"
    )

    for i, feature in enumerate(features, 1):
        response += f"  {i}. {feature}\n"

    if stats["level"] in {"Tsundere", "Confidant", "Devoted Friend", "Soulmate", "Eternal Bond"}:
        response += "\n💖 تو در یکی از عمیق‌ترین سطح‌های رابطه‌ای! ناتسوکی واقعاً بهت اهمیت می‌ده!"

    await _reply_html(bot, message, response)


async def handle_mood_command(bot, message: types.Message, mood_system):
    """دستور /mood"""
    user_id = message.from_user.id
    mood_details = mood_system.get_mood_details(user_id)
    mood = mood_details["mood"]
    update_user_mood(user_id, mood)

    mood_descriptions = {
        "Shy": "خجالت‌زده و کمی دست‌پاچه...",
        "Angry": "عصبانی و تند! مراقب باش!",
        "Happy": "خوشحال و پرانرژی!",
        "Affectionate": "مهربون... ولی نخواهی فهمید!",
        "Flustered": "دست‌پاچه و قرمز شده!",
        "Defensive": "دفاعی و محافظه‌کار",
        "Empathetic": "حساس به احساساتت و آماده‌ی همدردی",
        "Concerned": "نگرانت شده و با دقت گوش می‌دهد",
        "Curious": "کنجکاو و مشتاق فهمیدن منظورت",
        "Playful": "شوخ و بازیگوش، با محبت پنهان",
        "Sad": "دلگیر و کم‌حرف، اما هنوز اهمیت می‌دهد",
        "Lonely": "کمی تنها و نیازمند یک گفت‌وگوی صمیمی",
        "Proud": "به خودش یا تو افتخار می‌کند",
        "Jealous": "کمی حسود و زودرنج",
        "Frustrated": "کلافه و کم‌حوصله",
        "Calm": "آرام و آماده‌ی یک گفت‌وگوی خوب",
        "Excited": "هیجان‌زده و پرانرژی",
        "Protective": "حواسش به تو هست و می‌خواهد مراقبت کند",
        "Embarrassed": "خجالتی و دستپاچه",
        "Tender": "نرم، مهربان و دلگرم‌کننده",
    }

    description = mood_descriptions.get(mood, "حالت عادی")
    recent_moods = mood_details["recent_moods"]
    recent_text = ", ".join(recent_moods) if recent_moods else "هنوز احساس مشخصی از پیام‌ها ثبت نشده"
    response = (
        f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> <b>حالت فعلی ناتسوکی:</b> <b>{mood}</b>\n"
        f"{description}\n"
        f"<b>احساسات اخیر نسبت به گفت‌وگو:</b> {recent_text}"
    )

    await _reply_html(bot, message, response)


async def handle_features_command(bot, message: types.Message, xp_system, special_features):
    """دستور /features"""
    user_id = message.from_user.id
    stats = xp_system.get_user_stats(user_id)
    features = special_features.get_features(stats["level"])

    response = f"<tg-emoji emoji-id=\"5206357006864113601\">🎁</tg-emoji> <b>قابلیت‌های ویژه سطح {stats['level']}</b>\n\n"
    for i, feature in enumerate(features, 1):
        response += f"{i}. {feature}\n"

    response += f"\n<tg-emoji emoji-id=\"5206357006864113601\">📈</tg-emoji> با افزایش سطح دوستی، قابلیت‌های بیشتری باز می‌شه!"

    await _reply_html(bot, message, response)


async def handle_users_command(bot, message: types.Message, long_memory):
    """دستور /users"""
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    users = long_memory.get_all_users_sorted()
    if not users:
        await _reply_html(bot, message, "User list:\nNo users found.")
        return

    page_number = 1
    page_size = 5
    total_pages = max(1, (len(users) + page_size - 1) // page_size)
    text = _build_users_page_text(users, page_number, page_size, viewer_id=message.from_user.id)
    markup = _build_users_pagination_markup(
        page_number,
        total_pages,
        users=users,
        viewer_id=message.from_user.id,
    )
    await _send_html(bot, message.chat.id, text, reply_markup=markup)


async def handle_banlist_command(bot, message: types.Message, long_memory):
    """دستور /banlist"""
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    banned_users = long_memory.get_banned_users()
    if not banned_users:
        markup = InlineKeyboardBuilder()
        markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
        await _reply_html(bot, message, "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Ban list:\n<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> No users banned.", reply_markup=markup)
        return

    text = "Ban list:\n"
    for index, user in enumerate(banned_users, 1):
        text += "\n" + _format_user_row(user, index, mode="banlist")
        text += "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Unban user: <code>/unbanuser " + str(user.get("user_id", "Unknown")) + "</code>\n"
        text += "-------------------------\n"
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
    await _reply_html(bot, message, text, reply_markup=markup)


def _wrap_text_line(text, width=100):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = ""
    for word in words:
        if len((current + " " + word).strip()) <= width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _build_txt_report_lines(lines):
    report_lines = []
    for line in lines:
        for chunk in _wrap_text_line(line, width=120):
            report_lines.append(chunk)
    return report_lines


def _build_pdf_bytes_from_lines(lines):
    return "\n".join(lines).encode("utf-8")


def _generate_user_chat_txt(user_id, user_data):
    history = combine_histories(
        user_data.get("chat_history"),
        _load_chat_history_from_log(user_id),
        load_history_archive(user_id),
    )
    if not history:
        return None

    safe_username = _safe_username(user_data)
    lines = [
        "User chat history report",
        "=" * 40,
        f"Account name: {user_data.get('name') or 'Unknown'}",
        f"Username: {safe_username}",
        f"UserId: {user_id}",
        f"Interaction count: {user_data.get('interaction_count', 0)}",
        f"First use date: {user_data.get('created_at') or 'Unknown'}",
        f"Last use date: {user_data.get('last_interaction') or user_data.get('created_at') or 'Unknown'}",
        "",
    ]

    for entry in history:
        role = entry.get("role", "user")
        text = clean_text(entry.get("text"))
        if not text:
            continue

        timestamp = entry.get("timestamp") or "Unknown"
        speaker = "User" if role == "user" else "@NatsukiAiBot"
        lines.append(f"[{timestamp}] {speaker}: {text}")
        lines.append("")

    report = "\n".join(_build_txt_report_lines(lines)) + "\n"
    file_path = Path("data") / "logs" / f"chat_history_{user_id}.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(report, encoding="utf-8")
    return file_path


def _load_chat_history_from_log(user_id):
    """از فایل لاگ، پیام‌های کاربر و پاسخ ربات را پیدا می‌کند"""
    entries = []
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        return entries

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return entries

    target_id = str(user_id)
    for line in lines:
        if not line.strip():
            continue

        timestamp = line[:19] if len(line) >= 19 and line[4] == '-' and line[7] == '-' else "Unknown"

        user_match = re.search(rf"Message from\s*{re.escape(target_id)}\s*(?:\(@?[^\)]*\))?\s*:\s*(.*)$", line)
        if user_match:
            text = (user_match.group(1) or "").strip()
            if text:
                entries.append({"role": "user", "text": text, "timestamp": timestamp})
            continue

        bot_match = re.search(rf"Response sent to\s*{re.escape(target_id)}\s*(?:\(@?[^\)]*\))?\s*:\s*(.*)$", line)
        if bot_match:
            text = (bot_match.group(1) or "").strip()
            if text:
                entries.append({"role": "bot", "text": text, "timestamp": timestamp})
            continue

    return entries


def _open_user_history_terminal(user_id, user_data):
    """Open a UTF-8 Windows Terminal tab for one user's complete history."""
    title = str(user_data.get("name") or user_data.get("username") or user_id)
    base_dir = Path(__file__).resolve().parents[2]
    return open_history_terminal(user_id, title, base_dir, sys.executable)


def _generate_user_chat_pdf(user_id, user_data):
    history = combine_histories(
        user_data.get("chat_history"),
        _load_chat_history_from_log(user_id),
        load_history_archive(user_id),
    )
    if not history:
        return None

    safe_username = _safe_username(user_data)
    lines = [
        "User chat history",
        f"Account name: {user_data.get('name') or 'Unknown'}",
        f"Username: {safe_username}",
        f"UserId: {user_id}",
        f"Interaction count: {user_data.get('interaction_count', 0)}",
        f"first use date: {user_data.get('created_at') or 'Unknown'}",
        f"last use date: {user_data.get('last_interaction') or user_data.get('created_at') or 'Unknown'}",
        "",
    ]

    for entry in history:
        role = entry.get("role", "user")
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        timestamp = entry.get("timestamp") or "Unknown"
        if role == "user":
            speaker = f"[{timestamp}] {user_data.get('name') or 'Unknown'}"
            lines.append(f"{speaker}: {text}")
        else:
            lines.append(f"[{timestamp}] @NatsukiAiBot: {text}")

    pdf_bytes = _build_pdf_bytes_from_lines(lines)
    file_path = Path("data") / "logs" / f"chat_history_{user_id}.pdf"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(pdf_bytes)
    return file_path


async def handle_readmsg_command(bot, message: types.Message, long_memory):
    """دستور /readmsg"""
    if message.from_user.id != OWNER_ID:
        await _reply_html(bot, message, "<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> Access denied.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await _reply_html(bot, message, "Usage: /readmsg [userid]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await _reply_html(bot, message, "UserId must be a number.")
        return

    user_data = long_memory.get_user(user_id)
    history = combine_histories(
        user_data.get("chat_history"),
        _load_chat_history_from_log(user_id),
        load_history_archive(user_id),
    )
    if not history:
        await _reply_html(bot, message, "No chat history found for this user.")
        return

    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(
            text="Export .TXT file",
            callback_data=f"readmsg_export:{user_id}",
        )
    )
    markup.row(
        types.InlineKeyboardButton(
            text="Read on Terminal",
            callback_data=f"readmsg_terminal:{user_id}",
        )
    )
    await _reply_html(
        bot,
        message,
        f"Choose how to read chat history for user <code>{user_id}</code>:",
        reply_markup=markup,
    )


async def handle_addadmin_command(bot, message: types.Message, long_memory):
    """دستور /addadmin"""
    if message.from_user.id != OWNER_ID:
        await _reply_html(bot, message, "<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> Access denied.")
        return

    parts = (message.text or "").split()
    if len(parts) >= 2:
        try:
            target_id = int(parts[1])
        except ValueError:
            await _reply_html(bot, message, "UserId must be a number.")
            return

        if target_id == OWNER_ID:
            await _reply_html(bot, message, "The owner is already an admin.")
            return
        if long_memory.is_admin(target_id):
            await _reply_html(bot, message, "This user is already an admin.")
            return

        user = long_memory.get_user(target_id)
        if user.get("interaction_count", 0) <= 0:
            await _reply_html(bot, message, "This user has not started the bot yet.")
            return

        markup = InlineKeyboardBuilder()
        markup.row(
            types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_admin_add:{target_id}"),
            types.InlineKeyboardButton(text="No", callback_data="open_admin_control")
        )
        text = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to want add this user to admin?\n\n" + _format_user_row(user, 1, mode="user")
        await _reply_html(bot, message, text, reply_markup=markup)
        return

    admins = long_memory.get_admin_users()
    text = _build_admin_list_text(admins)
    markup = _build_admin_list_markup(owner_only=True)
    await _reply_html(bot, message, text, reply_markup=markup)


async def handle_dltadmin_command(bot, message: types.Message, long_memory):
    """دستور /dltadmin"""
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await _reply_html(bot, message, "Usage: /dltadmin [userid]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await _reply_html(bot, message, "UserId must be a number.")
        return

    if user_id == OWNER_ID:
        await _reply_html(bot, message, "The owner cannot be removed from admin access.")
        return

    user = long_memory.get_user(user_id)
    if not user.get("is_admin"):
        await _reply_html(bot, message, "This user is not an admin.")
        return

    await _show_user_confirmation(bot, message.chat.id, user_id, long_memory, action="delete_admin")


async def handle_banuser_command(bot, message: types.Message, long_memory):
    """دستور /banuser"""
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await _reply_html(bot, message, "Usage: /banuser [userid]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await _reply_html(bot, message, "UserId must be a number.")
        return

    await _show_user_confirmation(bot, message.chat.id, user_id, long_memory, action="ban")


async def handle_unbanuser_command(bot, message: types.Message, long_memory):
    """دستور /unbanuser"""
    if not await _ensure_owner_admin(bot, message, long_memory):
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await _reply_html(bot, message, "Usage: /unbanuser [userid]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await _reply_html(bot, message, "UserId must be a number.")
        return

    user = long_memory.get_user(user_id)
    if not user.get("banned"):
        await _reply_html(bot, message, "This user is not banned.")
        return

    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_unban:{user_id}"))
    markup.row(types.InlineKeyboardButton(text="No", callback_data=f"cancel_unban:{user_id}"))
    prompt = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to unban this user?\n\n" + _format_user_row(user, 1, mode="user")
    await _reply_html(bot, message, prompt, reply_markup=markup)


async def _show_banlist_from_memory(bot, chat_id, message_id, long_memory):
    banned_users = long_memory.get_banned_users()
    if not banned_users:
        text = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Ban list:\n<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> No users banned."
        markup = InlineKeyboardBuilder()
        markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
        await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)
        return

    text = "Ban list:\n"
    for index, user in enumerate(banned_users, 1):
        text += "\n" + _format_user_row(user, index, mode="banlist")
        text += "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Unban user: <code>/unbanuser " + str(user.get("user_id", "Unknown")) + "</code>\n"
        text += "-------------------------\n"
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
    await _edit_html(bot, chat_id, message_id, text, reply_markup=markup)


async def _show_power_confirmation(bot, chat_id, message_id, action):
    action_text = "off" if action == "off" else "on"
    prompt = f"<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to want turn {action_text} bot?"
    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_turn_{action}_bot"))
    markup.row(types.InlineKeyboardButton(text="No", callback_data="back_to_main"))
    await _edit_html(bot, chat_id, message_id, prompt, reply_markup=markup)


async def handle_ban_action(bot, call: types.CallbackQuery, long_memory):
    """مدیریت کلیک روی Ban user و Unban"""
    data = call.data or ""

    if data.startswith("readmsg_export:") or data.startswith("readmsg_terminal:"):
        if call.from_user.id != OWNER_ID:
            await call.answer("Access denied.", show_alert=True)
            return
        try:
            user_id = int(data.split(":", 1)[1])
        except ValueError:
            await call.answer("Invalid user id.", show_alert=True)
            return

        user_data = long_memory.get_user(user_id)
        history = combine_histories(
            user_data.get("chat_history"),
            _load_chat_history_from_log(user_id),
            load_history_archive(user_id),
        )
        if not history:
            await call.answer("No chat history found for this user.", show_alert=True)
            return

        if data.startswith("readmsg_export:"):
            await _edit_html(
                bot,
                call.message.chat.id,
                call.message.message_id,
                "<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Searching...",
            )
            txt_path = _generate_user_chat_txt(user_id, user_data)
            if not txt_path:
                await call.answer("No chat history found for this user.", show_alert=True)
                return
            await bot.send_document(
                call.message.chat.id,
                FSInputFile(str(txt_path)),
                caption=_html_text(
                    f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Chat history export\n<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> UserId: {user_id}\n"
                    f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Account name: {user_data.get('name') or 'Unknown'}\n"
                    f"<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> Username: {_safe_username(user_data)}"
                ),
                parse_mode="HTML",
                disable_content_type_detection=True,
            )
            await call.answer("TXT file exported.")
            return

        opened, result = _open_user_history_terminal(user_id, user_data)
        await call.answer(result, show_alert=not opened)
        return

    if data == "back_to_main":
        await _show_main_control_panel(bot, call.message.chat.id, call.message.message_id, user=call.from_user)
        return

    if data == "open_premium_emojis":
        await _show_premium_emoji_panel(
            bot,
            call.message.chat.id,
            long_memory,
            call.message.message_id,
        )
        await call.answer()
        return

    if data in {"add_emoji_prompt", "edit_emoji_prompt"}:
        await _show_premium_emoji_prompt(
            bot,
            call.message.chat.id,
            call.message.message_id,
            "emoji_add" if data == "add_emoji_prompt" else "emoji_edit",
        )
        await call.answer()
        return

    if data.startswith("delete_emoji:"):
        tag = data.split(":", 1)[1]
        if long_memory.delete_premium_emoji(tag):
            await call.answer("Emoji deleted.")
        else:
            await call.answer("Emoji not found.")
        await _show_premium_emoji_panel(
            bot,
            call.message.chat.id,
            long_memory,
            call.message.message_id,
        )
        return

    if data == "turn_off_bot":
        await _show_power_confirmation(bot, call.message.chat.id, call.message.message_id, "off")
        return

    if data == "turn_on_bot":
        await _show_power_confirmation(bot, call.message.chat.id, call.message.message_id, "on")
        return

    if data == "confirm_turn_off_bot":
        await _edit_html(bot, call.message.chat.id, call.message.message_id, "SHUTTINH DOWN")

        async def finalize_turn_off():
            _set_core_active(False)
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "BOT TURN OFF!")
            await asyncio.sleep(1.5)
            await _show_main_control_panel(bot, call.message.chat.id, call.message.message_id, user=call.from_user)

        asyncio.create_task(finalize_turn_off())
        return

    if data == "confirm_turn_on_bot":
        await _edit_html(bot, call.message.chat.id, call.message.message_id, "TURNING ON")

        async def finalize_turn_on():
            _set_core_active(True)
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "BOT TURN ON!")
            await asyncio.sleep(1.5)
            await _show_main_control_panel(bot, call.message.chat.id, call.message.message_id, user=call.from_user)

        asyncio.create_task(finalize_turn_on())
        return

    if data == "open_admin_control":
        await _show_admin_list(bot, call.message.chat.id, call.message.message_id, long_memory, user_id=call.from_user.id)
        return

    if data == "open_admin_add":
        await _show_admin_add_prompt(bot, call.message.chat.id, call.message.message_id)
        return

    if data.startswith("confirm_admin_add:"):
        try:
            user_id = int(data.split(":", 1)[1])
            if user_id == OWNER_ID:
                await _edit_html(bot, call.message.chat.id, call.message.message_id, "The owner is already an admin.")
                return
            if long_memory.is_admin(user_id):
                await _edit_html(bot, call.message.chat.id, call.message.message_id, "This user is already an admin.")
                return
            long_memory.set_admin(user_id, True)
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "Admin added!")

            await asyncio.sleep(2)
            await _show_admin_list(bot, call.message.chat.id, call.message.message_id, long_memory, user_id=call.from_user.id)
        except Exception:
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "Error while adding admin.")
        return

    if data == "cancel_admin_add":
        await _show_admin_list(bot, call.message.chat.id, call.message.message_id, long_memory, user_id=call.from_user.id)
        return

    if data == "open_users":
        users = long_memory.get_all_users_sorted()
        if not users:
            markup = InlineKeyboardBuilder()
            markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "User list:\nNo users found.", reply_markup=markup)
            return
        page_number = 1
        total_pages = max(1, (len(users) + 4) // 5)
        text = _build_users_page_text(users, page_number, 5, viewer_id=call.from_user.id)
        markup = _build_users_pagination_markup(
            page_number,
            total_pages,
            users=users,
            viewer_id=call.from_user.id,
        )
        await _edit_html(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup)
        return

    if data == "open_banlist":
        await _show_banlist_from_memory(bot, call.message.chat.id, call.message.message_id, long_memory)
        return

    if data == "open_addadmin":
        admins = long_memory.get_admin_users()
        if not admins:
            markup = InlineKeyboardBuilder()
            markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "admin list:\nNo admins found.", reply_markup=markup)
            return
        text = "admin list:\n"
        for index, user in enumerate(admins, 1):
            text += "\n" + _format_user_row(user, index, mode="admin")
            text += f"delete admin: <code>/dltadmin {user.get('user_id', 'Unknown')}</code>\n"
            text += "-------------------------\n"
        markup = InlineKeyboardBuilder()
        markup.row(types.InlineKeyboardButton(text="Back", callback_data="back_to_main"))
        await _edit_html(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup)
        return

    if data.startswith("users_page:"):
        try:
            page_number = int(data.split(":", 1)[1])
            users = long_memory.get_all_users_sorted()
            total_pages = max(1, (len(users) + 4) // 5)
            if page_number < 1:
                page_number = 1
            if page_number > total_pages:
                page_number = total_pages

            text = _build_users_page_text(users, page_number, 5, viewer_id=call.from_user.id)
            markup = _build_users_pagination_markup(
                page_number,
                total_pages,
                users=users,
                viewer_id=call.from_user.id,
            )
            await _edit_html(bot, call.message.chat.id, call.message.message_id, text, reply_markup=markup)
        except Exception:
            await call.answer("Unable to navigate page.")
        return

    if data.startswith("banuser:"):
        try:
            user_id = int(data.split(":", 1)[1])
            await _show_user_confirmation(bot, call.message.chat.id, user_id, long_memory, action="ban")
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            await call.answer("Unable to process ban action.")
        return

    if data.startswith("confirm_ban:"):
        user_id = int(data.split(":", 1)[1])
        await _show_ban_duration_selector(bot, call.message.chat.id, user_id, message_id=call.message.message_id)
        return

    if data.startswith("ban_duration:"):
        try:
            _, user_id, duration = data.split(":", 2)
            user_id = int(user_id)
            long_memory.set_user_ban(user_id, True, duration)
            await _edit_html(bot, call.message.chat.id, call.message.message_id, f"User banned for {duration}")
        except Exception:
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "Error while banning user.")
        return

    if data.startswith("cancel_ban:"):
        await _edit_html(bot, call.message.chat.id, call.message.message_id, "Action canceled.")
        return

    if data.startswith("dltadmin:"):
        try:
            user_id = int(data.split(":", 1)[1])
            await _show_user_confirmation(bot, call.message.chat.id, user_id, long_memory, action="delete_admin")
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            await call.answer("Unable to process delete action.")
        return

    if data.startswith("confirm_dltadmin:"):
        try:
            user_id = int(data.split(":", 1)[1])
            if user_id != OWNER_ID:
                long_memory.set_admin(user_id, False)
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "Admin removed.")
        except Exception:
            await _edit_html(bot, call.message.chat.id, call.message.message_id, "Error while deleting admin.")
        return

    if data.startswith("cancel_dltadmin:"):
        await _edit_html(bot, call.message.chat.id, call.message.message_id, "Action canceled.")
        return

    if data.startswith("unban:"):
        user_id = int(data.split(":", 1)[1])
        user = long_memory.get_user(user_id)
        markup = InlineKeyboardBuilder()
        markup.row(types.InlineKeyboardButton(text="Yes", callback_data=f"confirm_unban:{user_id}"))
        markup.row(types.InlineKeyboardButton(text="No", callback_data=f"cancel_unban:{user_id}"))
        prompt = "<tg-emoji emoji-id=\"5206357006864113601\">😊</tg-emoji> Are you sure to unban this user?\n\n" + _format_user_row(user, 1, mode="user")
        await _edit_html(bot, call.message.chat.id, call.message.message_id, prompt, reply_markup=markup)
        return

    if data.startswith("confirm_unban:"):
        user_id = int(data.split(":", 1)[1])
        long_memory.set_user_ban(user_id, False)
        await _edit_html(bot, call.message.chat.id, call.message.message_id, "User unbaned!")

        await asyncio.sleep(3)
        await _show_banlist_from_memory(bot, call.message.chat.id, call.message.message_id, long_memory)
        return

    if data.startswith("cancel_unban:"):
        await _show_banlist_from_memory(bot, call.message.chat.id, call.message.message_id, long_memory)
