from collections import defaultdict, deque
from config import SHORT_MEMORY_LIMIT

class ShortTermMemory:
    def __init__(self, limit=SHORT_MEMORY_LIMIT):
        self.limit = limit
        self.memory = defaultdict(lambda: deque(maxlen=limit))
    
    def add(self, user_id, message):
        """افزودن پیام به حافظه کوتاه‌مدت"""
        uid = str(user_id)
        self.memory[uid].append(message)
    
    def get(self, user_id, limit=None):
        """دریافت آخرین پیام‌های کاربر"""
        uid = str(user_id)
        messages = list(self.memory[uid])
        if limit:
            return messages[-limit:]
        return messages
    
    def clear(self, user_id=None):
        """پاک کردن حافظه"""
        if user_id:
            uid = str(user_id)
            if uid in self.memory:
                self.memory[uid].clear()
        else:
            self.memory.clear()
    
    def get_formatted(self, user_id, limit=5):
        """دریافت پیام‌ها به فرمت قابل استفاده"""
        messages = self.get(user_id, limit)
        return "\n".join([f"User: {msg}" for msg in messages])