"""
Google Gemini Client
مدیریت ارتباط با Google AI Studio (Gemini)
"""

from config import GEMINI_CONFIG
from src.utils.logger import setup_logger

logger = setup_logger()


class GeminiClient:
    """کلاس برای مدیریت اتصال به Google Gemini"""
    
    def __init__(self):
        """مقداردهی اولیه کلاینت Gemini"""
        self.config = GEMINI_CONFIG
        self.model = self.config["model"]
        self.api_key = self.config["api_key"]
        
        if not self.api_key:
            logger.error("GEMINI_API_KEY یافت نشد در متغیرهای محیطی")
            raise ValueError("GEMINI_API_KEY نیاز است. از https://aistudio.google.com/app/apikey دریافت کنید")
        
        logger.info(f"Gemini Client is runnig - model: {self.model}")
    
    def validate_api_key(self):
        """تایید صحت API Key"""
        if not self.api_key or len(self.api_key) < 10:
            logger.error("API Key نامعتبر است")
            return False
        
        logger.info("API Key معتبر است")
        return True
    
    def get_config(self):
        """بازگرداندن کانفیگ Gemini"""
        return self.config
