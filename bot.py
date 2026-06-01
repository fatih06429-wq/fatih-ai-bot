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
            --icon-color: #e3e3e3;
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
            --icon-color: #444746;
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
        
        .sidebar { width: 260px; background-color: var(--sidebar-bg); border-right: 1px solid var(--bot-border); display: flex; flex-direction: column; padding: 15px; z-index: 20;}
        .new-chat-btn { background-color: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); padding: 12px 15px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 20px; transition: 0.2s; width: 100%; box-sizing: border-box;}
        .new-chat-btn:hover { border-color: var(--accent); }
        .history-list { display: flex; flex-direction: column; gap: 5px; overflow-y: auto; flex: 1; }
        
        /* Geçmiş Sohbet Satırı ve Silme Butonu Uyumu */
        .history-row { display: flex; align-items: center; justify-content: space-between; border-radius: 8px; transition: 0.2s; padding-right: 5px; }
        .history-row:hover, .history-row.active { background-color: var(--hover-bg); }
        .history-item { background: transparent; border: none; color: var(--text-color); padding: 10px; text-align: left; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; font-size: 14px; }
        .history-row.active .history-item { font-weight: bold; border-left: 3px solid var(--accent); border-radius: 0; }
        .delete-btn { background: transparent; border: none; color: #ff5252; cursor: pointer; opacity: 0; transition: 0.2s; padding: 8px; display: flex; align-items: center; justify-content: center; border-radius: 6px; }
        .history-row:hover .delete-btn { opacity: 0.7; }
        .delete-btn:hover { opacity: 1 !important; background-color: rgba(255, 82, 82, 0.1); }

        .main-content { flex: 1; display: flex; flex-direction: column; background-color: var(--chat-bg); position: relative; }
        .header { background-color: var(--bg-color); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; z-index: 10; border-bottom: 1px solid var(--bot-border); transition: background-color 0.3s; }
        .header h2 { margin: 0; font-size: 20px; font-weight: 600;}
        .header-controls { display: flex; gap: 10px; align-items: center;}
        .theme-toggle { background: var(--hover-bg); border: 1px solid transparent; color: var(--text-color); padding: 8px 14px; border-radius: 20px; cursor: pointer; font-size: 13px; outline: none; transition: 0.2s;}
        .theme-toggle:hover { border-color: var(--input-border); }

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

        #input-container { padding: 10px 15% 25px 15%; background-color: var(--bg-color); display: flex; flex-direction: column; align-items: center; transition: background-color 0.3s; }
        .input-capsule { display: flex; background-color: var(--input-bg); border: 1px solid var(--input-border); border-radius: 35px; padding: 6px 14px 6px 14px; align-items: center; width: 100%; max-width: 750px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: 0.3s; }
        .input-capsule:focus-within { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); background-color: var(--bg-color); }
        
        .capsule-btn { background: transparent; border: none; color: var(--icon-color); cursor: pointer; padding: 10px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: 0.2s; opacity: 0.7; }
        .capsule-btn:hover { background-color: var(--hover-bg); opacity: 1; }
        
        input[type="text"] { flex: 1; padding: 12px 15px; border: none; background: transparent; color: var(--text-color); font-size: 16px; outline: none; }
        input[type="text"]::placeholder { color: #888; }
        
        .capsule-select { background: transparent; border: none; color: var(--text-color); padding: 8px 12px; cursor: pointer; font-size: 14px; outline: none; font-weight: 500; transition: 0.2s; border-radius: 20px; margin-right: 5px; }
        .capsule-select:hover { background-color: var(--hover-bg); }
        .capsule-select option { background-color: var(--input-bg); color: var(--text-color); }
        
        .disclaimer-text { font-size: 12px; color: #888; margin-top: 10px; text-align: center; width: 100%; letter-spacing: 0.3px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <button class="new-chat-btn" onclick="yeniSohbet()">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg> 
            Yeni Sohbet
        </button>
        <div style="font-size:12px; color:#888; margin-bottom:10px; font-weight:bold; padding-left:5px;">GEÇMİŞ SOHBETLER</div>
        <div class="history-list" id="sidebar-list"></div>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>✨ Kerem AI</h2>
            <div class="header-controls">
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
                <button class="capsule-btn" onclick="document.getElementById('file-input').click()" title="Dosya veya Görsel Ekle">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                </button>
                
                <input type="text" id="user-input" placeholder="Kerem'e bir şey sor..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
                
                <select id="ai-mode" class="capsule-select" title="Yanıt Hızını Seç">
                    <option value="thinking">🧠 Düşünen Mod</option>
                    <option value="fast">⚡ Hızlı Mod</option>
                </select>
                
                <button class="capsule-btn" id="mic-btn" title="Sesli Konuş">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg>
                </button>
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

        const micBtn = document.getElementById("mic-btn");
        const userInput = document.getElementById("user-input");
        let recognition;
        let isListening = false;
        let isSpeaking = false;
        let currentSpeakingBtn = null;

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

        function detectLanguage(text) {
            if (/[\u0600-\u06FF]/.test(text)) return 'ar-SA';
            const englishWords = ['the', 'and', 'you', 'is', 'a', 'to', 'it', 'that', 'with', 'for'];
            const words = text.toLowerCase().split(/\s+/);
            if (words.some(w => englishWords.includes(w))) return 'en-US';
            return 'tr-TR';
        }

        function stripMarkdown(text) {
            return text.replace(/[*#`~_]/g, '');
        }

        function sesliOkuElement(btn) {
            const wrapper = btn.closest('.message-wrapper');
            const botMsg = wrapper.querySelector('.bot-msg');
            
            if (isSpeaking && currentSpeakingBtn === btn) {
                window.speechSynthesis.cancel();
                btn.innerHTML = '🔊 Dinle';
                isSpeaking = false;
                currentSpeakingBtn = null;
                return;
            }

            window.speechSynthesis.cancel();
            document.querySelectorAll('.btn-dinle').forEach(b => b.innerHTML = '🔊 Dinle');

            if (botMsg) {
                const textToRead = botMsg.innerText.replace(/🔊 Dinle/g, "").replace(/⏹️ Durdur/g, "").trim();
                btn.innerHTML = '⏹️ Durdur';
                isSpeaking = true;
                currentSpeakingBtn = btn;

                const s = new SpeechSynthesisUtterance(stripMarkdown(textToRead));
                s.lang = detectLanguage(textToRead);
                s.onend = () => { btn.innerHTML = '🔊 Dinle'; isSpeaking = false; currentSpeakingBtn = null; };
                s.onerror = () => { btn.innerHTML = '🔊 Dinle'; isSpeaking = false; currentSpeakingBtn = null; };
                window.speechSynthesis.speak(s);
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
                if (userInput.value.trim() !== "") mesajGonder(); 
            };
            
            micBtn.onclick = () => { 
                if (isListening) recognition.stop();
                else { try { recognition.start(); } catch(e){} }
            };
        } else { micBtn.style.display = "none"; }

        // SOHBETLERİ SİLME DESTEKLİ SIDEBAR YÜKLEYİCİ
        async function sohbetleriYukle() {
            try {
                const res = await fetch('/api/sohbetler?user_id=' + deviceId);
                const data = await res.json();
                const list = document.getElementById('sidebar-list');
                list.innerHTML = '';
                if(data.sohbetler.length===0) return list.innerHTML = '<div style="color:#888; font-size:13px; text-align:center; margin-top:20px;">Henüz sohbet yok.</div>';
                
                data.sohbetler.forEach(s => {
                    const row = document.createElement('div');
                    row.className = `history-row ${s.id===currentSessionId?'active':''}`;
                    row.innerHTML = `
                        <button class="history-item" onclick="sohbetAc('${s.id}', this.parentElement)">${s.baslik}</button>
                        <button class="delete-btn" onclick="sohbetSil('${s.id}', event)" title="Sohbeti Kalıcı Olarak Sil">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                        </button>
                    `;
                    list.appendChild(row);
                });
            } catch(e) {}
        }
        window.onload = sohbetleriYukle;

        // KALICI SOHBET SİLME FONKSİYONU (BELLEK BOŞALTICI)
        async function sohbetSil(sessionId, event) {
            event.stopPropagation(); // Satır tıklama olayını engelle
            if(!confirm("Bu sohbet geçmişini kalıcı olarak silmek ve belleği boşaltmak istiyor musunuz?")) return;
            
            try {
                const res = await fetch(`/api/sohbet/sil?session_id=${sessionId}`, { method: 'DELETE' });
                const data = await res.json();
                if(data.status === "success") {
                    if(currentSessionId === sessionId) {
                        yeniSohbet();
                    } else {
                        sohbetleriYukle();
                    }
                }
            } catch(e) { alert("Silme işlemi sırasında bir hata oluştu."); }
        }

        async function sohbetAc(id, rowElement) {
            currentSessionId = id; isFirstMessage = false;
            document.querySelectorAll('.history-row').forEach(r => r.classList.remove('active'));
            if(rowElement) rowElement.classList.add('active');
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
                
                botBox.innerHTML = "";
                await daktiloEfekti(botBox, data.cevap);
                
                botBox.innerHTML += `<div class="msg-actions"><button class="action-icon btn-dinle" onclick="sesliOkuElement(this)">🔊 Dinle</button></div>`;
                if(isFirstMessage) { sohbetleriYukle(); isFirstMessage = false; }
            } catch (error) { document.getElementById(typingId).innerHTML = "Bağlantı hatası."; }
            
            userInput.disabled = false;
            userInput.focus();
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

# KALICI SİLME ENDPOINT'İ (FIREBASE SİLİCİ)
@app.route("/api/sohbet/sil", methods=["DELETE"])
def sohbet_sil():
    session_id = request.args.get("session_id")
    if not session_id: return jsonify({"status": "error", "message": "Missing session_id"}), 400
    try:
        db_client = firestore.client()
        db_client.collection("web_sohbetler").document(session_id).delete()
        # Kısa süreli yapay zeka ram hafızasını da uçur
        hafizayi_temizle(session_id)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

# --- GÜNCEL ÇOK KULLANICILI VE RAG DESTEKLİ TELEGRAM MOTORU ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await update.message.reply_text("✨ Kerem AI Telegram Merkezine Hoş Geldin! Bana normal mesaj yazabilir veya PDF dökümanı göndererek hafızama almamı sağlayabilirsin.")

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    hafizayi_temizle(user_id)
    await update.message.reply_text("🧹 Kısa süreli Telegram sohbet hafızam tamamen temizlendi!")

async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    caption = update.message.caption if update.message.caption else "Bu belgeyi analiz et."
    bekleme = await update.message.reply_text("📥 Belge derin öğrenme hafızama alınıyor, lütfen bekleyin...")
    
    dosya_adi = f"tg_doc_{user_id}_{Date.now()}.pdf"
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        await file.download_to_drive(dosya_adi)
        reply = ask_ai(caption, user_id, image_path=dosya_adi)
        await bekleme.edit_text(reply)
    except Exception as e:
        await bekleme.edit_text(f"Dosya işleme hatası: {e}")
    finally:
        if os.path.exists(dosya_adi): os.remove(dosya_adi)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    user_id = f"tg_{update.message.from_user.id}"
    reply = ask_ai(update.message.text, user_id)
    await update.message.reply_text(reply)

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app_telegram = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("temizle", temizle_command))
    app_telegram.add_handler(MessageHandler(filters.Document.PDF, dosya_al))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app_telegram.run_polling(stop_signals=None)

if __name__ == '__main__':
    threading.Thread(target=run_telegram_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
