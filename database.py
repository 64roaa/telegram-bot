import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = "amanteech.db"

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database Error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                subscribed  INTEGER DEFAULT 0,
                state       TEXT DEFAULT NULL,
                role        TEXT DEFAULT 'free',
                referred_by INTEGER DEFAULT NULL,
                ref_count   INTEGER DEFAULT 0,
                joined_at   TEXT DEFAULT (datetime('now')),
                last_seen   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                scan_type   TEXT NOT NULL,
                target      TEXT,
                result      TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS sent_alerts (
                alert_url   TEXT PRIMARY KEY,
                sent_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id           INTEGER PRIMARY KEY,
                plan              TEXT DEFAULT 'free',
                started_at        TEXT DEFAULT (datetime('now')),
                expires_at        TEXT,
                expiry_notified   INTEGER DEFAULT 0,
                stripe_customer   TEXT,
                stripe_sub_id     TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS codes (
                code        TEXT PRIMARY KEY,
                days        INTEGER NOT NULL,
                max_uses    INTEGER DEFAULT 1,
                used_count  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)

def upsert_user(user_id, username=None, first_name=None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_seen, role)
            VALUES (?, ?, ?, datetime('now'), 'free')
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_seen  = datetime('now')
        """, (user_id, username, first_name))

def set_user_state(user_id, state):
    with get_connection() as conn:
        conn.execute("UPDATE users SET state = ? WHERE user_id = ?", (state, user_id))

def get_user_state(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT state FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["state"] if row else None

def get_user_role(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT role FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["role"] if row and row["role"] else "free"

def set_user_role(user_id, role):
    with get_connection() as conn:
        conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))

def is_banned(user_id):
    return get_user_role(user_id) == "banned"

def get_user_plan(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {"plan": "free", "expires_at": None}

def update_subscription(user_id, plan, expires_at=None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO subscriptions (user_id, plan, expires_at, started_at, expiry_notified)
            VALUES (?, ?, ?, datetime('now'), 0)
            ON CONFLICT(user_id) DO UPDATE SET
                plan = excluded.plan,
                expires_at = excluded.expires_at,
                expiry_notified = 0
        """, (user_id, plan, expires_at))

def add_code(code, days, max_uses=1):
    with get_connection() as conn:
        conn.execute("INSERT INTO codes (code, days, max_uses) VALUES (?, ?, ?)", (code, days, max_uses))

def redeem_code(user_id, code_text):
    with get_connection() as conn:
        code = conn.execute("SELECT * FROM codes WHERE code = ?", (code_text,)).fetchone()
        if not code: return {"success": False, "msg": "❌ الكود غير صحيح."}
        if code["used_count"] >= code["max_uses"]: return {"success": False, "msg": "❌ الكود مستهلك."}
        conn.execute("UPDATE codes SET used_count = used_count + 1 WHERE code = ?", (code_text,))
        expiry = datetime.now() + timedelta(days=code["days"])
        update_subscription(user_id, "pro", expiry.isoformat())
        return {"success": True, "msg": f"✅ تم التفعيل حتى {expiry.strftime('%Y-%m-%d')}"}

def get_expired_subscriptions():
    with get_connection() as conn:
        return conn.execute("SELECT user_id FROM subscriptions WHERE expires_at IS NOT NULL AND expires_at < datetime('now')").fetchall()

def get_upcoming_expiries():
    with get_connection() as conn:
        return conn.execute("SELECT user_id FROM subscriptions WHERE expires_at IS NOT NULL AND expires_at > datetime('now') AND expires_at <= datetime('now', '+1 day') AND expiry_notified = 0").fetchall()

def mark_expiry_notified(user_id):
    with get_connection() as conn:
        conn.execute("UPDATE subscriptions SET expiry_notified = 1 WHERE user_id = ?", (user_id,))

def log_scan(user_id, scan_type, target, result):
    with get_connection() as conn:
        conn.execute("INSERT INTO scans (user_id, scan_type, target, result) VALUES (?, ?, ?, ?)", (user_id, scan_type, target, result))

def get_daily_scans_count(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as count FROM scans WHERE user_id = ? AND created_at >= datetime('now', '-1 day')", (user_id,)).fetchone()
        return row["count"] if row else 0

def cleanup_old_data(days=90):
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM scans WHERE created_at < datetime('now', ?)", (f"-{days} days",))
        return cur.rowcount

def is_alert_sent(alert_url):
    with get_connection() as conn:
        return conn.execute("SELECT 1 FROM sent_alerts WHERE alert_url = ?", (alert_url,)).fetchone() is not None

def mark_alert_sent(alert_url):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO sent_alerts (alert_url) VALUES (?)", (alert_url,))

def add_referral(user_id: int, referrer_id: int):
    """تسجيل عملية إحالة جديدة ومنح مكافأة عند الوصول لـ 5 إحالات."""
    if user_id == referrer_id: return False
    with get_connection() as conn:
        user = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user and user["referred_by"] is None:
            conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
            conn.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer_id,))
            
            # فحص إذا وصل الداعي للمكافأة (مضاعفات الرقم 5)
            new_count = conn.execute("SELECT ref_count FROM users WHERE user_id = ?", (referrer_id,)).fetchone()["ref_count"]
            if new_count > 0 and new_count % 5 == 0:
                # منح 7 أيام Pro
                expiry = datetime.now() + timedelta(days=7)
                update_subscription(referrer_id, "pro", expiry.isoformat())
                return "REWARD"
            return True
    return False

def get_ref_stats(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT ref_count FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["ref_count"] if row else 0

def get_all_subscribers():
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id FROM users WHERE subscribed = 1").fetchall()
        return [r["user_id"] for r in rows]

def ban_user(user_id: int) -> None:
    set_user_role(user_id, "banned")

def get_user(user_id: int) -> dict | None:
    """يُعيد بيانات مستخدم واحد أو None إذا لم يكن موجوداً."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

def set_subscription(user_id: int, subscribed: bool) -> None:
    """تفعيل/إيقاف اشتراك الإشعارات للمستخدم."""
    val = 1 if subscribed else 0
    with get_connection() as conn:
        conn.execute("UPDATE users SET subscribed = ? WHERE user_id = ?", (val, user_id))

def get_user_stats(user_id: int) -> dict:
    """يُعيد إحصائيات فحوصات المستخدم: الإجمالي + التوزيع حسب النوع."""
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM scans WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

        by_type_rows = conn.execute("""
            SELECT scan_type, COUNT(*) as cnt
            FROM scans WHERE user_id = ?
            GROUP BY scan_type
        """, (user_id,)).fetchall()

        return {
            "total": total,
            "by_type": {row["scan_type"]: row["cnt"] for row in by_type_rows}
        }

