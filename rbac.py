import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

ROLE_HIERARCHY = {"banned": 0, "free": 1, "pro": 2, "admin": 3}
ROLE_LABELS = {"admin": "👑 Admin", "pro": "💎 Pro", "free": "👤 Free", "banned": "🚫 Banned"}

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user: return
        
        from config import cfg
        # المطورة تتجاوز كل شيء
        if str(user.id) == str(cfg.ADMIN_ID):
            return await func(update, context)
            
        role = db.get_user_role(user.id)
        if role != "admin":
            logger.warning(f"RBAC [admin_only] DENIED: {user.id} ({user.username})")
            return
        return await func(update, context)
    return wrapper

def not_banned(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user: return
        
        from config import cfg
        # المطورة تتجاوز الحظر
        if str(user.id) == str(cfg.ADMIN_ID):
            return await func(update, context)
            
        if db.is_banned(user.id):
            if update.effective_message:
                await update.effective_message.reply_text("🚫 *تم حظرك من استخدام هذا البوت.*", parse_mode="Markdown")
            return
        return await func(update, context)
    return wrapper

def minimum_role(min_role: str):
    min_level = ROLE_HIERARCHY.get(min_role, 1)
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user: return
            
            from config import cfg
            # المطورة لها وصول كامل وحر
            if str(user.id) == str(cfg.ADMIN_ID):
                return await func(update, context)
                
            role = db.get_user_role(user.id)
            level = ROLE_HIERARCHY.get(role, 0)
            if level < min_level:
                if update.effective_message:
                    await update.effective_message.reply_text("🔒 هذه الميزة تتطلب اشتراكاً أعلى.", parse_mode="Markdown")
                return
            return await func(update, context)
        return wrapper
    return decorator
