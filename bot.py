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

# TAM EKRAN MODERN WEB ARAYÜZÜ + DOSYA + SES + MOD SEÇİMİ
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kerem AI - Yapay Zeka Asistanı</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        /* CSS Değişkenleri ile Gece/Gündüz Modu Altyapısı */
        :root {
            --bg-color: #131314;
            --chat-bg: #1e1e20;
            --text-color: #e3e3e3;
            --bot-msg-bg: #282a2c;
            --bot-border: #333;
            --user-msg-bg: #004a77;
            --input-bg: #1e1e20;
            --input-border: #444;
            --accent: #a8c7fa;
            --header-shadow: rgba(0,0,0,0.4);
        }

        [data-theme="light"] {
            --bg-color: #f0f4f9;
            --chat-bg: #ffffff;
            --text-color: #1f1f1f;
            --bot-msg-bg: #f0f4f9;
            --bot-border: #e0e0e0;
            --user-msg-bg: #d3e3fd;
            --input-bg: #f0f4f9;
            --input-border: #ccc;
            --accent: #0b57d0;
            --header-shadow: rgba(0,0,0,0.1);
        }

        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg-color); color: var(--text-color); margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; transition: background-color 0.4s, color 0.4s; }
        
        .header { background-color: var(--chat-bg); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--bot-border); box-shadow: 0 4px 15px var(--header-shadow); z-index: 10; transition: 0.4s; }
        .header h2 { margin: 0; color: var(--accent); font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 10px;}
        
        .header-controls { display: flex; gap: 10px; }
        .ui-select, .theme-toggle { background: var(--bg-color); border: 1px solid var(--bot-border); color: var(--text-color); padding: 8px 12px; border-radius: 20px; cursor: pointer; font-size: 15px; transition: 0.3s; outline: none; }
        .ui-select:hover, .theme-toggle:hover { background: var(--bot-msg-bg); border-color: var(--accent); }

        #chat-container { flex: 1; display: flex; flex-direction: column; width: 100%; overflow: hidden; }
        #chat-box { flex: 1; overflow-y: auto; padding: 40px 15%; display: flex; flex-direction: column; gap: 25px; scroll-behavior: smooth; }
        
        .message { padding: 18px 24px; border-radius: 18px; max-width: 85%; line-height: 1.6; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: 0.3s; }
        .user-msg { background-color: var(--user-msg-bg); color: var(--text-color); align-self: flex-end; border-bottom-right-radius: 4px; }
        .bot-msg { background-color: var(--bot-msg-bg); align-self: flex-start; border-bottom-left-radius: 4px; border: 1px solid var(--bot-border); width: 100%; }
        
        /* Markdown Tasarımları */
        .bot-msg p { margin: 0 0 12px 0; }
        .bot-msg p:last-child { margin: 0; }
        .bot-msg code { background-color: rgba(0,0,0,0.2); padding: 4px 8px; border-radius: 6px; font-family: Consolas, monospace; color: var(--accent); }
        [data-theme="light"] .bot-msg code { background-color: rgba(0,0,0,0.05); }
        .bot-msg pre { background-color: #1e1e1e; padding: 15px; border-radius: 10px; overflow-x: auto; color: #fff; }
        
        /* Düşünüyor Animasyonu */
        .thinking { display: flex; align-items: center; gap: 8px; font-style: italic; color: #888; font-size: 14px; }
        .spinner { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        /* Mikrofon Dinleme Animasyonu */
        @keyframes pulse-mic { 0% { transform: scale(1); } 50% { transform: scale(1.2); color: #ff5252; } 100% { transform: scale(1); } }
        .listening { animation: pulse-mic 1.5s infinite; color: #ff5252 !important; }

        /* Modern Giriş Alanı */
        #input-area { background-color: var(--chat-bg); padding: 20px 15%; display: flex; gap: 12px; border-top: 1px solid var(--bot-border); align-items: center; z-index: 10; transition: 0.4s; }
        .input-wrapper { flex: 1; display: flex; background-color: var(--input-bg); border: 1px solid var(--input-border); border-radius: 30px; padding: 5px 15px; align-items: center; transition: 0.3s; }
        .input-wrapper:focus-within { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
        
        input[type="text"] { flex: 1; padding: 12px 5px; border: none; background: transparent; color: var(--text-color); font-size: 16px; outline: none; }
        
        .action-btn { background: transparent; border: none; color: #888; font-size: 20px; cursor: pointer; padding: 10px; border-radius: 50%; transition: 0.2s; display: flex; align-items: center; justify-content: center; }
        .action-btn:hover { background-color: var(--bot-border); color: var(--text-color); }
        
        #send-btn { background-color: var(--accent); color: var(--bg-color); font-weight: bold; border-radius: 50%; width: 45px; height: 45px; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; transition: 0.3s; }
        #send-btn:hover { transform: scale(1.05); filter: brightness(1.1); }
        #send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        /* Kaydırma Çubuğu */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--bot-border); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h2>✨ Kerem AI</h2>
        <div class="header-controls">
            <select id="ai-mode" class="ui-select" title="Yanıt Hızını Seç">
                <option value="thinking">🧠 Düşünen Mod</option>
                <option value="fast">⚡ Hızlı Mod</option>
            </select>
            <button class="theme-toggle" onclick="temaDegistir()">☀️ Açık Mod</button>
        </div>
    </div>
    
    <div id="chat-container">
        <div id="chat-box">
            <div class="message bot-msg"><b>Kerem:</b> Merhaba! Yanıt hızımı yukarıdan ayarlayabilirsin. Sana nasıl yardımcı olabilirim?</div>
        </div>
        
        <div id="input-area">
            <input type="file" id="file-input" style="display:none" accept="image/*, video/*, audio/*, .pdf, .doc, .docx">
            
            <div class="input-wrapper">
                <button class="action-btn" onclick="document.getElementById('file-input').click()" title="Dosya Ekle">📎</button>
                <input type="text" id="user-input" placeholder="Kerem'e bir şey sor..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
                <button class="action-btn" id="mic-btn" title="Sesli Soru Sor">🎤</button>
            </div>
            
            <button id="send-btn" onclick="mesajGonder()">➤</button>
        </div>
    </div>

    <script>
        marked.setOptions({ breaks: true });

        // Gece/Gündüz Modu Kontrolü
        function temaDegistir() {
            const body = document.body;
            const btn = document.querySelector('.theme-toggle');
            if (body.getAttribute('data-theme') === 'light') {
                body.removeAttribute('data-theme');
                btn.innerHTML = '☀️ Açık Mod';
            } else {
                body.setAttribute('data-theme', 'light');
                btn.innerHTML = '🌙 Koyu Mod';
            }
        }

        // İnsansı Yazma Efekti (Typewriter)
        async function daktiloEfekti(element, metin, hiz = 15) {
            let i = 0;
            let anlikMetin = "";
            return new Promise((resolve) => {
                const timer = setInterval(() => {
                    anlikMetin += metin.charAt(i);
                    element.innerHTML = marked.parse(anlikMetin);
                    document.getElementById("chat-box").scrollTop = document.getElementById("chat-box").scrollHeight;
                    i++;
                    if (i === metin.length) {
                        clearInterval(timer);
                        resolve();
                    }
                }, hiz);
            });
        }

        // Ses Tanıma (Web Speech API) Ayarları
        const micBtn = document.getElementById("mic-btn");
        const userInput = document.getElementById("user-input");
        let recognition;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'tr-TR';
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onstart = function() {
                micBtn.classList.add("listening");
                userInput.placeholder = "Dinliyorum, konuşabilirsin...";
            };

            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                userInput.value = userInput.value ? userInput.value + " " + transcript : transcript;
            };

            recognition.onerror = function(event) {
                console.error("Ses tanıma hatası: ", event.error);
                userInput.placeholder = "Kerem'e bir şey sor...";
            };

            recognition.onend = function() {
                micBtn.classList.remove("listening");
                userInput.placeholder = "Kerem'e bir şey sor...";
            };

            micBtn.onclick = function() {
                try {
                    recognition.start();
                } catch(e) {
                    recognition.stop();
                }
            };
        } else {
            micBtn.style.display = "none";
        }

        async function mesajGonder() {
            const input = document.getElementById("user-input");
            const fileInput = document.getElementById("file-input");
            const chatBox = document.getElementById("chat-box");
            const sendBtn = document.getElementById("send-btn");
            const aiMode = document.getElementById("ai-mode").value; // Seçilen modu al
            
            if (!input.value.trim() && fileInput.files.length === 0) return;

            const formData = new FormData();
            formData.append("mesaj", input.value);
            
            let eklentiMetni = "";
            if (fileInput.files.length > 0) {
                formData.append("dosya", fileInput.files[0]);
                eklentiMetni = `<br><small style="color:var(--accent);">📎 ${fileInput.files[0].name}</small>`;
            }

            chatBox.innerHTML += `<div class="message user-msg">${input.value} ${eklentiMetni}</div>`;
            input.value = "";
            fileInput.value = "";
            
            input.disabled = true;
            sendBtn.disabled = true;
            micBtn.disabled = true;
            
            // Moda göre bekleme yazısını ayarla
            const waitingText = aiMode === "fast" ? "Hızla yanıtlıyor..." : "Kerem Düşünüyor...";
            
            const typingId = "typing-" + Date.now();
            chatBox.innerHTML += `
                <div id="${typingId}" class="message bot-msg">
                    <div class="thinking"><div class="spinner"></div> ${waitingText}</div>
                </div>`;
            chatBox.scrollTop = chatBox.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                
                const botMesajKutusu = document.getElementById(typingId);
                botMesajKutusu.innerHTML = ""; 
                
                // Seçime göre cevabı ekrana bas
                if (aiMode === "fast") {
                    botMesajKutusu.innerHTML = marked.parse(data.cevap);
                    chatBox.scrollTop = chatBox.scrollHeight;
                } else {
                    await daktiloEfekti(botMesajKutusu, data.cevap);
                }
                
            } catch (error) {
                document.getElementById(typingId).innerHTML = `<span style="color: #ff5252;">Bağlantı hatası oluştu.</span>`;
            }
            
            input.disabled = false;
            sendBtn.disabled = false;
            micBtn.disabled = false;
            input.focus();
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
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await update.message.reply_text("Merhaba! Kerem AI'ye hoş geldin. Bana metin, fotoğraf veya PDF gönderebilirsin.")

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    hafizayi_temizle(user_id)
    await update.message.reply_text("🧹 Hafızam tamamen temizlendi! Yepyeni bir sayfa açtık.")

async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    caption = update.message.caption if update.message.caption else "Lütfen bu dosyayı benim için analiz et."
    bekleme_mesaji = await update.message.reply_text("📥 Dosya inceleniyor, lütfen bekle...")
    
    dosya_adi = f"dosya_{user_id}"
    
    try:
        if update.message.photo:
            file = await context.bot.get_file(update.message.photo[-1].file_id)
            dosya_adi += ".jpg"
        elif update.message.document:
            file = await context.bot.get_file(update.message.document.file_id)
            dosya_adi += ".pdf"
            
        await file.download_to_drive(dosya_adi)
        
        reply = ask_ai(caption, user_id, image_path=dosya_adi)
        await bekleme_mesaji.edit_text(reply)
    except Exception as e:
        await bekleme_mesaji.edit_text(f"Dosya işlenirken hata oluştu: {e}")
    finally:
        if os.path.exists(dosya_adi):
            os.remove(dosya_adi)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await update.message.reply_text(ask_ai(update.message.text, str(update.message.from_user.id)))

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app_telegram = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("temizle", temizle_command))
    app_telegram.add_handler(MessageHandler(filters.PHOTO | filters.Document.PDF, dosya_al))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    app_telegram.run_polling(stop_signals=None)

if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
