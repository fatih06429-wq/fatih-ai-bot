import os
import threading
import asyncio
import time
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from ai import ask_ai
from hafiza import hafizayi_temizle
from firebase_admin import firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# GİZLİ KARAKTERLERDEN ARINDIRILMIŞ GÜNCEL HTML
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Kerem AI - Yapay Zeka Asistanı</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: sans-serif; background-color: #131314; color: #e3e3e3; margin: 0; height: 100vh; display: flex; }
        .sidebar { width: 260px; background-color: #1e1e20; padding: 15px; border-right: 1px solid #333; }
        .main-content { flex: 1; display: flex; flex-direction: column; }
        #chat-container { flex: 1; overflow-y: auto; padding: 20px; }
        .input-container { padding: 20px; display: flex; gap: 10px; background: #131314; }
        input[type="text"] { flex: 1; padding: 10px; border-radius: 20px; border: 1px solid #444; background: #1e1e20; color: white; }
        .bot-msg { background: #282a2c; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
        .user-msg { background: #303030; padding: 15px; border-radius: 10px; margin-bottom: 10px; text-align: right; }
    </style>
</head>
<body>
    <div class="sidebar">
        <button class="new-chat-btn" onclick="location.reload()">Yeni Sohbet</button>
        <div id="sidebar-list"></div>
    </div>
    <div class="main-content">
        <div id="chat-container"></div>
        <div class="input-container">
            <input type="text" id="user-input" placeholder="Bir şey sor..." onkeypress="if(event.key === 'Enter') mesajGonder()">
            <select id="ai-mode"><option value="thinking">Düşünen</option><option value="fast">Hızlı</option></select>
            <button onclick="mesajGonder()">Gönder</button>
        </div>
    </div>
    <script>
        let deviceId = localStorage.getItem("kerem_device_id") || "user_" + Math.random().toString(36).substr(2, 9);
        localStorage.setItem("kerem_device_id", deviceId);
        let currentSessionId = deviceId + "_" + Date.now();

        async function mesajGonder() {
            const input = document.getElementById("user-input");
            const msg = input.value;
            if (!msg.trim()) return;

            const chat = document.getElementById("chat-container");
            chat.innerHTML += '<div class="user-msg">' + msg + '</div>';
            input.value = "";
            input.disabled = true;

            const formData = new FormData();
            formData.append("mesaj", msg);
            formData.append("session_id", currentSessionId);
            formData.append("user_id", deviceId);
            formData.append("mode", document.getElementById("ai-mode").value);

            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                chat.innerHTML += '<div class="bot-msg">' + marked.parse(data.cevap) + '</div>';
                chat.scrollTop = chat.scrollHeight;
            } catch (e) { alert("Hata oluştu"); }
            input.disabled = false;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "")
    user_id = request.form.get("user_id", "")
    secilen_mod = request.form.get("mode", "thinking")
    
    cevap = ask_ai(mesaj, user_id=session_id, mode=secilen_mod)
    
    try:
        doc_ref = firestore.client().collection("web_sohbetler").document(session_id)
        if not doc_ref.get().exists: doc_ref.set({"baslik": mesaj[:25], "user_id": user_id, "mesajlar": []})
        doc_ref.update({"mesajlar": firestore.ArrayUnion([{"role": "user", "text": mesaj}, {"role": "bot", "text": cevap}])})
    except: pass
    return jsonify({"cevap": cevap})

# ... (Telegram fonksiyonları aynı kalacak)

if __name__ == '__main__':
    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)
    threading.Thread(target=run_flask, daemon=True).start()
    # (Telegram bot başlatma kodu)
