import re

from openai import OpenAI
from config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_TIMEOUT,
    GEMINI_API_KEY, GEMINI_MODEL,
    PERSIAN_PERSONALITY_PROMPT, ENGLISH_PERSONALITY_PROMPT
)
from src.utils.logger import setup_logger
from src.utils.error_handler import safe_execute, get_fallback_response

logger = setup_logger()

class ResponseGenerator:
    def __init__(self, long_memory=None):
        """مقداردهی اولیه ResponseGenerator با Gemini یا OpenAI"""
        self.backend = "gemini" if GEMINI_API_KEY else "openai"
        self.long_memory = long_memory

        if self.backend == "gemini":
            try:
                from google import genai
                self.client = genai.Client(api_key=GEMINI_API_KEY)
                self.model_name = GEMINI_MODEL
                logger.info(f"Gemini client is runnig - model: {self.model_name}")
                return
            except Exception as e:
                logger.warning(f"Gemini initialization failed, falling back to OpenAI: {e}")
                self.backend = "openai"

        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY یافت نشد")
            raise ValueError("OPENAI_API_KEY نیاز است")

        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=OPENAI_TIMEOUT)
        self.model_name = OPENAI_MODEL
        logger.info(f"OpenAI client is runnig - model: {self.model_name} - base_url: {OPENAI_BASE_URL}")
    
    def generate(self, user_text, user_data, short_memory_text, mood):
        """تولید پاسخ با شخصیت ناتسوکی"""
        
        # تشخیص زبان
        is_english = any(c.isascii() and c.isalpha() for c in user_text)
        
        # انتخاب پرامپت مناسب
        base_prompt = ENGLISH_PERSONALITY_PROMPT if is_english else PERSIAN_PERSONALITY_PROMPT
        
        # ساخت پرامپت نهایی
        system_prompt = self._build_system_prompt(
            base_prompt=base_prompt,
            user_data=user_data,
            mood=mood,
            is_english=is_english
        )
        
        # ساخت پیام کامل
        full_message = self._build_full_message(
            user_text=user_text,
            short_memory=short_memory_text,
            user_data=user_data
        )
        
        # تولید پاسخ
        response = safe_execute(
            self._call_agent,
            fallback_value=get_fallback_response(user_data.get("friendship_level", "Novice")),
            system_prompt=system_prompt,
            message=full_message
        )
        
        return self._clean_response(response)
    
    def _build_system_prompt(self, base_prompt, user_data, mood, is_english):
        """ساخت پرامپت سیستم"""
        level = user_data.get("friendship_level", "Novice")
        xp = user_data.get("xp", 0)
        emotional_guidance = (
            "First understand the user's intent and emotional subtext. Validate feelings when appropriate, "
            "show empathy for pain, and ask a gentle clarifying question when the meaning is unclear. "
            "Let the current mood affect word choice and intensity, but do not claim human experiences."
        )
        
        if is_english:
            prompt = (
                f"{base_prompt}\n\n"
                f"Friendship Level: {level} ({xp} XP), Current Mood: {mood}.\n"
                "Keep responses brief, tsundere style, reactive, with hidden affection.\n"
                f"{emotional_guidance} Return valid Telegram HTML only. Use custom emoji-id placeholders exactly like "
                "<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> when an emoji is useful."
            )
        else:
            prompt = (
                f"{base_prompt}\n\n"
                f"سطح دوستی: {level} ({xp} XP)، حالت فعلی: {mood}.\n"
                f"{emotional_guidance} کوتاه، تند، کمی پرخاش‌گر و با محبت پنهان جواب بده.\n"
                "فقط HTML معتبر Telegram برگردان. هرجا ایموجی لازم است از placeholder دقیق "
                "<tg-emoji emoji-id=\"5206357006864113601\">👋</tg-emoji> استفاده کن."
            )
        
        prompt += self._premium_emoji_prompt()

        # ویژگی سطح Tsundere
        if level in {"Tsundere", "Confidant", "Devoted Friend", "Soulmate", "Eternal Bond"}:
            if is_english:
                prompt += " This is a deeply bonded relationship. Natsuki is extremely loyal, protective, and loving while keeping her distinct personality."
            else:
                prompt += " این رابطه بسیار عمیق است؛ ناتسوکی در عین حفظ شخصیت خودش، بسیار وفادار، محافظ و مهربان باشد."
        
        return prompt

    def _premium_emoji_prompt(self):
        if self.long_memory is None:
            return ""
        emojis = self.long_memory.get_premium_emojis()
        emoji_list = "\n".join(
            f"{item['tag']} = {item['description']} (emoji_id: {item['emoji_id']})"
            for item in emojis
        ) or "(هیچ ایموجی‌ای تنظیم نشده است)"
        return (
            "\n\nاستفاده از لیست ایموجی‌ها:\n"
            "از کلیدهای متنی مشخص‌شده در لیست زیر برای علامت‌گذاری احساسات/واکنش‌ها "
            "در متن خروجی استفاده کن (مثلاً CONFIRM, LAUGHING, EMBARRASSED و ...).\n\n"
            f"لیست ایموجی:\n{emoji_list}\n\n"
            "قوانین:\n"
            "1. هنگام نیاز به نشان‌دادن احساس یا واکنش، به‌جای درج ایموجی یا توضیح احساس، "
            "کلید مربوطه را در متن قرار بده.\n"
            "2. فقط از کلیدهای داخل لیست استفاده کن.\n"
            "3. می‌توانی چند کلید را پشت سر هم یا چند بار در متن استفاده کنی."
        )
    
    def _build_full_message(self, user_text, short_memory, user_data):
        """ساخت پیام کامل برای ارسال به model"""
        import json
        
        return (
            f"User information: {json.dumps(user_data, ensure_ascii=False)}\n"
            f"Recent conversation:\n{short_memory}\n\n"
            f"User message: {user_text}\n"
            "Respond ONLY with your message, no explanations."
        )
    
    def _call_agent(self, system_prompt, message):
        """فراخوانی model Gemini یا OpenAI"""
        try:
            if self.backend == "gemini":
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"{system_prompt}\n\n{message}"
                )
                return getattr(response, "text", "...")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message.content if response and response.choices else "..."
        except Exception as e:
            logger.error(f"خطا در تولید پاسخ: {str(e)}")
            raise
    
    def _clean_response(self, response):
        """پاک‌سازی پاسخ"""
        cleaned = str(response).strip()
        cleaned = cleaned.replace('TERMINATE', '')
        cleaned = cleaned.replace('```', '')
        return self.replace_premium_emojis(cleaned)[:4000]

    def replace_premium_emojis(self, text):
        if self.long_memory is None:
            return str(text)
        result = str(text)
        for item in self.long_memory.get_premium_emojis():
            tag = re.escape(item["tag"])
            replacement = f'<tg-emoji emoji-id="{item["emoji_id"]}">😊</tg-emoji>'
            result = re.sub(
                rf"(?<![A-Za-z0-9_]){tag}(?![A-Za-z0-9_])",
                replacement,
                result,
            )
        return result
