import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from rbac import not_banned
from utils.security import can_proceed
from utils.ai_manager import get_ai_response

logger = logging.getLogger(__name__)

@not_banned
async def handle_ai_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for AI assistant requests."""
    logger.info(f"🤖 AI Request initiated by user {update.effective_user.id}")
    await update.effective_message.reply_text(
        "🧠 *اسألني أي شيء عن أمنك الرقمي!*\n\n"
        "أنا أمان، خبيرك الأمني المتاح على مدار الساعة.\n"
        "هل تشك في اختراق حسابك؟ أو تريد حماية الواي فاي؟ اكتب سؤالك الآن 👇",
        parse_mode="Markdown"
    )
    db.set_user_state(update.effective_user.id, "awaiting_ai")

async def answer_ai_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    """Processes the AI question and returns a response."""
    user_id = update.effective_user.id
    logger.info(f"📩 AI Question from {user_id}: {question[:50]}...")
    
    try:
        # التأكد من عدم تجاوز الحدود
        if not await can_proceed(update):
            logger.warning(f"🚫 AI Request denied by security for user {user_id}")
            return

        msg = await update.effective_message.reply_text("⏳ أحلل سؤالك بدقة لاستخراج أفضل نصيحة...")
        
        # جلب الرد
        try:
            response = await get_ai_response(question)
        except Exception as ai_err:
            logger.error(f"❌ Critical AI Manager Error: {ai_err}")
            response = "⚠️ عذراً، واجه محرك الذكاء الاصطناعي مشكلة فنية. جرب مجدداً لاحقاً."

        await msg.edit_text(response)
        db.log_scan(user_id, "🤖 AI", question[:100], "استشارة")
        logger.info(f"✅ AI Response delivered to {user_id}")
        
    except Exception as e:
        logger.error(f"❌ General AI Handler Error: {e}")
        await update.effective_message.reply_text("⚠️ حدث خطأ غير متوقع أثناء معالجة سؤالك.")
    finally:
        db.set_user_state(user_id, None)
