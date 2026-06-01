import os
import threading
import asyncio
import time
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from ai import ask_ai, hafizayi_temizle
from firebase_admin import firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# TAM TASARIMLI ARAYÜZ (sidebar, karanlık mod, daktilo vb.)
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Kerem AI</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --bg: #131314; --sidebar: #1e1e20; --text: #e3e3e3; --accent: #a8c7fa; }
        body { font-family: sans-serif; background-color: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; }
        .sidebar { width: 260px; background: var(--sidebar); padding: 15px; display: flex; flex-direction: column; }
        .main { flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }
        #chat-container { flex: 1; max-width: 800px; margin: 0 auto; width: 100%; }
        .message { padding: 15px; margin: 10px 0; border-radius: 10px; background: #202123; }
        .input-area { max-width: 800px; margin: 20px auto; display: flex; gap: 10px; width: 100%; }
        input { flex: 1; padding: 12px; border-radius: 5px; background: #303030; border: 1px solid #444; color: white; }
        button { padding: 10px 20px; cursor: pointer; background: var(--accent); border: none; border-radius: 5px; }
        .history-item { cursor: pointer; padding: 10px; border-bottom: 1px solid #333; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>Sohbetler</h3>
        <button onclick="location.reload()">Yeni Sohbet</button>
        <div id="sidebar-list"></div>
    </div>
    <div class="main">
        <div id="chat-container"><h2>✨ Kerem AI</h2></div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="Kerem'e bir şey sor...">
            <button onclick="mesajGonder()">Gönder</button>
        </div>
    </div>
    <script>
        let deviceId = localStorage.getItem("dev_id") || "user_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("dev_id", deviceId);
        let sessionId = deviceId + "_" + Date.now();

        async function mesajGonder() {
            const input = document.getElementById('user-input');
            const chat = document.getElementById('chat-container');
            const msg = input.value;
            if(!msg) return;
            chat.innerHTML += `<div class="message"><b>Sen:</b> ${msg}</div>`;
            const fd = new FormData();
            fd.append('mesaj', msg); fd.append('session_id', sessionId); fd.append('user_id', deviceId);
            const res = await fetch('/api/sor', {method: 'POST', body: fd});
            const data = await res.json();
            chat.innerHTML += `<div class="message"><b>Kerem:</b> ${marked.parse(data.cevap)}</div>`;
            input.value = '';
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

@app.route("/api/sohbetler", methods=["GET"])
def sohbetleri_getir():
    try:
        docs = firestore.client().collection("web_sohbetler").where("user_id", "==", request.args.get("user_id")).stream()
        return jsonify({"sohbetler": [{"id": d.id, "baslik": d.to_dict().get("baslik")} for d in docs]})
    except: return jsonify({"sohbetler": []})

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "")
    cevap = ask_ai(mesaj, user_id=session_id)
    try:
        doc_ref = firestore.client().collection("web_sohbetler").document(session_id)
        if not doc_ref.get().exists: doc_ref.set({"baslik": mesaj[:25], "user_id": request.form.get("user_id"), "mesajlar": []})
        doc_ref.update({"mesajlar": firestore.ArrayUnion([{"role": "user", "text": mesaj}, {"role": "bot", "text": cevap}])})
    except: pass
    return jsonify({"cevap": cevap})

# --- Telegram ve Başlatma ---
async def dosya_al(update, context):
    dosya_adi = f"tg_{int(time.time())}.pdf"
    file = await context.bot.get_file(update.message.document.file_id)
    await file.download_to_drive(dosya_adi)
    reply = ask_ai(update.message.caption or "Analiz et", f"tg_{update.message.from_user.id}", image_path=dosya_adi)
    await update.message.reply_text(reply)
    if os.path.exists(dosya_adi): os.remove(dosya_adi)

def run_telegram_bot():
    app_bot = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    app_bot.add_handler(MessageHandler(filters.Document.PDF, dosya_al))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: asyncio.run(u.message.reply_text(ask_ai(u.message.text, f"tg_{u.message.from_user.id}")))))
    app_bot.run_polling()

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False), daemon=True).start()
    run_telegram_bot()
