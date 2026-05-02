import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Returns the main menu as an Inline Keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 فحص رابط", callback_data="btn_scan_url"),
         InlineKeyboardButton("📄 فحص ملف", callback_data="btn_scan_file")],
        [InlineKeyboardButton("📱 فحص QR Code", callback_data="btn_scan_qr"),
         InlineKeyboardButton("🖼️ فحص صورة", callback_data="btn_scan_img")],
        [InlineKeyboardButton("🤖 محرك AI", callback_data="btn_ask_ai"),
         InlineKeyboardButton("📊 نظام التقارير", callback_data="btn_reports")],
        [InlineKeyboardButton("🚨 نظام الإشعارات", callback_data="btn_notifications"),
         InlineKeyboardButton("🍯 درع المجموعات", callback_data="btn_honeypot")],
        [InlineKeyboardButton("ℹ️ المساعدة", callback_data="btn_help")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data="admin_stats")],
        [InlineKeyboardButton("🍯 وضع Honeypot", callback_data="admin_honeypot")],
        [InlineKeyboardButton("💰 تقرير الأرباح", callback_data="admin_revenue")],
    ])

def get_admin_reply_keyboard():
    from telegram import ReplyKeyboardMarkup
    return ReplyKeyboardMarkup([
        ["📊 عرض المشتركين"],
        ["➕ إضافة اشتراك", "➖ حذف اشتراك"],
        ["🔙 العودة للقائمة الرئيسية"]
    ], resize_keyboard=True)

def get_notifications_keyboard(is_subscribed: bool):
    text = "🔕 إيقاف التنبيهات" if is_subscribed else "🔔 تفعيل التنبيهات"
    data = "notif_off" if is_subscribed else "notif_on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data)],
        [InlineKeyboardButton("📡 عرض المصادر", callback_data="show_sources")]
    ])
