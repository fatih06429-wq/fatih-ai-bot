from flask import Flask
import sqlite3

app = Flask(__name__)

@app.route("/")
def home():
    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    # id, user_id, user_msg, bot_msg sıralamasıyla geliyor
    cur.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 20")
    data = cur.fetchall()

    html = "<h1>AI PANEL V7</h1>"

    for row in data:
        # row[0] = id, row[1] = user_id, row[2] = user_msg, row[3] = bot_msg
        html += f"<p><b>User ({row[1]}):</b> {row[2]}<br><b>AI:</b> {row[3]}</p><hr>"
    
    conn.close()

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)