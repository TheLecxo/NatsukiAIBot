class SpecialFeatures:
    @staticmethod
    def get_features(level, user_data=None):
        """دریافت ویژگی‌های ویژه بر اساس سطح"""
        features = {
            "Novice": [
                "معرفی اولیه",
                "پرسیدن اسم",
                "صحبت درباره مانگا"
            ],
            "Friendly": [
                "توصیه مانگا",
                "دستور پخت ساده کاپ‌کیک",
                "نظر دادن درباره شعر"
            ],
            "Close Friend": [
                "اشتراک‌گذاری دستور پخت ویژه",
                "داستان‌های کوتاه از زندگی ناتسوکی",
                "توصیه شعرهای مورد علاقه"
            ],
            "Best Friend": [
                "رازهای ناتسوکی",
                "دستور پخت مخفی کاپ‌کیک",
                "اشتراک احساسات واقعی"
            ],
            "Tsundere": [
                "شعر خصوصی ناتسوکی",
                "دستور پخت اختصاصی",
                "قول‌های ویژه",
                "حمایت بی‌قید و شرط"
            ],
            "Confidant": [
                "گفت‌وگوهای عمیق و خصوصی",
                "شناختن احساسات پنهان کاربر",
                "توصیه‌ی شخصی ناتسوکی"
            ],
            "Devoted Friend": [
                "حمایت عاطفی ویژه",
                "خاطرات اختصاصی ناتسوکی",
                "نامه‌ی صمیمانه"
            ],
            "Soulmate": [
                "اعتماد کامل و گفت‌وگوی صادقانه",
                "شعر مخصوص رابطه",
                "همراهی در لحظه‌های سخت"
            ],
            "Eternal Bond": [
                "پیوند همیشگی ناتسوکی و کاربر",
                "قول مراقبت و همراهی",
                "راز نهایی ناتسوکی"
            ]
        }

        base_features = features.get(level, features["Novice"])
        
        # شخصی‌سازی برای کاربر خاص
        if user_data and "name" in user_data:
            name = user_data["name"]
            if level in {"Tsundere", "Confidant", "Devoted Friend", "Soulmate", "Eternal Bond"}:
                return [
                    f"شعر مخصوص {name}",
                    f"دستور پخت کاپ‌کیک {name}",
                    "راز بزرگ ناتسوکی",
                    "قول همیشه کنارت بودن"
                ]
        
        return base_features
    
    @staticmethod
    def unlock_feature(user_data, feature_name):
        """باز کردن قابلیت ویژه"""
        if "unlocked_features" not in user_data:
            user_data["unlocked_features"] = []
        
        if feature_name not in user_data["unlocked_features"]:
            user_data["unlocked_features"].append(feature_name)
            return True
        
        return False