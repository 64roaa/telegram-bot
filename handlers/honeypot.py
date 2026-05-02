import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from rbac import not_banned
from config import cfg

logger = logging.getLogger(__name__)

@not_banned
async def trap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle trap commands (/secret, /admin_panel, etc.)
    Anyone using these who isn't already an admin gets their risk score bumped 
    and potentially banned.
    """
    user = update.effective_user
    if not user: return
    
    # Ignore if real admin
    if str(user.id) == str(cfg.ADMIN_ID):
        await update.effective_message.reply_text("👑 أهلاً بك يا سيدي المشرف. هذه الدالة مخصصة لاصطياد المتسللين.")
        return

    # Trigger honeypot log
    logger.warning(f"🍯 Honeypot TRAP TRIGGERED by user {user.id} ({user.username}) via command {update.message.text}")
    
    # Increase risk score logic or direct ban
    # For SaaS-level strictness, anyone trying to access admin panel via guessing is a major risk.
    db.log_scan(user.id, "🍯 Honeypot", f"TRAP: {update.message.text}", "ضار")
    
    # In a real SaaS, we might ban them immediately or put them on a watchdog list.
    # Let's set their role to 'banned' if they hit a trap.
    db.set_user_role(user.id, "banned")
    
    await update.effective_message.reply_text(
        "🚫 *لقد تم اكتشاف محاولة وصول غير مصرح بها.*\n"
        "تم تسجيل هويتك وعملك وحظر حسابك تلقائياً لدواعي أمنية.",
        parse_mode="Markdown"
    )
    
    # Notify admin
    if cfg.ADMIN_ID:
        await context.bot.send_message(
            cfg.ADMIN_ID,
            f"🚨 *Honeypot Trap Alert*\n"
            f"👤 المستخدم: {user.full_name} (`{user.id}`)\n"
            f"🛠️ الأمر المستخدم: `{update.message.text}`\n"
            f"⚡ الإجراء: `تم الحظر بنجاح`",
            parse_mode="Markdown"
        )
