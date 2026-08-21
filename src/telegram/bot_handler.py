import asyncio
import re
from aiogram import Bot, Dispatcher, types, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TELEGRAM_BOT_TOKEN
from src.utils.logger import setup_logger
from src.memory.long_memory import LongTermMemory
from src.memory.short_memory import ShortTermMemory
from src.memory.xp_system import XPSystem
from src.personality.mood_system import MoodSystem
from src.personality.response_generator import ResponseGenerator
from src.personality.special_features import SpecialFeatures
from src.core.core_handler import CoreHandler
from src.telegram.guest_mode import GuestModeHandler
from src.telegram.proxy import get_system_proxy
from src.telegram.commands import _reply_html
from src.utils.runtime_monitor import (
    record_api_call,
    record_event,
    record_user,
    update_user_mood,
    set_bot_state,
)

logger = setup_logger()
OWNER_ID = 7915402928


class NatsukiBot:
    def __init__(self):
        proxy = get_system_proxy()
        session = AiohttpSession(proxy=proxy)
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
        logger.info("Telegram proxy: %s", proxy or "disabled")
        self.dp = Dispatcher()
        self.router = Router()
        self.api_traffic = 0
        self.long_memory = LongTermMemory()
        self.short_memory = ShortTermMemory()
        self.xp_system = XPSystem(self.long_memory)
        self.mood_system = MoodSystem(self.long_memory)
        self.response_generator = ResponseGenerator(self.long_memory)
        self.core_handler = CoreHandler(self.bot)
        self.guest_mode_handler = GuestModeHandler(
            self.bot,
            self.response_generator,
            self.mood_system,
            self.long_memory
        )

        # تنظیم هندلرها
        self._setup_handlers()

    def _core_allowed(self, message: types.Message, allow_owner_commands=False):
        if self.core_handler.has_core_file():
            return True

        if allow_owner_commands and message.from_user.id == OWNER_ID:
            return True

        return False
    
    def _setup_handlers(self):
        """تنظیم هندلرهای تلگرام"""

        @self.dp.errors()
        async def handle_telegram_errors(event):
            if isinstance(event.exception, TelegramForbiddenError):
                record_event(
                    "user_blocked_bot",
                    "Telegram rejected a response because the user blocked the bot",
                )
                return True
            return False

        async def track_message_activity(handler, event, data):
            user = event.from_user
            if user is not None:
                self.long_memory.sync_user_profile(
                    user.id,
                    first_name=user.full_name,
                    username=user.username,
                )
                text = event.text or ""
                record_user(
                    user.id,
                    user.full_name,
                    user.username,
                    "command" if text.startswith("/") else "message",
                )
            return await handler(event, data)
        self.dp.message.outer_middleware(track_message_activity)

        async def track_control_activity(handler, event, data):
            user = event.from_user
            action = event.data or "unknown_callback"
            record_event(
                "control_action",
                f"{action} requested by {user.full_name} ({user.id})",
            )
            try:
                return await handler(event, data)
            except Exception as error:
                record_event("control_action_failed", f"{action}: {error}", level="ERROR")
                raise
        self.dp.callback_query.outer_middleware(track_control_activity)
        
        # دستورات
        @self.router.message(Command("start"))
        @self.router.message(Command("help"))
        async def handle_start(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_start_command
            await handle_start_command(self.bot, message, self.long_memory)

        @self.router.message(Command("addadmin"))
        async def handle_addadmin(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_addadmin_command
            await handle_addadmin_command(self.bot, message, self.long_memory)

        @self.router.message(Command("dltadmin"))
        async def handle_dltadmin(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_dltadmin_command
            await handle_dltadmin_command(self.bot, message, self.long_memory)

        @self.router.message(Command("banuser"))
        async def handle_banuser(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_banuser_command
            await handle_banuser_command(self.bot, message, self.long_memory)

        @self.router.message(Command("unbanuser"))
        async def handle_unbanuser(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_unbanuser_command
            await handle_unbanuser_command(self.bot, message, self.long_memory)
        
        @self.router.message(Command("level"))
        async def handle_level(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_level_command
            await handle_level_command(self.bot, message, self.xp_system, SpecialFeatures)
        
        @self.router.message(Command("mood"))
        async def handle_mood(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_mood_command
            await handle_mood_command(self.bot, message, self.mood_system)
        
        @self.router.message(Command("features"))
        async def handle_features(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_features_command
            await handle_features_command(self.bot, message, self.xp_system, SpecialFeatures)

        @self.router.message(Command("users"))
        async def handle_users(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_users_command
            await handle_users_command(self.bot, message, self.long_memory)

        @self.router.message(Command("banlist"))
        async def handle_banlist(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_banlist_command
            await handle_banlist_command(self.bot, message, self.long_memory)

        @self.router.message(Command("readmsg"))
        async def handle_readmsg(message: types.Message):
            if self.long_memory.is_user_banned(message.from_user.id):
                user_data = self.long_memory.get_user(message.from_user.id)
                ban_time = user_data.get("ban_duration") or "unknown"
                await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> unfortunately, you are ban for {ban_time}\nplease wait until your ban time end")
                return
            if not self._core_allowed(message, allow_owner_commands=True):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            from src.telegram.commands import handle_readmsg_command
            await handle_readmsg_command(self.bot, message, self.long_memory)

        @self.router.message(Command("emojis"))
        async def handle_emojis(message: types.Message):
            from src.telegram.commands import handle_premium_emoji_command
            await handle_premium_emoji_command(self.bot, message, self.long_memory)

        @self.router.message(Command("addemoji"))
        async def handle_addemoji(message: types.Message):
            from src.telegram.commands import handle_premium_emoji_write_command
            await handle_premium_emoji_write_command(self.bot, message, self.long_memory, "addemoji")

        @self.router.message(Command("editemoji"))
        async def handle_editemoji(message: types.Message):
            from src.telegram.commands import handle_premium_emoji_write_command
            await handle_premium_emoji_write_command(self.bot, message, self.long_memory, "editemoji")

        @self.router.callback_query()
        async def handle_callbacks(query: types.CallbackQuery):
            from src.telegram.commands import handle_ban_action
            await handle_ban_action(self.bot, query, self.long_memory)

        # هندلر اصلی
        @self.router.message()
        async def handle_all_messages(message: types.Message):
            if not self._core_allowed(message):
                await _reply_html(self.bot, message, "natsuki.chr dose not exist.")
                return
            await self._handle_message(message)
        
        # اضافه کردن router به dispatcher
        self.dp.include_router(self.router)
        self.dp.include_router(self.guest_mode_handler.router)
    
    async def _should_respond(self, message: types.Message, is_private):
        """تعیین آیا باید پاسخ دهد یا نه"""
        if is_private:
            return True
        
        if not message.text:
            return False
        
        text_lower = message.text.lower()
        
        # بررسی تگ‌ها و نام‌ها
        triggers = [
            "@natsuki", "ناتسوکی", "/natsu",
            "نظر ناتسوکی", "چی میگه ناتسوکی",
            "what does natsuki think about this"
        ]
        
        if any(trigger in text_lower for trigger in triggers):
            return True
        
        # پاسخ به ریپلای
        if message.reply_to_message:
            try:
                me = await self.bot.get_me()
                if message.reply_to_message.from_user.id == me.id:
                    return True
            except:
                pass
        
        return False

    async def _keep_typing(self, chat_id):
        while True:
            await self.bot.send_chat_action(
                chat_id,
                "typing",
                request_timeout=5,
            )
            await asyncio.sleep(4)
    
    async def _handle_message(self, message: types.Message):
        """پردازش پیام دریافتی"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        text = message.text or ""
        is_private = message.chat.type == "private"
        username = message.from_user.username or "unknown"
        first_name = message.from_user.first_name or "Unknown"
        logger.info(f"Message from {user_id} (@{username}): {text[:50]}...")

        from src.telegram.commands import _handle_admin_prompt_input
        if await _handle_admin_prompt_input(self.bot, message, self.long_memory):
            return

        if self.long_memory.is_user_banned(user_id):
            user_data = self.long_memory.get_user(user_id)
            ban_time = user_data.get("ban_duration") or "unknown"
            ban_message = (
                f"unfortunately, you are ban for {ban_time}\n"
                "please wait until your ban time end"
            )
            await _reply_html(self.bot, message, f"<tg-emoji emoji-id=\"5206357006864113601\">⛔</tg-emoji> {ban_message}")
            return

        # بررسی آیا باید پاسخ دهد
        if not await self._should_respond(message, is_private):
            return

        thinking_message = None
        typing_task = None
        try:
            typing_task = asyncio.create_task(self._keep_typing(chat_id))
            thinking_message = await _reply_html(self.bot, message, "<tg-emoji emoji-id=\"5206357006864113601\">💭</tg-emoji> Thinking")
            logger.info("Thinking message sent to %s", user_id)
            # guest mode: reply as a guest when the bot is not actually in the chat history
            guest_mode = (message.chat.type != "private" and not is_private)
            guest_notice = ""
            if guest_mode:
                guest_notice = (
                    "<i>No chat history. "
                    "<a href=\"https://t.me/NatsukiAiBot?startgroup=guest_mode&amp;admin=invite_users+manage_topics\">"
                    "Add me to the chat</a> for full access.</i>"
                )

            # پردازش پیام
            response = await asyncio.to_thread(
                self._process_message,
                user_id,
                text,
                username=username,
                first_name=first_name,
            )

            if thinking_message is not None:
                try:
                    await self.bot.delete_message(chat_id, thinking_message.message_id)
                except Exception:
                    pass

            if guest_mode:
                reply_text = f"{response}\n \n{guest_notice}"
                await _reply_html(self.bot, message, reply_text)
            else:
                await _reply_html(self.bot, message, response)

            logger.info(f"Response sent to {user_id} (@{username}): {response[:400]}")

        except Exception as e:
            if isinstance(e, TelegramForbiddenError):
                record_event(
                    "user_blocked_bot",
                    f"User {user_id} blocked the bot; response skipped",
                )
                return
            logger.error(f"Error handling message: {e}", exc_info=True)
            try:
                if thinking_message is not None:
                    await self.bot.delete_message(chat_id, thinking_message.message_id)
            except Exception:
                pass
            await _reply_html(
                self.bot,
                message,
                "<tg-emoji emoji-id=\"5206357006864113601\">⚠️</tg-emoji> خطایی رخ داد! لطفاً دوباره تلاش کن.",
            )
        finally:
            if typing_task is not None:
                typing_task.cancel()
                await asyncio.gather(typing_task, return_exceptions=True)
    
    def _process_message(self, user_id, text, username=None, first_name=None):
        """پردازش کامل پیام و تولید پاسخ"""
        
        # 1. به‌روزرسانی حافظه بلندمدت
        user_data = self.long_memory.update_from_message(user_id, text, username=username, first_name=first_name)
        
        # 2. افزودن به حافظه کوتاه‌مدت
        self.short_memory.add(user_id, text)
        
        # 3. تحلیل خلق‌وخو
        self.mood_system.analyze_message_mood(text, user_id)
        
        # 4. افزایش XP
        self.xp_system.add_xp(user_id)
        
        # 5. تعیین خلق‌وخوی فعلی
        mood = self.mood_system.determine_current_mood(user_id)
        update_user_mood(user_id, mood)
        
        # 6. دریافت حافظه کوتاه‌مدت فرمت‌شده
        short_mem = self.short_memory.get_formatted(user_id, limit=5)
        
        # 7. تولید پاسخ
        self.api_traffic += 1
        record_api_call()
        response = self.response_generator.generate(
            user_text=text,
            user_data=user_data,            short_memory_text=short_mem,
            mood=mood
        )
        self.long_memory.add_chat_message(user_id, "bot", response)

        return response
    
    async def start(self, command_queue=None, control_ready=None):
        """شروع بات"""
        polling_task = None
        command_task = None
        try:
            me = await self.bot.get_me()
            logger.info(f"Bot started: {me.first_name} (@{me.username})")
            logger.info("Bot is polling...")
            if control_ready is not None:
                control_ready.set()
            set_bot_state("running", f"Polling as @{me.username}")
            record_event("bot_started", f"Polling as @{me.username}")
            polling_task = asyncio.create_task(self.dp.start_polling(self.bot))

            if command_queue is None:
                await polling_task
                return "stopped"

            command_task = asyncio.create_task(asyncio.to_thread(command_queue.get))
            done, _ = await asyncio.wait(
                {polling_task, command_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if polling_task in done:
                await polling_task
                return "stopped"

            command = command_task.result()
            if command == "y":
                record_event("shutdown_requested", "Complete shutdown requested from the main console")
                await self.dp.stop_polling()
                await polling_task
                set_bot_state("stopped", "Complete shutdown finished")
                return "stopped"
            if command == "r":
                record_event("restart_requested", "Restart requested to apply the latest changes")
                await self.dp.stop_polling()
                await polling_task
                set_bot_state("restarting", "Polling stopped for restart")
                return "restart"
        except Exception as e:
            set_bot_state("error", str(e))
            record_event("bot_error", str(e), level="ERROR")
            logger.critical(f"Failed to start bot: {e}", exc_info=True)
            raise
        finally:
            for task in (command_task, polling_task):
                if task is not None and not task.done():
                    task.cancel()
            await self.bot.session.close()

async def start_bot(command_queue=None, control_ready=None):
    """تابع شروع بات"""
    bot = NatsukiBot()
    return await bot.start(command_queue, control_ready)
