import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from rbac import admin_only

logger = logging.getLogger(__name__)

@admin_only
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with db.get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        pro_users = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE plan='pro'").fetchone()[0]
        total_codes = conn.execute("SELECT COUNT(*) FROM codes").fetchone()[0]
        used_codes = conn.execute("SELECT SUM(used_count) FROM codes").fetchone()[0] or 0

    report = (
        f"👑 *لوحة تحكم المشرف*\n\n"
        f"👥 المستخدمون: `{total_users}`\n"
        f"🔍 الفحوصات: `{total_scans}`\n"
        f"💎 المشتركون Pro: `{pro_users}`\n"
        f"🎟️ الأكواد: `{total_codes}` (مستخدمة: `{used_codes}`)\n"
    )
    from keyboards.main import get_admin_keyboard
    await update.effective_message.reply_text(report, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@admin_only
async def admin_panel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from keyboards.main import get_admin_reply_keyboard
    await update.effective_message.reply_text("🎮 لوحة التحكم التفاعلية:", reply_markup=get_admin_reply_keyboard())

@admin_only
async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 عرض المشتركين":
        with db.get_connection() as conn:
            pro = conn.execute("SELECT user_id, first_name FROM subscriptions WHERE plan='pro'").fetchall()
        report = "💎 *مشتركو Pro:*\n" + ("\n".join([f"• `{u[0]}` ({u[1]})" for u in pro]) or "لا يوجد")
        await update.message.reply_text(report, parse_mode="Markdown")
    elif text == "➕ إضافة اشتراك":
        await update.message.reply_text("👤 أرسل ID المستخدم لإضافته لـ Pro:")
        context.user_data["admin_action"] = "add_pro"
    elif text == "🔙 العودة للقائمة الرئيسية":
        from keyboards.main import get_main_keyboard
        from telegram import ReplyKeyboardRemove
        await update.message.reply_text("🔙 عودة...", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("📋 القائمة:", reply_markup=get_main_keyboard())

async def process_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.pop("admin_action", None)
    if action == "add_pro":
        try:
            target_id = int(update.message.text)
            db.update_subscription(target_id, "pro")
            await update.message.reply_text(f"✅ تم تفعيل Pro لـ `{target_id}`")
        except: await update.message.reply_text("❌ ID غير صالح")

@admin_only
async def cmd_hp_stats(update, context): await update.message.reply_text("🍯 Honeypot Stats: OK")
@admin_only
async def cmd_hp_recent(update, context): await update.message.reply_text("📋 Honeypot Recent: None")
