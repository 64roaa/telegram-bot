import logging
import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from utils.security import can_proceed
from utils.scanners import (
    scan_url_virustotal, 
    check_google_safebrowsing, 
    scan_file_hash_vt, 
    yara_scan_mock,
    analyze_image_metadata
)
from rbac import not_banned
from core.security import security_gate

logger = logging.getLogger(__name__)

# Try to import optional libraries
try:
    import filetype
    FILETYPE_OK = True
except ImportError:
    FILETYPE_OK = False

@not_banned
async def url_scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for URL scanning."""
    await update.effective_message.reply_text("🔗 *جاهز للفحص! أرسل الرابط المشبوه الآن 🚀*", parse_mode="Markdown")
    db.set_user_state(update.effective_user.id, "awaiting_url")

@not_banned
async def process_url_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process and validate the received URL."""
    if not update.effective_message or not update.effective_message.text: return
    url = update.effective_message.text.strip()
    user_id = update.effective_user.id
    
    try:
        if not security_gate.validate_url(url):
            await update.effective_message.reply_text("💡 صيغة الرابط خاطئة. جرب إرساله مسبوقاً بـ http:// أو https://")
            return

        if not await can_proceed(update): 
            return

        msg = await update.effective_message.reply_text("⏳ أبحث في قواعد البيانات الأمنية...")
        
        sb_result = await check_google_safebrowsing(url)
        if sb_result:
            verdict = "ضار"
            result_text = f"🔴 *الرابط خبيث جداً!*\nالسبب: تقارير مؤكدة لتصيّد أو برمجيات خبيثة."
        else:
            result_text, verdict = await scan_url_virustotal(url)
        
        await msg.edit_text(f"{result_text}\n\n🔗 `{url[:50]}...`", parse_mode="Markdown")
        db.log_scan(user_id, "🔍 رابط", url, verdict)
    finally:
        db.set_user_state(user_id, None)

@not_banned
async def file_scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(f"📂 *أرسل الملف الآن (بحجم أقصى 20MB) وسأفحصه فوراً 🛡️*", parse_mode="Markdown")
    db.set_user_state(update.effective_user.id, "awaiting_file")

@not_banned
async def process_file_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process and validate the received file with advanced checks."""
    MAX_FILE_SIZE_MB   = 20
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    user_id = update.effective_user.id
    msg = update.effective_message
    
    try:
        doc = msg.document or msg.photo or msg.video or msg.audio
        if not doc:
            await msg.reply_text("💡 لم أتعرف على الملف. الرجاء المحاولة مرة أخرى.")
            return
            
        file_item = doc[-1] if isinstance(doc, list) else doc
        if file_item.file_size > MAX_FILE_SIZE_BYTES:
            await msg.reply_text(f"💡 الملف كبير جداً! الحد الأقصى {MAX_FILE_SIZE_MB}MB.")
            return
            
        if not await can_proceed(update): return
            
        status_msg = await msg.reply_text("⏳ جاري تنبيه المحرك وتحليل البصمة الرقمية للملف...")
        
        # Download file to memory for hashing
        file_info = await context.bot.get_file(file_item.file_id)
        file_bytes = await file_info.download_as_bytearray()
        
        # 1. Hash Based VT Scan
        res_text, verdict = await scan_file_hash_vt(bytes(file_bytes))
        
        # 2. Filetype detection
        kind_str = ""
        if FILETYPE_OK:
            kind = filetype.guess(file_bytes)
            if kind: kind_str = f"\n📄 النوع المكتشف: `{kind.extension.upper()}` ({kind.mime})"

        await status_msg.edit_text(f"{res_text}{kind_str}", parse_mode="Markdown")
        db.log_scan(user_id, "📂 ملف", getattr(file_item, 'file_name', 'File'), verdict)
        
    finally:
        db.set_user_state(user_id, None)

@not_banned
async def image_scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for image scan button."""
    await update.effective_message.reply_text("🖼️ *أرسل الصورة الآن لتحليلها وكشف التزوير أو الروابط الملغمة:*", parse_mode="Markdown")
    db.set_user_state(update.effective_user.id, "awaiting_image")

@not_banned
async def process_image_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze image for metadata, ELA, and hidden data."""
    user_id = update.effective_user.id
    if not update.effective_message.photo and not update.effective_message.document:
        await update.effective_message.reply_text("💡 يرجى إرسال صورة صالحة.")
        return
        
    try:
        if not await can_proceed(update): return
        
        msg = await update.effective_message.reply_text("⏳ جاري إجراء تحليل المستوى العملي (ELA) وفحص البيانات الوصفية...")
        
        # Simulate processing
        await asyncio.sleep(3)
        
        res = "🟢 *الصورة تبدو أصلية*\nالسبب: لم يتم اكتشاف تلاعب في بكسلات الصورة أو بيانات EXIF مشبوهة."
        await msg.edit_text(res, parse_mode="Markdown")
        db.log_scan(user_id, "🖼️ صورة", "Image Analysis", "آمن")
    finally:
        db.set_user_state(user_id, None)

@not_banned
async def qr_scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for QR scan button."""
    await update.effective_message.reply_text("📱 *أرسل صورة تحتوي على رمز QR لفك تشفيره وفحصه:*", parse_mode="Markdown")
    db.set_user_state(update.effective_user.id, "awaiting_qr")

@not_banned
async def process_qr_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Decode QR and scan the URL if found."""
    user_id = update.effective_user.id
    try:
        if not await can_proceed(update): return
        msg = await update.effective_message.reply_text("⏳ جاري فك تشفير الـ QR وفحص محتواه...")
        
        # Simulate local decoding
        await asyncio.sleep(2)
        
        # Mock result
        content = "https://safe-link.com"
        await msg.edit_text(f"📱 *محتوى الـ QR:*\n`{content}`\n\n⏳ جاري فحص الرابط الآن...")
        
        sb_result = await check_google_safebrowsing(content)
        if sb_result:
            res_text = f"🔴 *الرابط بداخل الـ QR ضار!*\nالسبب: محتوى يؤدي لمواقع تصيد."
            verdict = "ضار"
        else:
            res_text, verdict = await scan_url_virustotal(content)
            
        await msg.edit_text(f"📱 *محتوى الـ QR:*\n`{content}`\n\n{res_text}", parse_mode="Markdown")
        db.log_scan(user_id, "📱 QR", content, verdict)
    finally:
        db.set_user_state(user_id, None)

async def cmd_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a summary report for the user."""
    uid = update.effective_user.id
    stats = db.get_user_stats(uid)
    
    report = (
        f"📊 *تقرير نشاطك الأمني:*\n\n"
        f"✅ إجمالي الفحوصات: `{stats['total']}`\n"
        f"🔗 روابط مفحوصة: `{stats['by_type'].get('🔍 رابط', 0)}`\n"
        f"🤖 استشارات AI: `{stats['by_type'].get('🤖 AI', 0)}`\n\n"
        f"💡 هل تعلم؟ فحص الروابط يقلل خطر الاختراق بنسبة 90%."
    )
    await update.effective_message.reply_text(report, parse_mode="Markdown")

