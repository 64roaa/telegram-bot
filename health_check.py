import os
import sys
import sqlite3
from pathlib import Path

def run_check():
    print("\n" + "="*50)
    print(" Amanteech Bot Health Check")
    print("="*50)
    
    # Check .env
    env_path = Path(".env")
    if env_path.exists():
        print("[OK] .env file exists.")
    else:
        print("[FAIL] .env file missing.")
        
    # Check Database
    db_path = Path("amanteech.db")
    if db_path.exists():
        print(f"[OK] Database exists ({db_path.stat().st_size} bytes)")
        try:
            conn = sqlite3.connect(str(db_path))
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            print(f"[OK] Database is readable. Users: {users_count}")
            conn.close()
        except Exception as e:
            print(f"[FAIL] Database error: {e}")
    else:
        print("[FAIL] Database missing.")

    print("="*50 + "\n")

if __name__ == "__main__":
    run_check()
