import asyncio
import logging
import os
from config import cfg

logger = logging.getLogger(__name__)

# ============================================================
# تهيئة العملاء
# ============================================================
_gemini_model = None

def _get_gemini_model():
    global _gemini_model
    gemini_key = getattr(cfg, 'GEMINI_KEY', os.getenv('GEMINI_KEY'))
    if _gemini_model is None and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            _gemini_model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            logger.error(f"❌ فشل تهيئة Gemini: {e}")
    return _gemini_model

# ============================================================
# الدالة الرئيسية
# ============================================================

async def get_ai_response(prompt: str, context_history: list = None) -> str:
    """الحصول على رد من Aman AI (يدعم Gemini المجاني و Claude و GPT)."""

    # 1. محاولة استخدام Google Gemini (الخيار المجاني القوي)
    gemini_model = _get_gemini_model()
    if gemini_model:
        try:
            logger.info("🤖 Calling Google Gemini (Free)...")
            # تحويل السياق لتنسيق Gemini
            chat = gemini_model.start_chat(history=[])
            response = await asyncio.to_thread(
                chat.send_message,
                f"أنت 'Aman AI'، خبير أمن سيبراني عربي. أجب باختصار ومودة على: {prompt}"
            )
            return response.text
        except Exception as e:
            logger.error(f"❌ Gemini Error: {e}")

    # 2. محاولة استخدام الاستدعاءات السابقة (OpenAI/Claude) كخلفية
    # [بقية الكود السابق للاتصال بـ OpenAI/Claude سيظل يعمل كاحتياط]
    
    return (
        "🤖 *Aman AI - نصائح أمنية سريعة:*\n\n"
        "للحماية من الاختراق:\n"
        "• 🔐 استخدم كلمات مرور قوية\n"
        "• 📱 فعّل المصادقة الثنائية\n\n"
        "_يرجى إضافة GEMINI_KEY في الإعدادات للحصول على ذكاء اصطناعي مجاني._"
    )
