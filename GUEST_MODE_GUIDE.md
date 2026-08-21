# Natsuki Guest Mode

Guest Mode is implemented with Aiogram 3 inline mode. It does not use Telethon, MTProto, API ID/HASH, or a user session.

## Setup

1. Open `@BotFather`.
2. Run `/setinline`.
3. Select the Natsuki bot and enable inline mode.
4. Start the bot with `python main.py`.

## Usage

In any chat where inline mode is available, type:

```text
@YourBotUsername your message
```

Select the Natsuki result to insert the generated response into the chat. The bot does not need to be a member of that chat for inline results.

## Architecture

- `src/telegram/guest_mode.py` defines a dedicated Aiogram `Router`.
- The router handles `InlineQuery` updates and returns an `InlineQueryResultArticle`.
- `src/telegram/bot_handler.py` includes the guest router in the main `Dispatcher`.
- Responses use the existing memory, mood, and response-generation services.
- Inline query answers are personal and are not cached.

## Important limitation

Aiogram can handle Bot API updates such as inline queries. Telegram's low-level `updateBotGuestChatQuery` MTProto update is not exposed as a normal Aiogram handler, so this implementation uses the supported inline-mode flow instead.

## Troubleshooting

- If no result appears, verify that `/setinline` is enabled for the bot.
- If the bot does not start, check `TELEGRAM_BOT_TOKEN` and the application logs in `data/logs/`.
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_GUEST_SESSION` are no longer used.

## References

- [Aiogram documentation](https://docs.aiogram.dev/en/latest/)
- [Aiogram dispatcher](https://docs.aiogram.dev/en/latest/dispatcher/)
- [Telegram inline mode](https://core.telegram.org/bots/inline)
