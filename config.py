"""
config.py - نظام تحميل الإعدادات المحسّن لـ Amanteech Bot
===========================================================
يحل جميع مشاكل load_dotenv الشائعة:
  - يجد .env بغض النظر عن مجلد التشغيل
  - يتحقق من وجود المتغيرات الضرورية
  - يعطي رسائل خطأ واضحة
  - يدعم قيم افتراضية
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


# -- 1. إيجاد ملف .env --------------------------------------------

def _find_env_file() -> Path | None:
    here = Path(__file__).parent.resolve()
    if (here / ".env").exists():
        return here / ".env"

    cwd = Path.cwd()
    if (cwd / ".env").exists():
        return cwd / ".env"

    parent = here.parent
    if (parent / ".env").exists():
        return parent / ".env"

    return None


# -- 2. تحميل الإعدادات -------------------------------------------------------

env_path = _find_env_file()

if env_path:
    load_dotenv(dotenv_path=env_path, override=True)
    _env_loaded = True
    _env_source = str(env_path)
else:
    _env_loaded = False
    _env_source = "Environment Variables (No .env file found)"


# -- 3. قراءة المتغيرات --------------------------------------

class _Config:
    BOT_TOKEN: str         = os.getenv("BOT_TOKEN", "")
    VIRUSTOTAL_KEY: str    = os.getenv("VIRUSTOTAL_KEY", "")
    OPENAI_KEY: str        = os.getenv("OPENAI_KEY", "")
    SAFE_BROWSING_KEY: str = os.getenv("SAFE_BROWSING_KEY", "")
    WEBHOOK_URL: str       = os.getenv("WEBHOOK_URL", "")
    PORT: int              = int(os.getenv("PORT", "8080"))
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    ADMIN_ID: str          = os.getenv("ADMIN_ID", "")
    DASHBOARD_TOKEN: str   = os.getenv("DASHBOARD_TOKEN", "amanteech123")

    ENV_LOADED: bool       = _env_loaded
    ENV_SOURCE: str        = _env_source

    def validate(self) -> None:
        print("\n" + "=" * 55)
        print("  Amanteech Bot - Config Check")
        print("=" * 55)

        if self.ENV_LOADED:
            print(f"  .env file: OK ({self.ENV_SOURCE})")
        else:
            print(f"  .env file: NOT FOUND (using env vars)")

        print()

        required = {"BOT_TOKEN": self.BOT_TOKEN}
        optional = {
            "VIRUSTOTAL_KEY": self.VIRUSTOTAL_KEY,
            "OPENAI_KEY": self.OPENAI_KEY,
            "STRIPE_SECRET_KEY": self.STRIPE_SECRET_KEY,
            "STRIPE_WEBHOOK_SECRET": self.STRIPE_WEBHOOK_SECRET
        }

        errors = []
        for key, val in required.items():
            if val:
                masked = val[:8] + "..."
                print(f"  [OK] {key:<22} = {masked}")
            else:
                print(f"  [MISSING] {key:<22}")
                errors.append(key)

        for key, val in optional.items():
            if val:
                masked = val[:8] + "..."
                print(f"  [OK] {key:<22} = {masked}")
            else:
                print(f"  [OPTIONAL] {key:<22} (Disabled)")

        print("=" * 55)

        if errors:
            print("\nERROR: Required variables missing!")
            sys.exit(1)

        print("Config validation complete!\n")


cfg = _Config()
