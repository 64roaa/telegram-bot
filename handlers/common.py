from telegram import Update
from telegram.ext import ContextTypes
import database as db
from keyboards.main import get_main_keyboard
from rbac import not_banned

@not_banned
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    db.upsert_user(user.id, user.username, user.first_name)
    
    # Referral
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.split("_")[1])
                res = db.add_referral(user.id, referrer_id)
                if res:
                    try:
                        if res == "REWARD":
                            await context.bot.send_message(
                                referrer_id,
                                "🏆 *تهانينا! لقد وصلت للهدف!* 🏆\n\n"
                                "لقد نجحت في دعوة 5 مستخدمين، وتم منحك *أسبوع مجاني وبشكل تلقائي* في باقة Pro! شكراً لمساعدتنا في نشر الأمان. 🛡️✨",
                                parse_mode="Markdown"
                            )
                        else:
                            await context.bot.send_message(referrer_id, "🎁 انضم مستخدم جديد عن طريقك!")
                    except: pass
            except: pass

    from config import cfg
    is_owner = str(user.id) == str(cfg.ADMIN_ID)
    
    welcome_text = (
        f"🛡️ *مرحباً {user.first_name} 💞 💞 في Amanteech Bot!* 🛡️\n\n"
        "أنتِ المطورة 👑 عندك كل الصلاحيات\n\n" if is_owner else ""
    ) + (
        "هل أنت قلق من الروابط المشبوهة؟\nنحن هنا لحمايتك! 🚀\n\n"
        "✨ *ماذا نقدم لك؟*\n• 🔗 فحص الروابط والملفات\n• 🖼️ تحليل الصور و QR\n• 🤖 استشارات Aman AI\n\n"
        "👇 اختر من القائمة للبدء:"
    )
    from telegram import ReplyKeyboardRemove
    await update.effective_message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@not_banned
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = "🛡️ *دليل الاستخدام*\n\nأرسل رابطاً أو ملفاً وسنقوم بفحصه فوراً.\nاستخدم /menu للوصول للخدمات."
    await update.effective_message.reply_text(help_text, parse_mode="Markdown")

@not_banned
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("📋 قائمة الخدمات:", reply_markup=get_main_keyboard())

@not_banned
async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start=ref_{user.id}"
    count = db.get_ref_stats(user.id)
    
    # حساب الإحالات المتبقية للمكافأة القادمة
    next_reward = 5 - (count % 5)
    
    msg = (
        f"🎁 *برنامج المكافآت الأمني:*\n\n"
        f"قم بدعوة أصدقائك واحصل على اشتراك Pro مجاني!\n"
        f"كل 5 إحالات = *أسبوع Pro مجاني* 💎\n\n"
        f"🔗 *رابط الإحالة الخاص بك:*\n`{link}`\n\n"
        f"📊 *إحصائياتك:*\n"
        f"• عدد الإحالات الحالية: `{count}`\n"
        f"• متبقي لك `{next_reward}` إحصائيات للحصول على المكافأة القادمة! ✨"
    )
    await update.effective_message.reply_text(msg, parse_mode="Markdown")
