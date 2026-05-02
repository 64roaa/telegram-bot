import logging
import os
import stripe
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from rbac import not_banned
from config import cfg

logger = logging.getLogger(__name__)

# Initialize Stripe from config
stripe.api_key = cfg.STRIPE_SECRET_KEY if hasattr(cfg, 'STRIPE_SECRET_KEY') else os.getenv("STRIPE_SECRET_KEY")

@not_banned
async def cmd_myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض خطة المستخدم الحالية."""
    user = update.effective_user
    plan_info = db.get_user_plan(user.id)
    plan_name = plan_info.get("plan", "free")
    
    # limits mapping
    limits = {"free": 5, "pro": 100, "enterprise": float('inf')}
    limit_val = limits.get(plan_name, 5)
    limit_str = str(limit_val) if limit_val != float('inf') else "غير محدود"
    
    count = db.get_daily_scans_count(user.id)
    
    await update.effective_message.reply_text(
        f"💳 *خطتك الحالية:*\n\n"
        f"الباقة: `{plan_name.upper()}`\n"
        f"الفحوصات المستهلكة اليوم: `{count}` من أصل `{limit_str}`\n\n"
        f"🚀 للترقية والحصول على حدود أعلى، استخدم /upgrade",
        parse_mode="Markdown"
    )

@not_banned
async def cmd_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ينشئ رابط دفع للمستخدم عبر Stripe."""
    user = update.effective_user
    if not stripe.api_key:
        await update.effective_message.reply_text("💡 خدمة الترقية تتحدث حالياً. نرجو المحاولة لاحقاً.")
        return
        
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Amanteech Pro Plan',
                        'description': 'فحص غير محدود وحماية متقدمة',
                    },
                    'unit_amount': 999,  # $9.99
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://t.me/AmanteechBot?start=success',
            cancel_url='https://t.me/AmanteechBot?start=cancel',
            client_reference_id=str(user.id)
        )
        
        await update.effective_message.reply_text(
            f"🚀 *استثمر في حمايتك الآن!*\n\n"
            f"💰 باقة المحترفين: `$9.99` شهرياً\n"
            f"✨ الفوائد: فحص كل روابطك يومياً بلا توقف، وتصفح الإنترنت بأمان تام لك ولعائلتك!\n\n"
            f"🔗 [اضغط لترقية درعك فوراً]({session.url})",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Stripe setup error: {e}")
        await update.effective_message.reply_text("⚠️ عذراً، واجهنا مشكلة في إنشاء رابط الدفع.")
@not_banned
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خيار الشراء اليدوي (STC Pay)."""
    await update.effective_message.reply_text(
        "💳 *للاشتراك عبر تحويل STC Pay:*\n\n"
        "📍 الرقم: `0500000000`\n"
        "💰 المبلغ: `40 ريال` (باقة شهرية)\n\n"
        "📸 *بعد التحويل:* يرجى إرسال صورة إيصال التحويل هنا في المحادثة مباشرة.\n"
        "سيقوم فريق الدعم بمراجعة طلبك وإعطائك كود التفعيل فوراً! 🚀",
        parse_mode="Markdown"
    )
    db.set_user_state(update.effective_user.id, "awaiting_payment_proof")

# Removed cmd_redeem (moved to handlers/codes.py)

async def process_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام لقطة شاشة التحويل وإبلاغ المشرف."""
    user = update.effective_user
    await update.effective_message.reply_text("✅ تم استلام صورة التحويل! جاري مراجعتها من قبل الإدارة وسوف نخطرك فور التفعيل. شكراً لثقتك! 🙏")
    db.set_user_state(user.id, None)
    
    # Notify Admin
    if cfg.ADMIN_ID:
        try:
            await context.bot.send_message(
                cfg.ADMIN_ID,
                f"💰 *طلب اشتراك جديد (تحويل يدوي):*\n\n"
                f"👤 المستخدم: {user.full_name} (`{user.id}`)\n"
                f"👇 صورة الإيصال بالأسفل:",
                parse_mode="Markdown"
            )
            # Send the photo too
            if update.message.photo:
                await context.bot.send_photo(cfg.ADMIN_ID, update.message.photo[-1].file_id)
            elif update.message.document:
                await context.bot.send_document(cfg.ADMIN_ID, update.message.document.file_id)
        except Exception as e:
            logger.error(f"Admin Notify Error: {e}")
