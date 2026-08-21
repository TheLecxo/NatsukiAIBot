import logging
import sys
import io
import os
from config import LOG_FILE


class MainConsoleFilter(logging.Filter):
    """Keep the primary console limited to the requested startup status."""

    ALLOWED_MESSAGES = (
        "=" * 50,
        "Starting Natsuki Bot...",
        "Telegram proxy:",
        "OpenAI client is runnig",
        "Gemini client is runnig",
        "GuestModeHandler initialized",
        "Bot started:",
        "Bot is polling...",
    )

    def filter(self, record):
        if os.getenv("NATSUKI_MAIN_CONSOLE") != "1":
            return True
        message = record.getMessage()
        return any(message == item or message.startswith(item) for item in self.ALLOWED_MESSAGES)


class RuntimeErrorHandler(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        try:
            from src.utils.runtime_monitor import record_event
            record_event("logger_error", self.format(record), level="ERROR")
        except Exception:
            pass

def setup_logger(name="natsuki_bot"):
    """تنظیم و بازگرداندن logger با پشتیبانی UTF-8"""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # جلوگیری از لاگ‌های تکراری
    if logger.handlers:
        return logger
    
    # فرمت لاگ
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # هندلر فایل (UTF-8)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # هندلر کنسول (UTF-8 برای Windows)
    # Windows Console به طور پیش‌فرض cp1252 استفاده می‌کند
    # باید به UTF-8 تغییر دهیم
    try:
        # اگر console قابل encoding است
        if hasattr(sys.stdout, 'buffer'):
            console_stream = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                line_buffering=True
            )
        else:
            console_stream = sys.stdout
    except Exception:
        console_stream = sys.stdout
    
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(MainConsoleFilter())
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    runtime_handler = RuntimeErrorHandler()
    runtime_handler.setFormatter(formatter)
    logger.addHandler(runtime_handler)
    
    return logger
