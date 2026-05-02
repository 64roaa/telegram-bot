import logging
import functools
import traceback
import sys
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("Amanteech.Core.Exceptions")

class AmanteechError(Exception):
    """Base category for all bot errors."""
    pass

class RateLimitError(AmanteechError): pass
class PermissionDeniedError(AmanteechError): pass
class ExternalAPIError(AmanteechError): pass

def safe_handler(func):
    """Decorator to wrap handlers in a global safety net."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            # We explicitly only pass update and context unless func expects more
            return await func(update, context, *args, **kwargs)
        except RateLimitError:
            if update.effective_message:
                await update.effective_message.reply_text("🛑 مهلاً! لقد تجاوزت حد الطلبات المسموح به. حاول لاحقاً.")
        except PermissionDeniedError:
            if update.effective_message:
                await update.effective_message.reply_text("🚫 عذراً، ليس لديك الصلاحية لاستخدام هذه الميزة.")
        except Exception as e:
            # Full logging to terminal for debugging
            err_msg = f"🚨 CRITICAL ERROR in {func.__name__}: {str(e)}"
            logger.error(err_msg)
            traceback.print_exc(file=sys.stdout)
            
            # User feedback
            if update.effective_chat and update.effective_chat.type == "private":
                if update.effective_message:
                    try:
                        await update.effective_message.reply_text("⚠️ حدث خطأ تقني داخلي. تم إرسال بلاغ للمطورين.")
                    except: pass
    return wrapper
