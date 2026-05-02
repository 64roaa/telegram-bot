import asyncio
import logging
from config import cfg

logger = logging.getLogger(__name__)

# ============================================================
# تهيئة عميل OpenAI (v1+ API)
# ============================================================
_client = None

def _get_client():
    """يُنشئ العميل مرة واحدة فقط (Singleton)."""
    global _client
    if _client is None:
        try:
            from openai import AsyncOpenAI
            _client = AsyncOpenAI(api_key=cfg.OPENAI_KEY)
        except Exception as e:
            logger.error(f"❌ فشل تهيئة OpenAI: {e}")
    return _client

# ============================================================
# الدالة الرئيسية
# ============================================================

async def get_ai_response(prompt: str, context_history: list = None) -> str:
    """الحصول على رد من Aman AI (GPT-4o-mini) مع إعادة المحاولة."""

    if not cfg.OPENAI_KEY:
        return (
            "🤖 *Aman AI - نصائح أمنية سريعة:*\n\n"
            "للحماية من الاختراق:\n"
            "• 🔐 استخدم كلمات مرور قوية مختلفة لكل حساب\n"
            "• 📱 فعّل المصادقة الثنائية (2FA)\n"
            "• 🔗 لا تضغط روابط مجهولة\n"
            "• 🛡️ حافظ على تحديث نظامك\n\n"
            "_للحصول على ردود مخصصة، يرجى إضافة مفتاح OpenAI._"
        )

    client = _get_client()
    if not client:
        return "❌ تعذر تشغيل محرك الذكاء الاصطناعي. جرب لاحقاً."

    # بناء سياق المحادثة
    messages = [
        {
            "role": "system",
            "content": (
                "أنت 'Aman AI'، خبير أمن سيبراني يتحدث العربية بأسلوب واضح وودود. "
                "تعمل لمنصة Amanteech الأمنية. "
                "أجاوبتك مختصرة ومباشرة مع نصائح عملية قابلة للتطبيق. "
                "استخدم الإيموجي بشكل مناسب لتسهيل القراءة."
            )
        }
    ]

    # إضافة سياق المحادثة السابق إن وُجد
    if context_history:
        for msg in context_history[-5:]:  # آخر 5 رسائل فقط
            messages.append({"role": msg.get("role", "user"), "content": msg.get("text", "")})

    messages.append({"role": "user", "content": prompt})

    # منطق إعادة المحاولة مع Exponential Backoff
    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=600,
                ),
                timeout=30.0
            )
            return response.choices[0].message.content

        except asyncio.TimeoutError:
            logger.warning(f"⚠️ AI Timeout - المحاولة {attempt + 1}/3")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s

        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower():
                logger.warning(f"⚠️ AI Rate Limit - المحاولة {attempt + 1}/3")
                if attempt < 2:
                    await asyncio.sleep(5)
            elif "api_key" in err_str.lower() or "authentication" in err_str.lower():
                logger.error("❌ مفتاح OpenAI غير صحيح")
                return "❌ مفتاح الذكاء الاصطناعي غير صحيح. راجعي الإعدادات."
            else:
                logger.error(f"❌ AI Error: {e}")
                break

    return (
        "⚠️ *محرك AI مشغول حالياً.*\n\n"
        "جرب إحدى هذه النصائح السريعة:\n"
        "• 🔐 استخدم كلمات مرور من 12+ حرف\n"
        "• 📱 فعّل 2FA على حساباتك\n"
        "• 🔗 افحص الروابط قبل النقر عليها\n\n"
        "_أو حاول مجدداً بعد دقيقة!_"
    )
