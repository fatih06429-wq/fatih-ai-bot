import os
import threading
import asyncio
from flask import Flask, request, jsonify, render_template_string
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# --- FLASK WEB SUNUCUSU ---
app = Flask(__name__)

# YENİ TASARIM: YAZIYOR ANİMASYONU VE MARKDOWN (ZENGİN METİN) DESTEĞİ EKLENDİ
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yapay Zeka Asistanı</title>
    <!-- Markdown Çevirici Kütüphane -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        h2 { color: #4CAF50; }
        #chat-container { width: 100%; max-width: 800px; background-color: #1e1e1e; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); padding: 20px; display: flex; flex-direction: column; height: 75vh; }
        #chat-box { flex: 1; overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; }
        .message { padding: 12px 16px; border-radius: 12px; max-width: 85%; line-height: 1.5; word-wrap: break-word; font-size: 15px; }
        .user-msg { background-color: #2196F3; align-self: flex-end; border-bottom-right-radius: 2px; }
        .bot-msg { background-color: #333333; align-self: flex-start; border-bottom-left-radius: 2px; }
        
        /* Markdown Özel Tasarımları (Kod blokları, listeler vs.) */
        .bot-msg p { margin: 0 0 10px 0; }
        .bot-msg p:last-child { margin: 0; }
        .bot-msg code { background-color: #1a1a1a; padding: 3px 6px; border-radius: 5px; font-family: Consolas, monospace; color: #4CAF50; border: 1px solid #444; }
        .bot-msg pre { background-color: #1a1a1a; padding: 12px; border-radius: 8px; overflow-x: auto; border: 1px solid #444; }
        .bot-msg pre code { background-color: transparent; padding: 0; border: none; color: #e0e0e0; }
        .bot-msg ul, .bot-msg ol { margin: 5px 0; padding-left: 20px; }
        .bot-msg a { color: #64B5F6; text-decoration: none; }
        .bot-msg a:hover { text-decoration: underline; }

        /* Yazıyor... Animasyonu CSS'i */
        .typing-indicator { display: flex; gap: 5px; padding: 5px; align-items: center; }
        .dot { width: 8px; height: 8px; background-color: #bbb; border-radius: 50%; animation: blink 1.4s infinite both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes blink { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }

        #input-area { display: flex; gap: 10px; margin-top: 20px; }
        input[type="text"] { flex: 1; padding: 15px; border-radius: 8px; border: 1px solid #444; background-color: #2d2d2d; color: white; font-size: 16px; outline: none; transition: 0.3s; }
        input[type="text"]:focus { border-color: #4CAF50; }
        input[type="text"]:disabled { background-color: #1a1a1a; color: #777; cursor: not-allowed; }
        button { padding: 15px 25px; border-radius: 8px; border: none; background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { background-color: #45a049; }
        button:disabled { background-color: #555; cursor: not-allowed; color: #aaa; }
        
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #1e1e1e; }
        ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
    </style>
</head>
<body>
    <h2>🤖 Yapay Zeka Asistanı</h2>
    <div id="chat-container">
        <div id="chat-box">
            <div class="message bot-msg"><b>Asistan:</b> Merhaba! Sana nasıl yardımcı olabilirim?</div>
        </div>
        <div id="input-area">
            <input type="text" id="user-input" placeholder="Mesajını yaz..." onkeypress="if(event.key === 'Enter') mesajGonder()" autocomplete="off">
            <button id="send-btn" onclick="mesajGonder()">Gönder</button>
        </div>
    </div>

    <script>
        // Metin içindeki enter boşluklarını koru
        marked.setOptions({ breaks: true });

        async function mesajGonder() {
            const inputElement = document.getElementById("user-input");
            const sendBtn = document.getElementById("send-btn");
            const mesaj = inputElement.value.trim();
            if (!mesaj) return;
            
            const chatBox = document.getElementById("chat-box");
            
            // 1. Senin mesajını ekrana bas
            chatBox.innerHTML += `<div class="message user-msg"><b>Sen:</b> ${mesaj}</div>`;
            inputElement.value = "";
            chatBox.scrollTop = chatBox.scrollHeight;

            // 2. Kutuyu kilitle ve "Yazıyor..." animasyonunu çıkar
            inputElement.disabled = true;
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
                // 3. Yapay zekaya soruyu gönder
                const response = await fetch("/api/sor", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mesaj: mesaj })
                });
                const data = await response.json();
                
                // 4. Animasyonu sil
                document.getElementById(typingId).remove();
                
                // 5. Gelen cevabı Markdown süzgecinden geçirip ekrana bas
                const formatliCevap = marked.parse(data.cevap);
                chatBox.innerHTML += `<div class="message bot-msg"><b>Asistan:</b> <br>${formatliCevap}</div>`;
            } catch (error) {
                document.getElementById(typingId).remove();
                chatBox.innerHTML += `<div class="message bot-msg" style="color: #ff5252;"><b>Hata:</b> Bağlantı kurulamadı.</div>`;
            }
            
            // 6. Kilidi aç, imleci tekrar kutuya koy
            inputElement.disabled = false;
            sendBtn.disabled = false;
            inputElement.focus();
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa():
    return render_template_string(HTML_SAYFASI)

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    veri = request.json
    gelen_mesaj = veri.get("mesaj", "")
    cevap = ask_ai(gelen_mesaj, user_id="web_kullanicisi")
    return jsonify({"cevap": cevap})

# --- TELEGRAM VE AI BAĞLANTILARI ---
print("--- KÜTÜPHANELER YÜKLENİYOR ---", flush=True)

from ai import ask_ai, hafizayi_temizle
from db import save

TOKEN = "8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0"
print(f"--- TOKEN OKUNDU ---", flush=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    mesaj = "Merhaba! Ben yapay zeka asistanınım. Benimle dilediğin konuda sohbet edebilirsin. Neler yapmak istersin?"
    await update.message.reply_text(mesaj)
    save(user_id, "/start", mesaj)

async def yardim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = "Bana doğrudan bir mesaj yazarak sohbet edebilirsin. Hafızam var, önceki konuştuklarımızı hatırlarım!\n\nKomutlar:\n/start - Botu yeniden başlatır\n/yardim - Bu menüyü gösterir\n/temizle - Sohbet geçmişini sıfırlar"
    await update.message.reply_text(mesaj)

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    hafizayi_temizle(user_id)
    mesaj = "🧹 Hafızam tamamen temizlendi! Artık yepyeni bir sayfa açtık. Ne konuşalım?"
    await update.message.reply_text(mesaj)
    save(user_id, "/temizle", mesaj)

async def fotograf_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    caption = update.message.caption if update.message.caption else "Bu fotoğrafta ne görüyorsun? Lütfen Türkçe açıkla."
    bekleme_mesaji = await update.message.reply_text("📸 Fotoğraf inceleniyor...")
    dosya_adi = f"foto_{user_id}.jpg"
    
    try:
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        await file.download_to_drive(dosya_adi)
        reply = ask_ai(caption, user_id, image_path=dosya_adi)
        await bekleme_mesaji.edit_text(reply)
        save(user_id, f"(Fotoğraf) {caption}", reply)
    finally:
        if os.path.exists(dosya_adi):
            os.remove(dosya_adi)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.message.from_user.id) 
    reply = ask_ai(user_text, user_id)
    await update.message.reply_text(reply)
    save(user_id, user_text, reply)

def run_telegram_bot():
    print("🔥 TELEGRAM BOTU BAŞLATILIYOR...", flush=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app_telegram = Application.builder().token(TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("yardim", yardim_command))
    app_telegram.add_handler(CommandHandler("temizle", temizle_command))
    app_telegram.add_handler(MessageHandler(filters.PHOTO, fotograf_al))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    app_telegram.run_polling(stop_signals=None)

if __name__ == '__main__':
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    print("--- TELEGRAM ARKA PLANDA ÇALIŞIYOR ---", flush=True)

    port = int(os.environ.get("PORT", 10000))
    print(f"--- WEB SUNUCUSU {port} PORTUNDA DİNLENİYOR ---", flush=True)
    app.run(host="0.0.0.0", port=port, use_reloader=False)
