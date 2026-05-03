import logging
import os
import asyncio
import feedparser
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import Forbidden, BadRequest, ChatMigrated, TimedOut
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ============================================================================
# ⚙️ الثوابت العامة (Constants)
# ============================================================================
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60
MEMORY_MAX_MESSAGES = 10
VT_MALICIOUS_THRESHOLD = 5
BROADCAST_INTERVAL_HOURS = 1

# Core & Utils
from config import cfg
import database as db
from utils.security import can_proceed
from utils.honeypot import monitor_group
from rbac import admin_only, not_banned

# Handlers
from handlers.common import start_handler, help_handler, menu_handler, cmd_referral
from handlers.scans import url_scan_handler, process_url_scan, file_scan_handler, cmd_reports
from handlers.ai import handle_ai_request, answer_ai_question
from handlers.callbacks import callback_router
from handlers.subscriptions import cmd_myplan, cmd_upgrade, cmd_buy, process_payment_proof
from handlers.codes import cmd_redeem, gen_code
from handlers.admin import cmd_admin, cmd_hp_stats, cmd_hp_recent, admin_panel_reply, handle_admin_buttons, process_admin_input
from handlers.honeypot import trap_handler

# ============================================================================
# 🔧 LOGGING CONFIGURATION
# ============================================================================

from utils.logger import setup_structured_logging
setup_structured_logging()
logger = logging.getLogger(__name__)

# ============================================================================
# 🛡️ RATE LIMITER
# ============================================================================

class RateLimiter:
    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, time_window: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
    
    def is_allowed(self, user_id: int) -> bool:
        now = datetime.now()
        if user_id not in self.requests:
            self.requests[user_id] = []
        self.requests[user_id] = [r for r in self.requests[user_id] if (now - r).seconds < self.time_window]
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        self.requests[user_id].append(now)
        return True

# ============================================================================
# 💭 CONVERSATION MEMORY
# ============================================================================

class ConversationMemory:
    def __init__(self, max_messages: int = MEMORY_MAX_MESSAGES):
        self.memory = {}
        self.max_messages = max_messages
    
    def add(self, user_id: int, message: str, role: str = "user"):
        if user_id not in self.memory:
            self.memory[user_id] = []
        self.memory[user_id].append({"text": message, "role": role, "timestamp": datetime.now()})
        if len(self.memory[user_id]) > self.max_messages:
            self.memory[user_id] = self.memory[user_id][-self.max_messages:]
    
    def get_context(self, user_id: int) -> list:
        return self.memory.get(user_id, [])

# ============================================================================
# 🌐 CONFIG & JOBS
# ============================================================================

TRUSTED_SOURCES = [
    {"name": "CERT-SA", "rss": "https://cert.gov.sa/ar/security-warnings/feed", "url": "https://cert.gov.sa"},
    {"name": "NCA",     "rss": "https://nca.gov.sa/ar/feed",                    "url": "https://nca.gov.sa"},
]

rate_limiter = RateLimiter()
memory = ConversationMemory()

async def backup_db():
    try:
        import shutil
        backup_name = f"backups/amanteech_{datetime.now().strftime('%Y%m%d')}.db"
        os.makedirs("backups", exist_ok=True)
        shutil.copy2("amanteech.db", backup_name)
        logger.info(f"✅ Database backup created: {backup_name}")
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")

async def check_subscriptions(app: Application):
    try:
        upcoming = db.get_upcoming_expiries()
        for sub in upcoming:
            uid = sub["user_id"]
            try:
                await app.bot.send_message(uid, "⏰ *تنبيه:* ينتهي اشتراكك في باقة Pro خلال أقل من 24 ساعة!\nاستخدم /buy للتجديد.", parse_mode="Markdown")
                db.mark_expiry_notified(uid)
            except: pass
            
        expired = db.get_expired_subscriptions()
        for sub in expired:
            uid = sub["user_id"]
            try:
                db.update_subscription(uid, "free")
                await app.bot.send_message(uid, "❌ *انتهى اشتراكك!*\nتمت إعادتك للباقة المجانية (Free).", parse_mode="Markdown")
            except: pass
    except Exception as e:
        logger.error(f"❌ Sub Check Error: {e}")

async def daily_maintenance():
    try:
        deleted_count = db.cleanup_old_data(90)
        logger.info(f"🧹 Maintenance: Cleaned up {deleted_count} old scans.")
        await backup_db()
    except Exception as e:
        logger.error(f"❌ Maintenance failed: {e}")

async def auto_broadcast(app: Application):
    subscribers = db.get_all_subscribers()
    if not subscribers: return
    for source in TRUSTED_SOURCES:
        try:
            loop = asyncio.get_event_loop()
            feed = await asyncio.wait_for(loop.run_in_executor(None, feedparser.parse, source["rss"]), timeout=10.0)
            for entry in feed.entries[:3]:
                link = entry.get("link", "")
                if not link or db.is_alert_sent(link): continue
                db.mark_alert_sent(link)
                text = f"🚨 *تنبيه أمني - {source['name']}*\n\n📌 {entry.get('title')}\n\n🔗 [التفاصيل]({link})"
                for uid in subscribers:
                    try:
                        await app.bot.send_message(uid, text, parse_mode="Markdown", read_timeout=10)
                    except Forbidden: db.ban_user(uid)
                    except Exception: pass
        except Exception as e:
            logger.error(f"❌ Broadcast error: {e}")

# ============================================================================
# 📨 MESSAGE ROUTER
# ============================================================================

def sanitize_text(text: str) -> str:
    return text.replace('\ufe0f', '').replace('\u200d', '').strip()

@not_banned
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text
    uid = update.effective_user.id
    
    if not rate_limiter.is_allowed(uid):
        await update.message.reply_text("⏳ *تريث دقيقة!*")
        return

    # ✅ Admin Button Logic
    if str(uid) == str(cfg.ADMIN_ID):
        admin_btns = ["📊 عرض المشتركين", "➕ إضافة اشتراك", "➖ حذف اشتراك", "🔙 العودة للقائمة الرئيسية"]
        if text in admin_btns:
            await handle_admin_buttons(update, context)
            return
        if "admin_action" in context.user_data:
            await process_admin_input(update, context)
            return

    memory.add(uid, text, role="user")
    state = db.get_user_state(uid)
    
    if state == "awaiting_url":
        await process_url_scan(update, context)
        return
    if state == "awaiting_ai":
        await answer_ai_question(update, context, text)
        return
        
    if update.message.chat.type != "private":
        await monitor_group(update, context)
        return
    
    await update.message.reply_text("❓ عذراً، لم أتعرف على طلبك! استخدم /help", parse_mode="Markdown")

@not_banned
async def document_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not rate_limiter.is_allowed(uid): return
    state = db.get_user_state(uid)
    
    if state in ["awaiting_file", "awaiting_image", "awaiting_qr", "awaiting_payment_proof"]:
        from handlers.scans import process_file_scan, process_image_scan, process_qr_scan
        from handlers.subscriptions import process_payment_proof as proof_handler
        
        if state == "awaiting_file": await process_file_scan(update, context)
        elif state == "awaiting_image": await process_image_scan(update, context)
        elif state == "awaiting_qr": await process_qr_scan(update, context)
        elif state == "awaiting_payment_proof": await proof_handler(update, context)
        return
            
    await update.message.reply_text("💡 يرجى اختيار الخدمة من القائمة أولاً!")

# ============================================================================
# 🚨 GLOBAL ERROR HANDLER
# ============================================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الأخطاء العالمي - يُفلتر أخطاء الشبكة المؤقتة."""
    from telegram.error import NetworkError, TimedOut, Conflict
    
    err = context.error
    
    # تجاهل أخطاء الشبكة المؤقتة تماماً بدون إزعاج المستخدم
    if isinstance(err, (NetworkError, TimedOut, Conflict)):
        logger.warning(f"⚠️ انقطاع شبكة مؤقت (يتجاهل): {type(err).__name__}")
        return
    
    # للأخطاء الحقيقية فقط: تسجيل مفصل + تنبيه مختصر للمستخدم
    logger.error("❌ خطأ غير متوقع:", exc_info=err)
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ مؤقت. حاول مرة أخرى! 🙏"
            )
        except: pass

async def web_server():
    from aiohttp import web
    import stripe
    
    async def dashboard_handler(request):
        token = request.query.get('token')
        if token != cfg.DASHBOARD_TOKEN: return web.Response(text="Unauthorized Access", status=401)
        
        with db.get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            pro_users = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE plan='pro'").fetchone()[0]
            total_refs = conn.execute("SELECT SUM(ref_count) FROM users").fetchone()[0] or 0
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Amanteech | Dashboard</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=Noto+Kufi+Arabic:wght@400;700&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --bg: #0f172a;
                    --glass: rgba(30, 41, 59, 0.7);
                    --accent: #38bdf8;
                    --text: #f1f5f9;
                    --card-bg: #1e293b;
                }}
                body {{
                    background: var(--bg);
                    color: var(--text);
                    font-family: 'Noto Kufi Arabic', 'Outfit', sans-serif;
                    margin: 0;
                    display: flex;
                    justify-content: center;
                    padding: 40px 20px;
                }}
                .container {{
                    max-width: 1000px;
                    width: 100%;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 50px;
                }}
                .header h1 {{
                    font-size: 2.5rem;
                    background: linear-gradient(to right, #38bdf8, #818cf8);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 10px;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 40px;
                }}
                .card {{
                    background: var(--card-bg);
                    padding: 25px;
                    border-radius: 20px;
                    border: 1px solid rgba(255,255,255,0.1);
                    text-align: center;
                    transition: transform 0.3s ease;
                }}
                .card:hover {{ transform: translateY(-5px); border-color: var(--accent); }}
                .card h3 {{ font-size: 0.9rem; color: #94a3b8; margin: 0; }}
                .card .value {{ font-size: 2rem; font-weight: 700; margin: 10px 0; color: var(--accent); }}
                
                .footer {{ text-align: center; color: #64748b; font-size: 0.8rem; margin-top: 50px; }}
                @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
                .container {{ animation: fadeIn 0.8s ease-out; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Amanteech SaaS Console</h1>
                    <p>إدارة أعمال المنصة السيبرانية الذكية</p>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h3>إجمالي المستخدمين</h3>
                        <div class="value">{total_users}</div>
                    </div>
                    <div class="card">
                        <h3>المشتركون Pro</h3>
                        <div class="value">{pro_users}</div>
                    </div>
                    <div class="card">
                        <h3>إجمالي الفحوصات</h3>
                        <div class="value">{total_scans}</div>
                    </div>
                    <div class="card">
                        <h3>نجاح الإحالات</h3>
                        <div class="value">{total_refs}</div>
                    </div>
                </div>
                
                <div class="footer">
                    &copy; 2026 Amanteech | All Rights Reserved
                </div>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html_template, content_type='text/html')

    async def stripe_webhook_handler(request):
        payload = await request.read()
        sig_header = request.headers.get('STRIPE_SIGNATURE')
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, cfg.STRIPE_WEBHOOK_SECRET)
            if event['type'] == 'checkout.session.completed':
                uid = event['data']['object'].get('client_reference_id')
                if uid: db.update_subscription(int(uid), "pro")
        except: pass
        return web.Response(status=200)

    app_web = web.Application()
    app_web.router.add_get('/health', lambda r: web.Response(text="OK"))
    app_web.router.add_get('/dashboard', dashboard_handler)
    app_web.router.add_post('/webhook/stripe', stripe_webhook_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', cfg.PORT)
    await site.start()

async def post_init(app: Application):
    asyncio.create_task(web_server())
    if cfg.ADMIN_ID: db.set_user_role(int(cfg.ADMIN_ID), "admin")

def main():
    cfg.validate()
    db.init_db()
    
    app = Application.builder().token(cfg.BOT_TOKEN) \
        .read_timeout(120).write_timeout(120).connect_timeout(120) \
        .pool_timeout(120).post_init(post_init).build()
    
    # تسجيل معالج الأخطاء العالمي
    app.add_error_handler(error_handler)
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("menu", menu_handler))
    app.add_handler(CommandHandler("share", cmd_referral))
    app.add_handler(CommandHandler("myplan", cmd_myplan))
    app.add_handler(CommandHandler("upgrade", cmd_upgrade))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("gen_code", gen_code))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("admin_panel", admin_panel_reply))
    app.add_handler(CommandHandler("hp_stats", cmd_hp_stats))
    app.add_handler(CommandHandler("hp_recent", cmd_hp_recent))
    app.add_handler(CommandHandler("stats", cmd_reports))
    
    async def ping(u, c):
        start = datetime.now()
        msg = await u.message.reply_text("🏓")
        await msg.edit_text(f"🚀 {(datetime.now()-start).total_seconds()*1000:.0f}ms")
    app.add_handler(CommandHandler("ping", ping))
    
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_router))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, document_router))
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_broadcast, 'interval', hours=1, args=[app])
    scheduler.add_job(daily_maintenance, 'interval', hours=24)
    scheduler.add_job(check_subscriptions, 'interval', hours=1, args=[app])
    scheduler.start()
    
    # البدء بتنظيف أي تحديثات قديمة لضمان عدم حدوث تعارض
    logger.info("🚀 Starting Bot in Production Mode...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
