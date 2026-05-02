import sqlite3

def fix_db():
    conn = sqlite3.connect('amanteech.db')
    cursor = conn.cursor()
    
    columns_to_add = [
        ('expires_at', 'TEXT'),
        ('expiry_notified', 'INTEGER DEFAULT 0'),
        ('ref_count', 'INTEGER DEFAULT 0'),
        ('subscribed', 'INTEGER DEFAULT 0')
    ]
    
    cursor.execute("PRAGMA table_info(users)")
    current_columns = [row[1] for row in cursor.fetchall()]
    
    for col_name, col_type in columns_to_add:
        if col_name not in current_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")
            
    conn.commit()
    conn.close()
    print("Database fix completed!")

if __name__ == "__main__":
    fix_db()
