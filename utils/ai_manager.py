import asyncio
import logging
from config import cfg

logger = logging.getLogger(__name__)

# ============================================================
# تهيئة العملاء (OpenAI & Anthropic)
# ============================================================
_openai_client = None
_claude_client = None

def _get_openai_client():
    global _openai_client
    if _openai_client is None and getattr(cfg, 'OPENAI_KEY', None):
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=cfg.OPENAI_KEY)
        except Exception as e:
            logger.error(f"❌ فشل تهيئة OpenAI: {e}")
    return _openai_client

def _get_claude_client():
    global _claude_client
    # نبحث عن CLAUDE_KEY في الإعدادات أو البيئة
    import os
    claude_key = getattr(cfg, 'CLAUDE_KEY', os.getenv('CLAUDE_KEY'))
    if _claude_client is None and claude_key:
        try:
            from anthropic import AsyncAnthropic
            _claude_client = AsyncAnthropic(api_key=claude_key)
        except Exception as e:
            logger.error(f"❌ فشل تهيئة Claude: {e}")
    return _claude_client

# ============================================================
# الدالة الرئيسية
# ============================================================

async def get_ai_response(prompt: str, context_history: list = None) -> str:
    """الحصول على رد من Aman AI (يدعم Claude و GPT)."""

    # 1. محاولة استخدام Claude أولاً (إذا توفر المفتاح)
    claude_client = _get_claude_client()
    if claude_client:
        try:
            logger.info("🤖 Calling Claude AI...")
            response = await asyncio.wait_for(
                claude_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=600,
                    system="أنت 'Aman AI'، خبير أمن سيبراني يتحدث العربية بأسلوب واضح وودود. أجب باختصار مع نصائح عملية.",
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=30.0
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"❌ Claude Error: {e}")

    # 2. المحاولة مع OpenAI كخيار ثاني
    openai_client = _get_openai_client()
    if openai_client:
        try:
            logger.info("🤖 Calling OpenAI...")
            messages = [{"role": "system", "content": "أنت خبير أمن سيبراني عربي ودود."}]
            messages.append({"role": "user", "content": prompt})
            
            response = await asyncio.wait_for(
                openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=600,
                ),
                timeout=30.0
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ OpenAI Error: {e}")

    # 3. خطة الطوارئ (Fallback) إذا لم تتوفر مفاتيح أو فشلت
    return (
        "🤖 *Aman AI - نصائح أمنية سريعة:*\n\n"
        "للحماية من الاختراق:\n"
        "• 🔐 استخدم كلمات مرور قوية ومختلفة\n"
        "• 📱 فعّل المصادقة الثنائية (2FA)\n"
        "• 🔗 لا تضغط روابط مجهولة\n\n"
        "_يرجى التأكد من إضافة رصيد لمفتاح الذكاء الاصطناعي._"
    )
