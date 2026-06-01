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
            --bg-color: #131314; 
            --chat-bg: #131314; 
            --sidebar-bg: #1e1e20;
            --text-color: #e3e3e3; 
            --bot-msg-bg: transparent; 
            --bot-border: #333;
            --user-msg-bg: #303030; 
            --input-bg: #1e1e20; 
            --input-border: #444;
            --accent: #a8c7fa; 
            --hover-bg: #282a2c;
        }
        [data-theme="light"] {
            --bg-color: #ffffff; 
            --chat-bg: #ffffff; 
            --sidebar-bg: #f0f4f9;
            --text-color: #1f1f1f; 
            --bot-msg-bg: transparent; 
            --bot-border: #e0e0e0;
            --user-msg-bg: #f0f4f9; 
            --input-bg: #f0f4f9; 
            --input-border: #ccc;
            --accent: #0b57d0; 
            --hover-bg: #e1e5ea;
        }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background-color: var(--bg-color); 
            color: var(--text-color); 
            margin: 0; 
            height: 100vh; 
            display: flex; 
            overflow: hidden; 
            transition: background-color 0.3s, color 0.3s; 
        }
        
        /* Sol Menü (Sidebar) */
        .sidebar { width: 260px; background-color: var(--sidebar-bg); border-right: 1px solid var(--bot-border); display: flex; flex-direction: column; padding: 15px; z-index: 20;}
        .new-chat-btn { background-color: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); padding: 12px 15px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 20px; transition: 0.2s;}
        .new-chat-btn:hover { border-color: var(--accent); }
        .history-list { display: flex; flex-direction: column; gap: 5px; overflow-y: auto; flex: 1; }
        .history-item { background: transparent; border: none; color: var(--text-color); padding: 10px; text-align: left; border-radius: 8px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: 0.2s; }
        .history-item:hover, .history-item.active { background-color: var(--hover-bg); }
        .history-item.active { border-left: 3px solid var(--accent); font-weight: bold;}
        
        /* Ana İçerik Alanı */
        .main-content { flex: 1; display: flex; flex-direction: column; background-color: var(--chat-bg); position: relative; }
        
        .header { background-color: var(--bg-color); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; z-index: 10; border-bottom: 1px solid var(--bot-border); transition: background-color 0.3s; }
        .header h2 { margin: 0; font-size: 20px; font-weight: 600;}
        .header-controls { display: flex; gap: 10px; align-items: center;}
        
        .theme-toggle, .btn-action { background: var(--hover-bg); border: 1px solid transparent; color: var(--text-color); padding: 8px 14px; border-radius: 20px; cursor: pointer; font-size: 13px; outline: none; transition: 0.2s;}
        .theme-toggle:hover, .btn-action:hover { border-color: var(--input-border); }
        .btn-action.active { background: rgba(255, 82, 82, 0.15); color: #ff5252; border-color: #ff5252; font-weight: bold;}

        #chat-container { flex: 1; overflow-y: auto; padding: 20px 15%; display: flex; flex-direction: column; scroll-behavior: smooth; }
        .chips-container { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; width: 100%; max-width: 700px; margin: 0 auto; margin-top: 40px;}
        .chip { background-color: var(--hover-bg); border: 1px solid var(--bot-border); padding: 15px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 10px; color: var(--text-color); text-align: left; transition: 0.2s;}
        .chip:hover { border-color: var(--accent); background-color: var(--input-bg); }
        
        .message-wrapper { margin-bottom: 30px; display: flex; flex-direction: column; }
        .message { padding: 12px 20px; border-radius: 18px; max-width: 85%; line-height: 1.6; font-size: 16px; }
        .user-msg { background-color: var(--user-msg-bg); align-self: flex-end; border-bottom-right-radius: 4px; color: var(--text-color); }
        .bot-msg { align-self: flex-start; border-radius: 0; width: 100%; max-width: 100%; padding: 0; color: var(--text-color); }
        .bot-msg p { margin: 0 0 12px 0; }
        .bot-msg pre { background-color: #1e1e1e; padding: 35px 15px 15px; border-radius: 10px; color: #fff; position: relative; overflow-x: auto;}
        .bot-msg code { font-family: Consolas, monospace; color: var(--accent); }
        
        .msg-actions { display: flex; gap: 8px; margin-top: 10px; }
        .action-icon { background: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); cursor: pointer; padding: 6px 12px; border-radius: 12px; font-size: 13px; transition: 0.2s;}
        .action-icon:hover { border-color: var(--accent); }
        
        .spinner { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: var(--accent); border-radius: 50%; animation: spin 1s infinite; display: inline-block;}
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .listening { animation: pulse-mic 1.5s infinite; color: #ff5252 !important; }
        @keyframes pulse-mic { 50% { transform: scale(1.2); } }

        /* --- MÜKEMMEL GEMINI KAPSÜL GİRİŞ ALANI --- */
        #input-container { padding: 10px 15% 25px 15%; background-color: var(--bg-color); display: flex; flex-direction: column; align-items: center; transition: background-color 0.3s; }
        .input-capsule { display: flex; background-color: var(--input-bg); border: 1px solid var(--input-border); border-radius: 35px; padding: 6px 14px 6px 20px; align-items: center; width: 100%; max-width: 750px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: 0.3s; }
        .input-capsule:focus-within { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); background-color: var(--bg-color); }
        
        .capsule-btn { background: transparent; border: none; color: var(--text-color); font-size: 22px; cursor: pointer; padding: 8px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: 0.2s; opacity: 0.8; }
        .capsule-btn:hover { background-color: var(--hover-bg); opacity: 1; }
        
        input[type="text"] { flex: 1; padding: 12px 15px; border: none; background: transparent; color: var(--text-color); font-size: 16px; outline: none; }
        input[type="text"]::placeholder { color: #888; }
        
        /* Kapsül İçi Mod Seçici Dropdown */
        .capsule-select { background: transparent; border: none; color: var(--text-color); padding: 8px 12px; cursor: pointer; font-size: 14px; outline: none; font-weight: 500; transition: 0.2s; border-radius: 20px; margin-right: 5px; }
        .capsule-select:hover { background-color: var(--hover-bg); }
        .capsule-select option { background-color: var(--input-bg); color: var(--text-color); }
        
        /* Alt Uyarı Yazısı */
        .disclaimer-text { font-size: 12px; color: #888; margin-top: 10px; text-align: center; width: 100%; letter-spacing: 0.3px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <button class="new-chat-btn" onclick="yeniSohbet()">➕ Yeni Sohbet</button>
        <div style="font-size:12px; color:#888; margin-bottom:10px; font-weight:bold; padding-left:5px;">GEÇMİŞ SOHBETLER</div>
        <div class="history-list" id="sidebar-list"></div>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>✨ Kerem AI</h2>
            <div class="header-controls">
                <button id="voice-chat-btn" class="btn-action" onclick="toggleVoiceChat()" title="Kesintisiz otonom sohbet">🎙️ Sesli Sohbet: KAPALI</button>
                <button id="theme-btn" class="theme-toggle" onclick="temaDegistir()">☀️</button>
            </div>
        </div>
        
        <div id="chat-container">
            <div id="welcome-screen" style="text-align:center; padding-top:50px;">
                <h1 style="font-size:38px; margin-bottom:10px; font-weight:600; background: linear-gradient(45deg, #a8c7fa, #ffb6c1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Merhaba, bugün ne keşfedelim?</h1>
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
            <div class="input-capsule">
                <button class="capsule-btn" onclick="document.getElementById('file-input').click()" title="Dosya veya Görsel Ekle">＋</button>
                
                <input type="text" id="user-input" placeholder="Kerem'e bir şey sor..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
                
                <select id="ai-mode" class="capsule-select" title="Yanıt Hızını Seç">
                    <option value="thinking">🧠 Düşünen Mod</option>
                    <option value="fast">⚡ Hızlı Mod</option>
                </select>
                
                <button class="capsule-btn" id="mic-btn" title="Sesli Konuş">🎤</button>
            </div>
            <div class="disclaimer-text">Kerem AI bir yapay zeka modeli olduğu için hata yapabilir.</div>
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
        let otonomSpeechLang = 'tr-TR';

        // --- TEMA DEGISTIRICI ---
        const kaydedilenTema = localStorage.getItem("kerem_theme") || "dark";
        if (kaydedilenTema === "light") {
            document.body.setAttribute('data-theme', 'light');
            document.getElementById("theme-btn").innerHTML = '🌙';
        } else {
            document.body.removeAttribute('data-theme');
            document.getElementById("theme-btn").innerHTML = '☀️';
        }

        function temaDegistir() {
            const body = document.body;
            const btn = document.getElementById("theme-btn");
            if (body.hasAttribute('data-theme')) {
                body.removeAttribute('data-theme');
                btn.innerHTML = '☀️';
                localStorage.setItem("kerem_theme", "dark");
            } else {
                body.setAttribute('data-theme', 'light');
                btn.innerHTML = '🌙';
                localStorage.setItem("kerem_theme", "light");
            }
        }

        function toggleVoiceChat() {
            voiceChatMode = !voiceChatMode;
            const btn = document.getElementById("voice-chat-btn");
            if(voiceChatMode) {
                btn.innerHTML = '🔴 Sesli Sohbet: AÇIK';
                btn.classList.add('active');
                if(recognition) { try { recognition.lang = otonomSpeechLang; recognition.start(); } catch(e){} }
            } else {
                btn.innerHTML = '🎙️ Sesli Sohbet: KAPALI';
                btn.classList.remove('active');
                if(recognition) recognition.stop();
                window.speechSynthesis.cancel();
            }
        }

        function detectLanguage(text) {
            if (/[\u0600-\u06FF]/.test(text)) return 'ar-SA';
            const englishWords = ['the', 'and', 'you', 'is', 'a', 'to', 'it', 'that', 'with', 'for', 'story', 'what', 'how'];
            const words = text.toLowerCase().split(/\s+/);
            if (words.some(w => englishWords.includes(w))) return 'en-US';
            return 'tr-TR';
        }

        function stripMarkdown(text) {
            return text.replace(/[*#`~_]/g, '');
        }

        function sesliOkuMetin(metin, autoRestartMic = false) {
            window.speechSynthesis.cancel();
            const temizMetin = stripMarkdown(metin);
            const s = new SpeechSynthesisUtterance(temizMetin);
            
            otonomSpeechLang = detectLanguage(temizMetin);
            s.lang = otonomSpeechLang;
            
            s.onend = () => {
                if(voiceChatMode && autoRestartMic) {
                    setTimeout(() => { try { recognition.lang = otonomSpeechLang; recognition.start(); } catch(e){} }, 300);
                }
            };
            s.onerror = () => { if(voiceChatMode && autoRestartMic) { try { recognition.start(); } catch(e){} } };
            window.speechSynthesis.speak(s);
        }

        function sesliOkuElement(btn) {
            const wrapper = btn.closest('.message-wrapper');
            const botMsg = wrapper.querySelector('.bot-msg');
            if (botMsg) {
                const textToRead = botMsg.innerText.replace(/🔊 Dinle/g, "").trim();
                sesliOkuMetin(textToRead, false);
            }
        }

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            
            recognition.lang = navigator.language || 'tr-TR';
            recognition.continuous = false;
            recognition.interimResults = true; 
            
            recognition.onstart = () => { 
                isListening = true; 
                micBtn.classList.add("listening"); 
                userInput.placeholder = "Dinliyorum, konuşun..."; 
            };
            
            recognition.onresult = (e) => { 
                let interimTranscript = '';
                let finalTranscript = '';
                for (let i = e.resultIndex; i < e.results.length; ++i) {
                    if (e.results[i].isFinal) {
                        finalTranscript += e.results[i][0].transcript;
                    } else {
                        interimTranscript += e.results[i][0].transcript;
                    }
                }
                if(finalTranscript) {
                    userInput.value = (userInput.value + " " + finalTranscript).trim();
                } else if(interimTranscript) {
                    userInput.placeholder = interimTranscript; 
                }
            };
            
            recognition.onend = () => { 
                isListening = false; 
                micBtn.classList.remove("listening"); 
                userInput.placeholder = "Kerem'e bir şey sor..."; 
                
                if (userInput.value.trim() !== "") {
                    mesajGonder(); 
                } else if (voiceChatMode) {
                    setTimeout(() => { try { recognition.lang = otonomSpeechLang; recognition.start(); } catch(e){} }, 300);
                }
            };
            
            micBtn.onclick = () => { 
                if (isListening) recognition.stop();
                else { try { recognition.lang = otonomSpeechLang; recognition.start(); } catch(e){} }
            };
        } else { micBtn.style.display = "none"; }

        async function sohbetleriYukle() {
            try {
                const res = await fetch('/api/sohbetler?user_id=' + deviceId);
                const data = await res.json();
                const list = document.getElementById('sidebar-list');
                list.innerHTML = '';
                if(data.sohbetler.length===0) return list.innerHTML = '<div style="color:#888; font-size:13px; text-align:center; margin-top:20px;">Henüz sohbet yok.</div>';
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
                if(data.mesajlar.length > 0) {
                    otonomSpeechLang = detectLanguage(data.mesajlar[data.mesajlar.length - 1].text);
                }
                container.scrollTop = container.scrollHeight;
            } catch(e) { container.innerHTML = '<div style="color:#ff5252;">Hata oluştu.</div>'; }
        }

        function yeniSohbet() { location.reload(); }
        function hizliSor(metin) { userInput.value = metin; mesajGonder(); }

        async function daktiloEfekti(element, metin) {
            let i = 0; let anlik = "";
            return new Promise((resolve) => {
                const timer = setInterval(() => {
                    anlik += metin.charAt(i); element.innerHTML = marked.parse(anlik);
                    document.getElementById("chat-container").scrollTop = document.getElementById("chat-container").scrollHeight;
                    i++; if (i === metin.length) { clearInterval(timer); resolve(); }
                }, 12);
            });
        }

        async function mesajGonder() {
            const currentMsg = userInput.value;
            const fileInput = document.getElementById("file-input");
            if (!currentMsg.trim() && fileInput.files.length === 0) return;
            
            if (isFirstMessage) { document.getElementById("welcome-screen").style.display = "none"; }
            
            const chat = document.getElementById("chat-container");
            chat.innerHTML += `<div class="message-wrapper"><div class="message user-msg">${currentMsg}</div></div>`;
            
            otonomSpeechLang = detectLanguage(currentMsg);
            
            const formData = new FormData();
            formData.append("mesaj", currentMsg);
            formData.append("session_id", currentSessionId); 
            formData.append("user_id", deviceId);
            if (fileInput.files.length > 0) formData.append("dosya", fileInput.files[0]);
            
            userInput.value = ""; fileInput.value = "";
            userInput.disabled = true;
            
            const aiMode = document.getElementById("ai-mode").value;
            const waitingText = aiMode === "fast" ? "Hızla yanıtlanıyor..." : "Kerem düşünüyor...";
            
            const typingId = "type-" + Date.now();
            chat.innerHTML += `<div class="message-wrapper"><div id="${typingId}" class="message bot-msg"><div class="spinner"></div> ${waitingText}</div></div>`;
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                const botBox = document.getElementById(typingId);
                
                otonomSpeechLang = detectLanguage(data.cevap);
                
                if(voiceChatMode) { sesliOkuMetin(data.cevap, true); }
                
                botBox.innerHTML = "";
                await daktiloEfekti(botBox, data.cevap);
                
                botBox.innerHTML += `<div class="msg-actions"><button class="action-icon" onclick="sesliOkuElement(this)">🔊 Dinle</button></div>`;
                if(isFirstMessage) { sohbetleriYukle(); isFirstMessage = false; }
            } catch (error) { document.getElementById(typingId).innerHTML = "Bağlantı hatası."; }
            
            userInput.disabled = false;
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
