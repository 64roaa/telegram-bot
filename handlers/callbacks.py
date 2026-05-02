from telegram import Update
from telegram.ext import ContextTypes
import database as db
from keyboards.main import get_notifications_keyboard

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # Reset state on any button click to avoid state-traps
    db.set_user_state(user_id, None)
    
    # Main menu routes
    from handlers.scans import url_scan_handler, file_scan_handler, image_scan_handler, qr_scan_handler, cmd_reports
    from handlers.ai import handle_ai_request
    from handlers.common import help_handler
    
    if data == "btn_scan_url":
        await url_scan_handler(update, context)
    elif data == "btn_scan_file":
        await file_scan_handler(update, context)
    elif data == "btn_scan_img":
        await image_scan_handler(update, context)
    elif data == "btn_scan_qr":
        await qr_scan_handler(update, context)
    elif data == "btn_ask_ai":
        await handle_ai_request(update, context)
    elif data == "btn_reports":
        await cmd_reports(update, context)
    elif data == "btn_honeypot":
        await query.message.reply_text(
            "🍯 *درع حماية المجموعات (Honeypot)*\n\n"
            "هذه الميزة تعمل تلقائياً عند إضافة البوت إلى المجموعات بصلاحيات المشرف.\n"
            "سيقوم البوت برصد أي محادثات تحتوي على روابط خبيثة وحظر المرسل فوراً لحماية أعضاء المجموعة.",
            parse_mode="Markdown"
        )
    elif data == "btn_help":
        await help_handler(update, context)
    elif data == "btn_notifications":
        await show_notifications_settings(update, context)
    elif data == "notif_on":
        db.set_subscription(user_id, True)
        await query.message.edit_text("✅ *تم تفعيل التنبيهات بنجاح.*", parse_mode="Markdown")
    elif data == "notif_off":
        db.set_subscription(user_id, False)
        await query.message.edit_text("🔕 *تم إيقاف التنبيهات.*", parse_mode="Markdown")
    elif data == "show_sources":
        await query.message.reply_text("📡 مصادرنا الرسمية تشمل: CERT-SA و NCA.")

    # Admin Handlers
    elif data.startswith("admin_"):
        from handlers.admin import cmd_admin, cmd_hp_stats
        if data == "admin_stats":
            await cmd_admin(update, context)
        elif data == "admin_honeypot":
            await cmd_hp_stats(update, context)
        elif data == "admin_revenue":
            await cmd_admin(update, context)

async def show_notifications_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the notifications settings keyboard from a message or button click."""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    is_sub = user_data.get("subscribed", 0) == 1 if user_data else False
    
    await update.effective_message.reply_text(
        "📡 *إدارة التنبيهات الأمنية*\n\n"
        "يمكنك تفعيل الحصول على تنبيهات فورية عند صدور تحذيرات من CERT-SA و NCA.",
        parse_mode="Markdown",
        reply_markup=get_notifications_keyboard(is_sub)
    )
