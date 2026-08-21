import random
from datetime import datetime, timedelta
from config import MOODS
from src.utils.logger import setup_logger

logger = setup_logger()

class MoodSystem:
    def __init__(self, long_memory):
        self.memory = long_memory
    
    def analyze_message_mood(self, text, user_id):
        """تحلیل خلق‌وخوی پیام کاربر"""
        text_lower = text.lower()
        uid = str(user_id)
        
        mood_indicators = {
            "affectionate": ["دوستت دارم", "love you", "عزیزم", "دلم برات تنگ شده"],
            "angry": ["احمق", "خنگ", "idiot", "stupid", "hate you"],
            "happy": ["خوشحالم", "مانگا", "manga", "کاپ‌کیک", "cupcake", "شعر", "happy"],
            "defensive": ["بچه", "کوتوله", "childish", "مسخره", "mock"],
            "empathetic": ["کمک", "درد", "سخت می‌گذره", "help", "hurt", "pain"],
            "concerned": ["نگران", "می‌ترسم", "نگرانم", "worried", "afraid"],
            "curious": ["چرا", "چطور", "why", "how", "what if"],
            "playful": ["شوخی", "بازی", "joke", "funny", "tease"],
            "sad": ["غمگین", "ناراحتم", "گریه", "sad", "cry", "depressed"],
            "lonely": ["تنها", "تنهایی", "lonely", "alone", "miss everyone"],
            "proud": ["موفق شدم", "انجامش دادم", "I did it", "proud"],
            "jealous": ["حسودی", "حسادت", "jealous"],
            "frustrated": ["اعصابم", "کلافه", "خسته شدم", "frustrated", "annoyed"],
            "calm": ["آرام", "ریلکس", "calm", "relaxed"],
            "excited": ["هیجان", "ذوق", "excited", "amazing", "can't wait"],
            "protective": ["مراقب", "حفاظت", "protect", "safe"],
            "embarrassed": ["خجالت", "شرمنده", "embarrassed", "blush"],
            "tender": ["مهربان", "لطیف", "دلگرمی", "gentle", "comfort"],
        }
        
        detected_moods = []
        for mood, keywords in mood_indicators.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_moods.append(mood.capitalize())
        
        if detected_moods:
            # ذخیره تأثیر پیام
            user_data = self.memory.get_user(user_id)
            if "mood_history" not in user_data:
                user_data["mood_history"] = []
            
            user_data["mood_history"].append({
                "mood": detected_moods[0],
                "detected_moods": detected_moods,
                "timestamp": datetime.now().isoformat(),
                "message_preview": text[:30]
            })
            
            # محدود کردن تاریخچه
            if len(user_data["mood_history"]) > 50:
                user_data["mood_history"] = user_data["mood_history"][-50:]
            
            self.memory.save()
            logger.info(f"User {uid} message mood: {detected_moods}")
        
        return detected_moods
    
    def determine_current_mood(self, user_id):
        """تعیین خلق‌وخوی فعلی"""
        user_data = self.memory.get_user(user_id)
        level = user_data.get("friendship_level", "Novice")
        
        # وزن‌های خلق‌وخو بر اساس سطح
        mood_weights = {
            "Novice": {"Shy": 20, "Defensive": 15, "Curious": 12, "Concerned": 8, "Calm": 10, "Happy": 10, "Embarrassed": 10, "Angry": 5, "Empathetic": 5, "Playful": 5},
            "Friendly": {"Happy": 18, "Empathetic": 15, "Curious": 12, "Playful": 10, "Affectionate": 10, "Concerned": 8, "Calm": 8, "Shy": 7, "Proud": 5, "Tender": 7},
            "Close Friend": {"Happy": 15, "Affectionate": 15, "Empathetic": 13, "Playful": 10, "Concerned": 8, "Curious": 8, "Flustered": 7, "Tender": 8, "Protective": 6, "Proud": 5, "Calm": 5},
            "Best Friend": {"Affectionate": 15, "Empathetic": 15, "Happy": 12, "Protective": 12, "Tender": 10, "Playful": 8, "Proud": 8, "Concerned": 7, "Excited": 6, "Flustered": 4, "Calm": 3},
            "Tsundere": {"Affectionate": 14, "Flustered": 13, "Defensive": 12, "Empathetic": 10, "Proud": 9, "Jealous": 8, "Protective": 8, "Happy": 8, "Embarrassed": 7, "Angry": 5, "Tender": 6},
            "Confidant": {"Affectionate": 15, "Empathetic": 15, "Protective": 12, "Tender": 11, "Concerned": 10, "Happy": 9, "Proud": 8, "Playful": 7, "Calm": 6, "Flustered": 4, "Jealous": 3},
            "Devoted Friend": {"Affectionate": 16, "Empathetic": 16, "Protective": 14, "Tender": 13, "Concerned": 10, "Happy": 9, "Proud": 7, "Playful": 6, "Calm": 5, "Flustered": 4},
            "Soulmate": {"Tender": 17, "Empathetic": 17, "Affectionate": 16, "Protective": 13, "Calm": 10, "Concerned": 9, "Happy": 7, "Proud": 5, "Playful": 4, "Flustered": 2},
            "Eternal Bond": {"Tender": 18, "Empathetic": 18, "Affectionate": 17, "Protective": 14, "Calm": 10, "Concerned": 8, "Happy": 7, "Proud": 5, "Playful": 3},
        }
        
        weights = mood_weights.get(level, mood_weights["Novice"])
        moods = list(weights.keys())
        probabilities = list(weights.values())
        
        chosen_mood = random.choices(moods, weights=probabilities, k=1)[0]
        
        # به‌روزرسانی حالت فعلی
        user_data["current_mood"] = chosen_mood
        user_data["last_mood_update"] = datetime.now().isoformat()
        self.memory.save()
        
        return chosen_mood

    def get_mood_details(self, user_id):
        user_data = self.memory.get_user(user_id)
        current_mood = user_data.get("current_mood") or self.determine_current_mood(user_id)
        history = user_data.get("mood_history") or []
        recent = history[-1] if history else {}
        return {
            "mood": current_mood,
            "recent_moods": recent.get("detected_moods") or ([recent["mood"]] if recent.get("mood") else []),
            "updated_at": user_data.get("last_mood_update") or recent.get("timestamp"),
        }