import traceback
from src.utils.logger import setup_logger

logger = setup_logger()


def describe_error(error):
    """تبدیل یک خطا به توضیح کوتاه و قابل فهم به زبان فارسی"""
    if error is None:
        return "خطایی نامشخص رخ داده است. لطفاً دوباره تلاش کنید."

    message = str(error).strip()
    lower_msg = message.lower()
    error_type = type(error).__name__

    if "insufficient balance" in lower_msg or "402" in lower_msg or "balance" in lower_msg and "insufficient" in lower_msg:
        return "⚠️ مشکلی در اعتبار حساب رخ داده است: موجودی سرویس AI کافی نیست. لطفاً حساب را شارژ کنید یا از سرویس جایگزین استفاده کنید."

    if "not found" in lower_msg or "404" in lower_msg:
        return "⚠️ سرویس یا مدل موردنظر پیدا نشد. ممکن است آدرس یا نام مدل اشتباه باشد."

    if "ssl" in lower_msg or "unexpected eof" in lower_msg or "certificate" in lower_msg or "connection" in lower_msg:
        return "⚠️ مشکل اتصال به سرور رخ داده است. اینترنت، VPN و تنظیمات امنیتی را بررسی کنید."

    if "api key" in lower_msg or "unauthorized" in lower_msg or "forbidden" in lower_msg:
        return "⚠️ کلید دسترسی نامعتبر یا غیرفعال است. لطفاً تنظیمات API را بررسی کنید."

    if "timeout" in lower_msg or "timed out" in lower_msg:
        return "⚠️ درخواست زمان زیادی طول کشید و به پایان رسید. لطفاً دوباره تلاش کنید."

    if "rate limit" in lower_msg or "429" in lower_msg or "too many requests" in lower_msg:
        return "⚠️ تعداد درخواست‌ها بیش از حد مجاز است. کمی بعد دوباره امتحان کنید."

    if "503" in lower_msg or "unavailable" in lower_msg or "high demand" in lower_msg or "temporarily unavailable" in lower_msg:
        return "⚠️ سرور مدل در حال حاضر شلوغ است و درخواست شما به‌صورت موقت رد شد. کمی صبر کنید و دوباره امتحان کنید."

    if "telegram" in lower_msg or "bot" in lower_msg:
        return "⚠️ مشکلی در ارتباط با ربات تلگرام اتفاق افتاده است. توکن یا وضعیت اتصال را بررسی کنید."

    if "json" in lower_msg or "parse" in lower_msg or "decode" in lower_msg:
        return "⚠️ داده دریافتی نامعتبر است و قابل پردازش نیست."

    if "file" in lower_msg or "memory" in lower_msg or "permission" in lower_msg:
        return "⚠️ مشکلی در ذخیره یا دسترسی به داده‌ها رخ داده است."

    if not message:
        return f"⚠️ یک خطای {error_type} رخ داد، اما توضیح دقیق‌تری وجود ندارد. لطفاً دوباره تلاش کنید."

    return f"⚠️ خطایی رخ داد: {error_type}. توضیح کوتاه: {message[:180]}"


def format_error_report(error, context=None):
    """ساخت یک گزارش کوتاه، زیبا و قابل فهم از خطا به زبان فارسی"""
    title = "⚠️ گزارش خطا"
    summary = describe_error(error)
    details = f"نوع خطا: {type(error).__name__}"

    if context:
        details += f"\nبخش: {context}"

    if str(error).strip():
        details += f"\nجزئیات: {str(error)[:220]}"

    return f"{title}\n{summary}\n\n{details}"


def safe_execute(func, fallback_value=None, *args, **kwargs):
    """اجرای امن یک تابع با مدیریت خطا"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}")
        logger.error(format_error_report(e, context=func.__name__))
        return fallback_value


def get_fallback_response(user_level="Novice"):
    """دریافت پاسخ جایگزین بر اساس سطح کاربر"""
    fallback_responses = {
        "Novice": [
            "هوم... الان نمی‌تونم درست فکر کنم!",
            "ببخشید، یه مشکلی پیش اومده...",
        ],
        "Friendly": [
            "اوه، خطایی رخ داد! اما مهم نیست...",
            "چیزی اشتباه شد، ولی می‌تونیم ادامه بدیم!",
        ],
        # ... بقیه سطوح
    }
    import random
    return random.choice(fallback_responses.get(user_level, fallback_responses["Novice"]))