
import sqlite3

db = sqlite3.connect("tugmabot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    qoida TEXT,
    viloyat TEXT,
    elon TEXT
)
""")

# Eski bazaga yangi ustun qo‘shish
cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]

if "matnlink" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN matnlink TEXT")

db.commit()
