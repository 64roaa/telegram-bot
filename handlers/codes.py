import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from rbac import not_banned, admin_only
import random
import string

logger = logging.getLogger(__name__)

@not_banned
async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استخدام كود تفعيل."""
    if not context.args:
        await update.effective_message.reply_text("❌ يرجى إدخال الكود بعد الأمر. مثال: `/redeem ABC-123`", parse_mode="Markdown")
        return
    
    code_text = context.args[0].strip().upper()
    result = db.redeem_code(update.effective_user.id, code_text)
    await update.effective_message.reply_text(result["msg"])

@admin_only
async def gen_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توليد كود جديد للمشرفين."""
    if len(context.args) < 2:
        return await update.message.reply_text("💡 الاستخدام: `/gen_code [أيام] [عدد_الاستخدامات]`")
    
    try:
        days = int(context.args[0])
        uses = int(context.args[1])
        code = "AMAN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        db.add_code(code, days, uses)
        await update.message.reply_text(
            f"🎫 *كود تفعيل جديد:*\n`{code}`\n\n"
            f"📅 المدة: `{days}` يوم\n"
            f"👥 الاستخدامات: `{uses}`", 
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ خطأ: يرجى إدخال أرقام صحيحة للأيام وعدد الاستخدامات.")
    except Exception as e:
        logger.error(f"Gen Code Error: {e}")
        await update.message.reply_text("❌ حدث خطأ داخلي أثناء توليد الكود.")
