import time
import logging
from collections import defaultdict
from telegram import Update
import database as db

logger = logging.getLogger(__name__)

# Cache for rate limiting
_rate_limit_cache = defaultdict(list)

async def check_rate_limit(user_id: int) -> bool:
    """Check if user has exceeded 10 requests per minute."""
    now = time.time()
    _rate_limit_cache[user_id] = [t for t in _rate_limit_cache[user_id] if now - t < 60]
    return len(_rate_limit_cache[user_id]) < 10

def record_request(user_id: int):
    _rate_limit_cache[user_id].append(time.time())

async def can_proceed(update: Update) -> bool:
    """Gatekeeper for all scan and AI requests."""
    user = update.effective_user
    uid = user.id
    
    # 0. Admin Bypass
    from config import cfg
    if str(uid) == str(cfg.ADMIN_ID) or db.get_user_role(uid) == "admin":
        return True
    
    # 1. Rate Limiting
    if not await check_rate_limit(uid):
        await update.effective_message.reply_text("⏳ *مهلاً!* لقد تجاوزت الحد المسموح (10 طلبات في الدقيقة). يرجى الانتظار قليلاً.", parse_mode="Markdown")
        return False
    record_request(uid)

    # 2. Subscription/Daily Limit Check
    plan_info = db.get_user_plan(uid)
    plan_name = plan_info.get("plan", "free")
    
    # Magic numbers moved to constants/config if needed, but keeping here for now
    LIMITS = {"free": 5, "pro": 100, "enterprise": float('inf')}
    limit = LIMITS.get(plan_name, 5)
    
    count = db.get_daily_scans_count(uid)
    if count >= limit:
        await update.effective_message.reply_text(
            f"🚫 *عذراً! لقد وصلت للحد اليومي لباقتك.*\n\n"
            f"باقتك الحالية: `{plan_name}`\n"
            f"الرصيد المتاح: {limit} فحوصات/يوم.\n"
            f"استهلاكك اليوم: {count}.\n\n"
            f"🚀 للترقية والحصول على فحص غير محدود، استخدم `/upgrade`",
            parse_mode="Markdown"
        )
        return False
    return True
