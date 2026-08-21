from config import LEVELS
from src.utils.logger import setup_logger

logger = setup_logger()

class XPSystem:
    def __init__(self, long_memory):
        self.memory = long_memory
        self.levels = LEVELS
    
    def get_level_name(self, xp):
        """دریافت نام سطح بر اساس XP"""
        name = "Novice"
        for threshold, level_name in self.levels:
            if xp >= threshold:
                name = level_name
            else:
                break
        return name
    
    def add_xp(self, user_id, amount=1):
        """افزایش XP کاربر"""
        uid = str(user_id)
        user_data = self.memory.get_user(user_id)
        
        old_xp = user_data.get("xp", 0)
        user_data["xp"] = old_xp + amount
        
        old_level = user_data.get("friendship_level", "Novice")
        new_level = self.get_level_name(user_data["xp"])
        user_data["friendship_level"] = new_level
        
        # لاگ ارتقاء سطح
        if old_level != new_level:
            logger.info(f"User {uid} leveled up: {old_level} -> {new_level} ({user_data['xp']} XP)")
        
        self.memory.save()
        return user_data
    
    def get_user_stats(self, user_id):
        """دریافت آمار کاربر"""
        user_data = self.memory.get_user(user_id)
        return {
            "xp": user_data.get("xp", 0),
            "level": user_data.get("friendship_level", "Novice"),
            "interactions": user_data.get("interaction_count", 0),
            "name": user_data.get("name", "Unknown")
        }