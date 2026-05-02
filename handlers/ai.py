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
    
    try:
        if not await can_proceed(update):
            return

        msg = await update.effective_message.reply_text("⏳ أحلل سؤالك بدقة لاستخراج أفضل نصيحة...")
        
        response = await get_ai_response(question)
        
        await msg.edit_text(response, parse_mode="Markdown")
        db.log_scan(user_id, "🤖 AI", question[:100], "استشارة")
    finally:
        db.set_user_state(user_id, None)
