import os
import threading
import asyncio
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from ai import ask_ai, hafizayi_temizle
from db import save
from firebase_admin import firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kerem AI - Yapay Zeka Asistanı</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-color: #131314; --chat-bg: #1e1e20; --sidebar-bg: #1e1e20;
            --text-color: #e3e3e3; --bot-msg-bg: transparent; --bot-border: #333;
            --user-msg-bg: #303030; --input-bg: #1e1e20; --input-border: #444;
            --accent: #a8c7fa; --hover-bg: #282a2c;
        }
        [data-theme="light"] {
            --bg-color: #ffffff; --chat-bg: #ffffff; --sidebar-bg: #f0f4f9;
            --text-color: #1f1f1f; --bot-msg-bg: transparent; --bot-border: #e0e0e0;
            --user-msg-bg: #f0f4f9; --input-bg: #f0f4f9; --input-border: #ccc;
            --accent: #0b57d0; --hover-bg: #e1e5ea;
        }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: var(--bg-color); color: var(--text-color); margin: 0; height: 100vh; display: flex; overflow: hidden; transition: 0.4s; }
        .sidebar { width: 260px; background-color: var(--sidebar-bg); border-right: 1px solid var(--bot-border); display: flex; flex-direction: column; padding: 15px; z-index: 20;}
        .new-chat-btn { background-color: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); padding: 12px 15px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 20px;}
        .new-chat-btn:hover { border-color: var(--accent); }
        .history-list { display: flex; flex-direction: column; gap: 5px; overflow-y: auto; flex: 1; }
        .history-item { background: transparent; border: none; color: var(--text-color); padding: 10px; text-align: left; border-radius: 8px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .history-item:hover, .history-item.active { background-color: var(--hover-bg); }
        .history-item.active { border-left: 3px solid var(--accent); font-weight: bold;}
        .main-content { flex: 1; display: flex; flex-direction: column; }
        
        .header { background-color: var(--bg-color); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; z-index: 10; border-bottom: 1px solid var(--bot-border);}
        .header h2 { margin: 0; font-size: 20px; font-weight: 600;}
        .header-controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;}
        .ui-select, .theme-toggle, .btn-action { background: var(--hover-bg); border: 1px solid transparent; color: var(--text-color); padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; outline: none; transition: 0.2s;}
        .ui-select:hover, .btn-action:hover { border-color: var(--bot-border); }
        .btn-action.active { background: rgba(255, 82, 82, 0.1); color: #ff5252; border-color: #ff5252; font-weight: bold;}

        #chat-container { flex: 1; overflow-y: auto; padding: 20px 15%; display: flex; flex-direction: column; scroll-behavior: smooth; }
        .chips-container { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; width: 100%; max-width: 700px; margin: 0 auto; margin-top: 40px;}
        .chip { background-color: var(--hover-bg); border: 1px solid var(--bot-border); padding: 15px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 10px;}
        .chip:hover { border-color: var(--accent); }
        .message-wrapper { margin-bottom: 30px; display: flex; flex-direction: column; }
        .message { padding: 12px 20px; border-radius: 18px; max-width: 85%; line-height: 1.6; }
        .user-msg { background-color: var(--user-msg-bg); align-self: flex-end; border-bottom-right-radius: 4px; }
        .bot-msg { align-self: flex-start; border-radius: 0; width: 100%; max-width: 100%; padding: 0; }
        .bot-msg p { margin: 0 0 12px 0; }
        .bot-msg pre { background-color: #1e1e1e; padding: 35px 15px 15px; border-radius: 10px; color: #fff; position: relative; overflow-x: auto;}
        .bot-msg code { font-family: Consolas, monospace; color: var(--accent); }
        .copy-btn { position: absolute; top: 5px; right: 5px; background: #333; color: #fff; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .msg-actions { display: flex; gap: 8px; margin-top: 10px; }
        .action-icon { background: transparent; border: none; color: #888; cursor: pointer; padding: 6px; border-radius: 6px;}
        .action-icon:hover { background: var(--hover-bg); color: var(--text-color); }
        .spinner { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: var(--accent); border-radius: 50%; animation: spin 1s infinite; display: inline-block;}
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .listening { animation: pulse-mic 1.5s infinite; color: #ff5252 !important; }
        @keyframes pulse-mic { 50% { transform: scale(1.2); } }

        #input-container { padding: 20px 15%; background-color: var(--bg-color); }
        .input-wrapper { display: flex; background-color: var(--input-bg); border: 1px solid var(--input-border); border-radius: 30px; padding: 8px 15px; align-items: center; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
        .input-wrapper:focus-within { border-color: var(--accent); }
        input[type="text"] { flex: 1; padding: 12px 5px; border: none; background: transparent; color: var(--text-color); font-size: 16px; outline: none; }
        .action-btn { background: transparent; border: none; color: #888; font-size: 20px; cursor: pointer; padding: 10px; border-radius: 50%; }
        .action-btn:hover { background-color: var(--hover-bg); color: var(--text-color); }
        #send-btn { background-color: var(--accent); color: var(--bg-color); font-weight: bold; width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer; margin-left: 10px;}
        ::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-thumb { background: var(--bot-border); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <button class="new-chat-btn" onclick="yeniSohbet()">➕ Yeni Sohbet</button>
        <div style="font-size:12px; color:#888; margin-bottom:10px;">GEÇMİŞ SOHBETLER</div>
        <div class="history-list" id="sidebar-list"></div>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>✨ Kerem AI</h2>
            <div class="header-controls">
                <select id="ai-mode" class="ui-select" title="Yanıt Hızını Seç">
                    <option value="thinking">🧠 Düşünen Mod</option>
                    <option value="fast">⚡ Hızlı Mod</option>
                </select>
                <button id="voice-chat-btn" class="btn-action" onclick="toggleVoiceChat()" title="Kesintisiz otonom sohbet">🎙️ Sesli Sohbet: KAPALI</button>
                <button class="theme-toggle" onclick="temaDegistir()">☀️</button>
            </div>
        </div>
        
        <div id="chat-container">
            <div id="welcome-screen" style="text-align:center; padding-top:50px;">
                <h1 style="font-size:36px; margin-bottom:10px;">Ne keşfedelim?</h1>
                <div class="chips-container">
                    <div class="chip" onclick="hizliSor('AÖF ders notlarımı inceleyip benim için özet çıkarır mısın?')">📚 AÖF Ders Özeti Çıkar</div>
                    <div class="chip" onclick="hizliSor('Python kodumda hata alıyorum, mantık hatalarını nasıl ayıklayabilirim?')">💻 Python Hata Ayıklama</div>
                    <div class="chip" onclick="hizliSor('Bana Ammice Arapça (Suudi Arabistan) günlük diyalog kalıplarıyla pratik yaptır.')">🇸🇦 Ammice Arapça Pratik</div>
                    <div class="chip" onclick="hizliSor('Tell me a short story in English to improve my vocabulary.')">🇬🇧 İngilizce Pratik Yap</div>
                </div>
            </div>
        </div>
        
        <div id="input-container">
            <input type="file" id="file-input" style="display:none" accept="image/*, .pdf">
            <div class="input-wrapper">
                <button class="action-btn" onclick="document.getElementById('file-input').click()">📎</button>
                <input type="text" id="user-input" placeholder="Yaz veya mikrofon ikonuna basarak konuş..." onkeypress="if(event.key === 'Enter') mesajGonder()">
                <button class="action-btn" id="mic-btn">🎤</button>
                <button id="send-btn" onclick="mesajGonder()">➤</button>
            </div>
        </div>
    </div>

    <script>
        marked.setOptions({ breaks: true });
        
        let deviceId = localStorage.getItem("kerem_device_id");
        if (!deviceId) { deviceId = "user_" + Math.random().toString(36).substr(2, 9); localStorage.setItem("kerem_device_id", deviceId); }
        let currentSessionId = deviceId + "_" + Date.now();
        let isFirstMessage = true;

        let voiceChatMode = false;
        const micBtn = document.getElementById("mic-btn");
        const userInput = document.getElementById("user-input");
        let recognition;
        let isListening = false;

        function toggleVoiceChat() {
            voiceChatMode = !voiceChatMode;
            const btn = document.getElementById("voice-chat-btn");
            if(voiceChatMode) {
                btn.innerHTML = '🔴 Sesli Sohbet: AÇIK';
                btn.classList.add('active');
                if(recognition) { try { recognition.start(); } catch(e){} }
            } else {
                btn.innerHTML = '🎙️ Sesli Sohbet: KAPALI';
                btn.classList.remove('active');
                if(recognition) recognition.stop();
                window.speechSynthesis.cancel();
            }
        }

        // OTOMATİK DİL ALGILAMA MOTORU (TTS - Okuma İçin)
        function detectLanguage(text) {
            if (/[\u0600-\u06FF]/.test(text)) return 'ar-SA'; // Arapça harf tespiti
            const englishWords = ['the', 'and', 'you', 'is', 'a', 'to', 'it', 'that', 'with', 'for'];
            const words = text.toLowerCase().split(/\s+/);
            if (words.some(w => englishWords.includes(w))) return 'en-US'; // İngilizce kelime tespiti
            return 'tr-TR'; // Varsayılan Türkçe
        }

        function stripMarkdown(text) {
            return text.replace(/[*#`~_]/g, '');
        }

        function sesliOkuMetin(metin, autoRestartMic = false) {
            window.speechSynthesis.cancel();
            const temizMetin = stripMarkdown(metin);
            const s = new SpeechSynthesisUtterance(temizMetin);
            
            // Cevabın diline göre ses motorunu dinamik olarak eşleştirir
            s.lang = detectLanguage(temizMetin);
            
            s.onend = () => {
                if(voiceChatMode && autoRestartMic) {
                    setTimeout(() => { try { recognition.start(); } catch(e){} }, 300);
                }
            };
            s.onerror = () => { if(voiceChatMode && autoRestartMic) { try { recognition.start(); } catch(e){} } };
            window.speechSynthesis.speak(s);
        }

        // OTOMATİK DİL ALGILAMA (STT - Dinleme İçin kullanıcının cihaz dilini baz alır)
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = navigator.language || 'tr-TR'; // Cihaz dilini otomatik tanır
            
            recognition.onstart = () => { isListening = true; micBtn.classList.add("listening"); userInput.placeholder = "Dinliyorum..."; };
            recognition.onresult = (e) => { userInput.value = (userInput.value + " " + e.results[0][0].transcript).trim(); };
            
            recognition.onend = () => { 
                isListening = false; 
                micBtn.classList.remove("listening"); 
                userInput.placeholder = "Yaz veya mikrofon ikonuna basarak konuş..."; 
                
                if (userInput.value.trim() !== "") {
                    mesajGonder(); 
                } else if (voiceChatMode) {
                    setTimeout(() => { try { recognition.start(); } catch(e){} }, 300);
                }
            };
            
            micBtn.onclick = () => { 
                if (isListening) recognition.stop();
                else { try { recognition.start(); } catch(e){} }
            };
        } else { micBtn.style.display = "none"; }

        async function sohbetleriYukle() {
            try {
                const res = await fetch('/api/sohbetler?user_id=' + deviceId);
                const data = await res.json();
                const list = document.getElementById('sidebar-list');
                list.innerHTML = '';
                if(data.sohbetler.length===0) return list.innerHTML = '<div style="color:#888; font-size:13px; text-align:center;">Henüz sohbet yok.</div>';
                data.sohbetler.forEach(s => {
                    list.innerHTML += `<button class="history-item ${s.id===currentSessionId?'active':''}" onclick="sohbetAc('${s.id}', this)">${s.baslik}</button>`;
                });
            } catch(e) {}
        }
        window.onload = sohbetleriYukle;

        async function sohbetAc(id, btn) {
            currentSessionId = id; isFirstMessage = false;
            document.querySelectorAll('.history-item').forEach(b => b.classList.remove('active'));
            if(btn) btn.classList.add('active');
            const container = document.getElementById("chat-container");
            container.innerHTML = `<div style="text-align:center; padding: 20px;"><div class="spinner"></div> Yükleniyor...</div>`;
            try {
                const res = await fetch('/api/sohbet/' + id); const data = await res.json();
                container.innerHTML = '';
                data.mesajlar.forEach(msg => {
                    container.innerHTML += `<div class="message-wrapper"><div class="message ${msg.role==='user'?'user-msg':'bot-msg'}">${msg.role==='user'?msg.text:marked.parse(msg.text)}</div></div>`;
                });
                container.scrollTop = container.scrollHeight;
            } catch(e) { container.innerHTML = '<div style="color:#ff5252;">Hata oluştu.</div>'; }
        }

        function yeniSohbet() { location.reload(); }
        function hizliSor(metin) { userInput.value = metin; mesajGonder(); }
        function temaDegistir() { document.body.toggleAttribute('data-theme', 'light'); }

        async function daktiloEfekti(element, metin) {
            let i = 0; let anlik = "";
            return new Promise((resolve) => {
                const timer = setInterval(() => {
                    anlik += metin.charAt(i); element.innerHTML = marked.parse(anlik);
                    document.getElementById("chat-container").scrollTop = document.getElementById("chat-container").scrollHeight;
                    i++; if (i === metin.length) { clearInterval(timer); resolve(); }
                }, 15);
            });
        }

        async function mesajGonder() {
            const currentMsg = userInput.value;
            const fileInput = document.getElementById("file-input");
            if (!currentMsg.trim() && fileInput.files.length === 0) return;
            
            if (isFirstMessage) { document.getElementById("welcome-screen").style.display = "none"; }
            
            const chat = document.getElementById("chat-container");
            chat.innerHTML += `<div class="message-wrapper"><div class="message user-msg">${currentMsg}</div></div>`;
            
            const formData = new FormData();
            formData.append("mesaj", currentMsg);
            formData.append("session_id", currentSessionId); 
            formData.append("user_id", deviceId);
            if (fileInput.files.length > 0) formData.append("dosya", fileInput.files[0]);
            
            userInput.value = ""; fileInput.value = "";
            userInput.disabled = true; document.getElementById("send-btn").disabled = true;
            
            const typingId = "type-" + Date.now();
            chat.innerHTML += `<div class="message-wrapper"><div id="${typingId}" class="message bot-msg"><div class="spinner"></div> Yanıtlanıyor...</div></div>`;
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                const botBox = document.getElementById(typingId);
                
                if(voiceChatMode) { sesliOkuMetin(data.cevap, true); }
                
                await daktiloEfekti(botBox, data.cevap);
                
                botBox.innerHTML += `<div class="msg-actions"><button class="action-icon" onclick="sesliOkuMetin('${data.cevap.replace(/'/g, "\\'")}', false)">🔊 Dinle</button></div>`;
                if(isFirstMessage) { sohbetleriYukle(); isFirstMessage = false; }
            } catch (error) { document.getElementById(typingId).innerHTML = "Bağlantı hatası."; }
            
            userInput.disabled = false; document.getElementById("send-btn").disabled = false;
            if(!voiceChatMode) userInput.focus();
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

@app.route("/api/sohbetler", methods=["GET"])
def sohbetleri_getir():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify({"sohbetler": []})
    try:
        db_client = firestore.client()
        docs = db_client.collection("web_sohbetler").where("user_id", "==", user_id).stream()
        sohbetler = [{"id": d.id, "baslik": d.to_dict().get("baslik", "Yeni")} for d in docs]
        sohbetler.sort(key=lambda x: x["id"], reverse=True)
        return jsonify({"sohbetler": sohbetler[:15]})
    except: return jsonify({"sohbetler": []})

@app.route("/api/sohbet/<session_id>", methods=["GET"])
def sohbet_getir(session_id):
    try:
        doc = firestore.client().collection("web_sohbetler").document(session_id).get()
        return jsonify({"mesajlar": doc.to_dict().get("mesajlar", []) if doc.exists else []})
    except: return jsonify({"mesajlar": []})

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj, session_id, user_id = request.form.get("mesaj", ""), request.form.get("session_id", ""), request.form.get("user_id", "")
    dosya_yolu = None
    if 'dosya' in request.files and request.files['dosya'].filename:
        dosya_yolu = os.path.join(UPLOAD_FOLDER, secure_filename(request.files['dosya'].filename))
        request.files['dosya'].save(dosya_yolu)
    
    cevap = ask_ai(mesaj, user_id=session_id, image_path=dosya_yolu)
    if dosya_yolu and os.path.exists(dosya_yolu): os.remove(dosya_yolu)

    try:
        doc_ref = firestore.client().collection("web_sohbetler").document(session_id)
        if not doc_ref.get().exists: doc_ref.set({"baslik": mesaj[:25], "user_id": user_id, "mesajlar": []})
        doc_ref.update({"mesajlar": firestore.ArrayUnion([{"role": "user", "text": mesaj}, {"role": "bot", "text": cevap}])})
    except: pass
    return jsonify({"cevap": cevap})

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app_telegram = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    
    async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(ask_ai(update.message.text, str(update.message.from_user.id)))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app_telegram.run_polling(stop_signals=None)

if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
