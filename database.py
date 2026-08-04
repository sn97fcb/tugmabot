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

db.commit()