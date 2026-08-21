import asyncio

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from config import TELEGRAM_BOT_TOKEN
from src.utils.logger import setup_logger

logger = setup_logger()


class GuestModeHandler:
    """Handle guest-style interactions through Telegram inline mode."""

    def __init__(self, bot, response_generator, mood_system, long_memory):
        self.bot = bot
        self.response_generator = response_generator
        self.mood_system = mood_system
        self.long_memory = long_memory
        self.router = Router(name="guest_mode")
        self.router.inline_query()(self.handle_inline_query)
        logger.info("GuestModeHandler initialized")

    @property
    def is_configured(self):
        return bool(TELEGRAM_BOT_TOKEN)

    async def handle_inline_query(self, query: InlineQuery) -> None:
        """Return one inline result that can be inserted into any chat."""
        text = (query.query or "").strip()
        if not text:
            await query.answer(results=[], cache_time=1, is_personal=True)
            return

        user = query.from_user
        response = await asyncio.to_thread(
            self._generate_response,
            user.id,
            text,
            user.username,
            user.first_name,
        )
        response = self._prepare_inline_text(response)
        result = InlineQueryResultArticle(
            id=f"natsuki_guest_{query.id}",
            title="Natsuki",
            description=response[:200],
            input_message_content=InputTextMessageContent(
                message_text=response[:4096],
                parse_mode="HTML",
            ),
        )
        await query.answer(results=[result], cache_time=0, is_personal=True)
        logger.info("Guest response prepared for inline query %s", query.id)

    def _generate_response(self, user_id, text, username=None, first_name=None):
        user_data = self.long_memory.update_from_message(
            user_id,
            text,
            username=username,
            first_name=first_name,
        )
        self.mood_system.analyze_message_mood(text, user_id)
        mood = self.mood_system.determine_current_mood(user_id)
        response = self.response_generator.generate(
            user_text=text,
            user_data=user_data,
            short_memory_text="",
            mood=mood,
        )
        self.long_memory.add_chat_message(user_id, "bot", response)
        return response

    @staticmethod
    def _prepare_inline_text(response):
        """Preserve Telegram HTML, including premium custom emoji tags."""
        return str(response)

    @staticmethod
    def is_guest_mode_supported():
        return bool(TELEGRAM_BOT_TOKEN)

    @staticmethod
    def get_guest_mode_info():
        return (
            "Guest Mode uses Aiogram inline mode. Enable inline mode for the bot "
            "with BotFather, then mention it in a chat."
        )
