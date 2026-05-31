import os
import threading
import asyncio
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from ai import ask_ai, hafizayi_temizle
from db import save

# --- FLASK WEB SUNUCUSU ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# TAM EKRAN (FULL-SCREEN) MODERN WEB ARAYÜZÜ + DOSYA YÜKLEME
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yapay Zeka Asistanı</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        .header { background-color: #1e1e1e; padding: 15px 20px; text-align: center; border-bottom: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.4); z-index: 10; }
        .header h2 { margin: 0; color: #4CAF50; font-size: 22px; letter-spacing: 1px; }
        #chat-container { flex: 1; display: flex; flex-direction: column; background-color: #121212; width: 100%; overflow: hidden; }
        #chat-box { flex: 1; overflow-y: auto; padding: 30px 15%; display: flex; flex-direction: column; gap: 20px; scroll-behavior: smooth; }
        .message { padding: 15px 22px; border-radius: 12px; max-width: 80%; line-height: 1.6; word-wrap: break-word; font-size: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .user-msg { background-color: #2196F3; align-self: flex-end; border-bottom-right-radius: 2px; }
        .bot-msg { background-color: #1e1e1e; align-self: flex-start; border-bottom-left-radius: 2px; border: 1px solid #2a2a2a; }
        
        /* Markdown Özel Tasarımları */
        .bot-msg p { margin: 0 0 10px 0; }
        .bot-msg p:last-child { margin: 0; }
        .bot-msg code { background-color: #000; padding: 4px 8px; border-radius: 6px; font-family: Consolas, monospace; color: #4CAF50; border: 1px solid #333; }
        .bot-msg pre { background-color: #0a0a0a; padding: 15px; border-radius: 10px; overflow-x: auto; border: 1px solid #333; }
        .bot-msg pre code { background-color: transparent; padding: 0; border: none; color: #e0e0e0; }
        
        /* Yazıyor... Animasyonu */
        .typing-indicator { display: flex; gap: 6px; padding: 5px; align-items: center; }
        .dot { width: 8px; height: 8px; background-color: #888; border-radius: 50%; animation: blink 1.4s infinite both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes blink { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }

        /* Input Alanı */
        #input-area { background-color: #1e1e1e; padding: 20px 15%; display: flex; gap: 15px; border-top: 1px solid #333; align-items: center; z-index: 10; }
        input[type="text"] { flex: 1; padding: 16px 25px; border-radius: 30px; border: 1px solid #444; background-color: #2d2d2d; color: white; font-size: 16px; outline: none; transition: 0.3s; }
        button { padding: 16px 25px; border-radius: 30px; border: none; background-color: #4CAF50; color: white; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:disabled { background-color: #555; cursor: not-allowed; }
        #file-btn { background-color: #555; }
    </style>
</head>
<body>
    <div class="header"><h2>🤖 Yapay Zeka Asistanı</h2></div>
    <div id="chat-container">
        <div id="chat-box">
            <div class="message bot-msg"><b>Asistan:</b> Merhaba! Dosya yükleyebilir veya soru sorabilirsin.</div>
        </div>
        <div id="input-area">
            <input type="file" id="file-input" style="display:none" accept="image/*,.pdf">
            <button id="file-btn" onclick="document.getElementById('file-input').click()">📁</button>
            <input type="text" id="user-input" placeholder="Mesajını yaz..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
            <button id="send-btn" onclick="mesajGonder()">Gönder</button>
        </div>
    </div>
    <script>
        marked.setOptions({ breaks: true });
        
        async function mesajGonder() {
            const input = document.getElementById("user-input");
            const fileInput = document.getElementById("file-input");
            const chatBox = document.getElementById("chat-box");
            const sendBtn = document.getElementById("send-btn");
            
            if (!input.value.trim() && fileInput.files.length === 0) return;

            const formData = new FormData();
            formData.append("mesaj", input.value);
            if (fileInput.files.length > 0) formData.append("dosya", fileInput.files[0]);

            chatBox.innerHTML += `<div class="message user-msg"><b>Sen:</b> ${input.value} ${fileInput.files.length ? '(Dosya eklendi)' : ''}</div>`;
            input.value = "";
            fileInput.value = "";
            
            // Kutuyu kilitle ve animasyonu çıkar
            input.disabled = true;
            sendBtn.disabled = true;
            const typingId = "typing-" + Date.now();
            chatBox.innerHTML += `
                <div id="${typingId}" class="message bot-msg">
                    <b>Asistan:</b>
                    <div class="typing-indicator">
                        <div class="dot"></div><div class="dot"></div><div class="dot"></div>
                    </div>
                </div>`;
            chatBox.scrollTop = chatBox.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                
                document.getElementById(typingId).remove();
                chatBox.innerHTML += `<div class="message bot-msg"><b>Asistan:</b> <br>${marked.parse(data.cevap)}</div>`;
            } catch (error) {
                document.getElementById(typingId).remove();
                chatBox.innerHTML += `<div class="message bot-msg" style="color: #ff5252;"><b>Hata:</b> Bağlantı kurulamadı.</div>`;
            }
            
            // Kilidi aç
            input.disabled = false;
            sendBtn.disabled = false;
            input.focus();
            chatBox.scrollTop = chatBox.scrollHeight;
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
    dosya_yolu = None
    if 'dosya' in request.files:
        file = request.files['dosya']
        if file.filename != '':
            dosya_yolu = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(dosya_yolu)
    
    cevap = ask_ai(mesaj, user_id="web_kullanicisi", image_path=dosya_yolu)
    if dosya_yolu and os.path.exists(dosya_yolu): os.remove(dosya_yolu)
    return jsonify({"cevap": cevap})

# --- TELEGRAM BOTU ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Merhaba! AÖF Asistanına hoş geldin.")
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(ask_ai(update.message.text, str(update.message.from_user.id)))

def run_telegram_bot():
    app_telegram = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    # KRİTİK ÇÖZÜM: stop_signals=None eklendi.
    app_telegram.run_polling(stop_signals=None)

if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
