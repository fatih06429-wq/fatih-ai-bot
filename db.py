import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    user_msg TEXT,
    bot_msg TEXT
)
""")

conn.commit()


def save(user_id, user_msg, bot_msg):
    cursor.execute(
        "INSERT INTO messages (user_id, user_msg, bot_msg) VALUES (?, ?, ?)",
        (user_id, user_msg, bot_msg)
    )
    conn.commit()


def get_last(user_id, limit=10):
    cursor.execute(
        "SELECT user_msg, bot_msg FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    return cursor.fetchall()