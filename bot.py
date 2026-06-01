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

# --- FLASK WEB SUNUCUSU ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# TAM EKRAN GEMINI PRO ARAYÜZÜ + FIREBASE SİDEBAR (GEÇMİŞ SOHBETLER)
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
            --chat-bg: #1e1e20;
            --sidebar-bg: #1e1e20;
            --text-color: #e3e3e3;
            --bot-msg-bg: transparent;
            --bot-border: #333;
            --user-msg-bg: #303030;
            --input-bg: #1e1e20;
            --input-border: #444;
            --accent: #a8c7fa;
            --hover-bg: #282a2c;
            --header-shadow: rgba(0,0,0,0.4);
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
            --header-shadow: rgba(0,0,0,0.05);
        }

        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg-color); color: var(--text-color); margin: 0; padding: 0; height: 100vh; display: flex; overflow: hidden; transition: background-color 0.4s, color 0.4s; }
        
        /* Sol Menü (Sidebar) */
        .sidebar { width: 260px; background-color: var(--sidebar-bg); border-right: 1px solid var(--bot-border); display: flex; flex-direction: column; padding: 15px; transition: 0.3s; z-index: 20;}
        .new-chat-btn { background-color: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); padding: 12px 15px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 15px; margin-bottom: 20px; transition: 0.2s;}
        .new-chat-btn:hover { border-color: var(--accent); }
        .history-title { font-size: 12px; color: #888; margin-bottom: 10px; padding-left: 5px; text-transform: uppercase; font-weight: bold;}
        .history-list { display: flex; flex-direction: column; gap: 5px; overflow-y: auto; flex: 1; }
        .history-item { background: transparent; border: none; color: var(--text-color); padding: 10px; text-align: left; border-radius: 8px; cursor: pointer; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; transition: 0.2s; }
        .history-item:hover { background-color: var(--hover-bg); }
        .history-item.active { background-color: var(--hover-bg); border-left: 3px solid var(--accent); border-radius: 4px; font-weight: bold;}

        /* Ana İçerik */
        .main-content { flex: 1; display: flex; flex-direction: column; position: relative; }
        
        .header { background-color: var(--bg-color); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; z-index: 10; }
        .header h2 { margin: 0; color: var(--text-color); font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 10px;}
        .header-controls { display: flex; gap: 10px; }
        .ui-select, .theme-toggle { background: var(--hover-bg); border: 1px solid transparent; color: var(--text-color); padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 14px; transition: 0.3s; outline: none; }
        .ui-select:hover, .theme-toggle:hover { border-color: var(--bot-border); }

        #chat-container { flex: 1; overflow-y: auto; padding: 20px 15%; display: flex; flex-direction: column; scroll-behavior: smooth; }
        
        /* Hoş Geldin Kartları (Prompt Chips) */
        #welcome-screen { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; padding-bottom: 50px; }
        .greeting { font-size: 42px; font-weight: 600; background: -webkit-linear-gradient(45deg, #a8c7fa, #ffb6c1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 40px; text-align: center; }
        .chips-container { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; max-width: 700px; width: 100%; }
        .chip { background-color: var(--hover-bg); border: 1px solid var(--bot-border); padding: 15px 20px; border-radius: 12px; color: var(--text-color); cursor: pointer; text-align: left; font-size: 15px; transition: 0.2s; display: flex; align-items: center; gap: 10px;}
        .chip:hover { background-color: var(--input-bg); transform: translateY(-2px); border-color: var(--accent); }

        /* Mesaj Tasarımları */
        .message-wrapper { margin-bottom: 30px; display: flex; flex-direction: column; }
        .message { padding: 12px 20px; border-radius: 18px; max-width: 85%; line-height: 1.6; font-size: 16px; }
        .user-msg { background-color: var(--user-msg-bg); color: var(--text-color); align-self: flex-end; border-bottom-right-radius: 4px; }
        .bot-msg { background-color: var(--bot-msg-bg); align-self: flex-start; border-radius: 0; width: 100%; max-width: 100%; padding: 0 20px; }
        
        /* Markdown & Kod Blokları */
        .bot-msg p { margin: 0 0 12px 0; }
        .bot-msg p:last-child { margin: 0; }
        .bot-msg code { background-color: var(--hover-bg); padding: 4px 8px; border-radius: 6px; font-family: Consolas, monospace; color: var(--accent); font-size: 14px; }
        .bot-msg pre { background-color: #1e1e1e; padding: 40px 15px 15px 15px; border-radius: 10px; overflow-x: auto; color: #fff; position: relative; margin-top: 15px; }
        .copy-btn { position: absolute; top: 8px; right: 8px; background: #333; color: #fff; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: 0.2s; }
        .copy-btn:hover { background: #555; }
        
        /* Aksiyon Çubuğu */
        .msg-actions { display: flex; gap: 8px; margin-top: 10px; margin-left: 20px; }
        .action-icon { background: transparent; border: none; color: #888; font-size: 16px; cursor: pointer; padding: 6px 10px; border-radius: 6px; transition: 0.2s; display: flex; align-items: center; gap: 5px;}
        .action-icon:hover { background: var(--hover-bg); color: var(--text-color); }

        /* Animasyonlar */
        .thinking { display: flex; align-items: center; gap: 8px; font-style: italic; color: #888; font-size: 14px; margin-left: 20px;}
        .spinner { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse-mic { 0% { transform: scale(1); } 50% { transform: scale(1.2); color: #ff5252; } 100% { transform: scale(1); } }
        .listening { animation: pulse-mic 1.5s infinite; color: #ff5252 !important; }

        /* Modern Giriş Alanı */
        #input-container { padding: 20px 15%; background-color: var(--bg-color); z-index: 10; }
        .input-wrapper { display: flex; background-color: var(--input-bg); border: 1px solid var(--input-border); border-radius: 30px; padding: 8px 15px; align-items: center; transition: 0.3s; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
        .input-wrapper:focus-within { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); background-color: var(--chat-bg);}
        input[type="text"] { flex: 1; padding: 12px 5px; border: none; background: transparent; color: var(--text-color); font-size: 16px; outline: none; }
        .action-btn { background: transparent; border: none; color: #888; font-size: 20px; cursor: pointer; padding: 10px; border-radius: 50%; transition: 0.2s; display: flex; align-items: center; justify-content: center; }
        .action-btn:hover { background-color: var(--hover-bg); color: var(--text-color); }
        #send-btn { background-color: var(--accent); color: var(--bg-color); font-weight: bold; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; transition: 0.3s; margin-left: 10px;}
        #send-btn:hover { transform: scale(1.05); filter: brightness(1.1); }
        #send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--bot-border); border-radius: 4px; }
    </style>
</head>
<body>
    
    <div class="sidebar">
        <button class="new-chat-btn" onclick="yeniSohbet()">➕ Yeni Sohbet</button>
        <div class="history-title">Geçmiş Sohbetler</div>
        <div class="history-list" id="sidebar-list">
            <div style="color:#888; font-size:13px; text-align:center; margin-top:20px;">Yükleniyor...</div>
        </div>
    </div>

    <div class="main-content">
        <div class="header">
            <h2>✨ Kerem AI</h2>
            <div class="header-controls">
                <select id="ai-mode" class="ui-select" title="Yanıt Hızını Seç">
                    <option value="thinking">🧠 Düşünen Mod</option>
                    <option value="fast">⚡ Hızlı Mod</option>
                </select>
                <button class="theme-toggle" onclick="temaDegistir()">☀️</button>
            </div>
        </div>
        
        <div id="chat-container">
            <div id="welcome-screen">
                <div class="greeting">Merhaba, bugün ne keşfedelim?</div>
                <div class="chips-container">
                    <div class="chip" onclick="hizliSor('AÖF ders notlarımı inceleyip benim için kritik konulardan oluşan bir sınav özeti çıkarır mısın?')">📚 AÖF Ders Özeti Çıkar</div>
                    <div class="chip" onclick="hizliSor('Python kodumda hata alıyorum, en sık yapılan mantık hatalarını nasıl ayıklayabilirim?')">💻 Python Hata Ayıklama</div>
                    <div class="chip" onclick="hizliSor('Bana Ammice Arapça (Suudi Arabistan) günlük diyalog kalıplarıyla pratik yaptır.')">🇸🇦 Ammice Arapça Pratik</div>
                    <div class="chip" onclick="hizliSor('Stefan Zweig Satranç ve Sabahattin Ali Kürk Mantolu Madonna eserlerindeki psikolojik temaları karşılaştır.')">♟️ Edebi Metin Analizi</div>
                </div>
            </div>
        </div>
        
        <div id="input-container">
            <input type="file" id="file-input" style="display:none" accept="image/*, video/*, audio/*, .pdf, .doc, .docx">
            <div class="input-wrapper">
                <button class="action-btn" onclick="document.getElementById('file-input').click()" title="Dosya Ekle">📎</button>
                <input type="text" id="user-input" placeholder="Kerem'e bir şey sor..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
                <button class="action-btn" id="mic-btn" title="Sesli Soru Sor">🎤</button>
                <button id="send-btn" onclick="mesajGonder()">➤</button>
            </div>
        </div>
    </div>

    <script>
        marked.setOptions({ breaks: true });
        
        // --- 1. KULLANICI İZOLASYONU (Cihaza Özel Kimlik) ---
        let deviceId = localStorage.getItem("kerem_device_id");
        if (!deviceId) {
            deviceId = "user_" + Math.random().toString(36).substr(2, 9);
            localStorage.setItem("kerem_device_id", deviceId);
        }

        let currentSessionId = deviceId + "_" + Date.now();
        let isFirstMessage = true;
        let lastUserMessage = ""; 

        // 1. Sayfa yüklendiğinde SADECE BU CİHAZIN sohbetlerini çek
        async function sohbetleriYukle() {
            try {
                const response = await fetch('/api/sohbetler?user_id=' + deviceId);
                const data = await response.json();
                const list = document.getElementById('sidebar-list');
                list.innerHTML = '';
                
                if (data.sohbetler.length === 0) {
                    list.innerHTML = '<div style="color:#888; font-size:13px; text-align:center;">Henüz sohbet yok.</div>';
                    return;
                }

                data.sohbetler.forEach(sohbet => {
                    const btn = document.createElement('button');
                    btn.className = `history-item ${sohbet.id === currentSessionId ? 'active' : ''}`;
                    btn.innerText = sohbet.baslik;
                    btn.onclick = () => sohbetAc(sohbet.id, btn);
                    list.appendChild(btn);
                });
            } catch(e) {
                console.error("Sidebar yüklenemedi", e);
            }
        }
        window.onload = sohbetleriYukle;

        // 2. Geçmiş Sohbeti Ekrana Yükle
        async function sohbetAc(id, btnElement) {
            currentSessionId = id;
            isFirstMessage = false;
            
            document.querySelectorAll('.history-item').forEach(b => b.classList.remove('active'));
            if(btnElement) btnElement.classList.add('active');

            const chatContainer = document.getElementById("chat-container");
            chatContainer.innerHTML = `<div style="text-align:center; color:#888; padding: 20px;"><div class="spinner" style="margin:0 auto;"></div> Sohbet yükleniyor...</div>`;
            
            try {
                const response = await fetch('/api/sohbet/' + id);
                const data = await response.json();
                chatContainer.innerHTML = '';
                
                if(data.mesajlar && data.mesajlar.length > 0) {
                    data.mesajlar.forEach(msg => {
                        if(msg.role === 'user') {
                            chatContainer.innerHTML += `<div class="message-wrapper"><div class="message user-msg">${msg.text}</div></div>`;
                        } else {
                            chatContainer.innerHTML += `<div class="message-wrapper"><div class="message bot-msg">${marked.parse(msg.text)}</div></div>`;
                        }
                    });
                    addCopyButtons(chatContainer);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                } else {
                    chatContainer.innerHTML = '<div style="text-align:center; color:#888; padding: 20px;">Bu sohbet boş.</div>';
                }
            } catch(e) {
                chatContainer.innerHTML = '<div style="color:#ff5252; text-align:center;">Sohbet yüklenirken hata oluştu.</div>';
            }
        }

        // 3. Yeni Sohbet Başlat
        function yeniSohbet() {
            currentSessionId = deviceId + "_" + Date.now();
            isFirstMessage = true;
            document.querySelectorAll('.history-item').forEach(b => b.classList.remove('active'));
            
            document.getElementById("chat-container").innerHTML = `
                <div id="welcome-screen">
                    <div class="greeting">Merhaba, bugün ne keşfedelim?</div>
                    <div class="chips-container">
                        <div class="chip" onclick="hizliSor('AÖF ders notlarımı inceleyip benim için kritik konulardan oluşan bir sınav özeti çıkarır mısın?')">📚 AÖF Ders Özeti Çıkar</div>
                        <div class="chip" onclick="hizliSor('Python kodumda hata alıyorum, en sık yapılan mantık hatalarını nasıl ayıklayabilirim?')">💻 Python Hata Ayıklama</div>
                        <div class="chip" onclick="hizliSor('Bana Ammice Arapça (Suudi Arabistan) günlük diyalog kalıplarıyla pratik yaptır.')">🇸🇦 Ammice Arapça Pratik</div>
                        <div class="chip" onclick="hizliSor('Stefan Zweig Satranç ve Sabahattin Ali Kürk Mantolu Madonna eserlerindeki psikolojik temaları karşılaştır.')">♟️ Edebi Metin Analizi</div>
                    </div>
                </div>`;
        }

        function temaDegistir() {
            const body = document.body;
            const btn = document.querySelector('.theme-toggle');
            if (body.getAttribute('data-theme') === 'light') {
                body.removeAttribute('data-theme'); btn.innerHTML = '☀️';
            } else {
                body.setAttribute('data-theme', 'light'); btn.innerHTML = '🌙';
            }
        }

        function hizliSor(metin) {
            document.getElementById("user-input").value = metin;
            mesajGonder();
        }

        function addCopyButtons(container) {
            const pres = container.querySelectorAll('pre');
            pres.forEach(pre => {
                if(pre.querySelector('.copy-btn')) return; 
                const btn = document.createElement('button');
                btn.className = 'copy-btn';
                btn.innerHTML = '📋 Kopyala';
                btn.onclick = () => {
                    navigator.clipboard.writeText(pre.querySelector('code').innerText);
                    btn.innerHTML = '✔️ Kopyalandı';
                    btn.style.background = '#4CAF50';
                    setTimeout(() => { btn.innerHTML = '📋 Kopyala'; btn.style.background = '#333'; }, 2000);
                };
                pre.appendChild(btn);
            });
        }

        function sesliOku(btn) {
            const textElement = btn.parentElement.previousElementSibling;
            if(!textElement) return;
            const s = new SpeechSynthesisUtterance(textElement.innerText);
            s.lang = 'tr-TR';
            window.speechSynthesis.speak(s);
        }

        async function daktiloEfekti(element, metin, hiz = 15) {
            let i = 0; let anlikMetin = "";
            return new Promise((resolve) => {
                const timer = setInterval(() => {
                    anlikMetin += metin.charAt(i);
                    element.innerHTML = marked.parse(anlikMetin);
                    addCopyButtons(element);
                    document.getElementById("chat-container").scrollTop = document.getElementById("chat-container").scrollHeight;
                    i++;
                    if (i === metin.length) { clearInterval(timer); resolve(); }
                }, hiz);
            });
        }

        // --- 2. SESLİ KOMUT DÜZELTMESİ (Aç/Kapat Mantığı) ---
        const micBtn = document.getElementById("mic-btn");
        const userInput = document.getElementById("user-input");
        let recognition;
        let isListening = false;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'tr-TR';
            
            recognition.onstart = () => { 
                isListening = true; 
                micBtn.classList.add("listening"); 
                userInput.placeholder = "Dinliyorum..."; 
            };
            
            recognition.onresult = (e) => { 
                userInput.value = userInput.value ? userInput.value + " " + e.results[0][0].transcript : e.results[0][0].transcript; 
            };
            
            recognition.onerror = () => { 
                isListening = false;
                micBtn.classList.remove("listening");
                userInput.placeholder = "Kerem'e bir şey sor..."; 
            };
            
            recognition.onend = () => { 
                isListening = false; 
                micBtn.classList.remove("listening"); 
                userInput.placeholder = "Kerem'e bir şey sor..."; 
            };
            
            micBtn.onclick = () => { 
                if (isListening) {
                    recognition.stop();
                } else {
                    try { recognition.start(); } catch(e) { console.error("Mikrofon başlatılamadı", e); }
                }
            };
        } else { 
            micBtn.style.display = "none"; 
        }

        // --- ANA MESAJ GÖNDERME FONKSİYONU ---
        async function mesajGonder(retryMessage = null) {
            const input = document.getElementById("user-input");
            const fileInput = document.getElementById("file-input");
            const chatContainer = document.getElementById("chat-container");
            const sendBtn = document.getElementById("send-btn");
            const aiMode = document.getElementById("ai-mode").value;
            
            let currentMsg = retryMessage || input.value;
            if (!currentMsg.trim() && fileInput.files.length === 0) return;
            
            lastUserMessage = currentMsg;

            if (isFirstMessage) {
                const welcomeScreen = document.getElementById("welcome-screen");
                if(welcomeScreen) welcomeScreen.style.display = "none";
            }

            const formData = new FormData();
            formData.append("mesaj", currentMsg);
            formData.append("session_id", currentSessionId); 
            formData.append("user_id", deviceId); // Backend'e kimlik bildirimi
            
            let eklentiMetni = "";
            if (fileInput.files.length > 0) {
                formData.append("dosya", fileInput.files[0]);
                eklentiMetni = `<br><small style="color:var(--accent);">📎 ${fileInput.files[0].name}</small>`;
            }

            if(!retryMessage) {
                chatContainer.innerHTML += `<div class="message-wrapper"><div class="message user-msg">${currentMsg} ${eklentiMetni}</div></div>`;
            }
            
            input.value = ""; fileInput.value = "";
            input.disabled = true; sendBtn.disabled = true; micBtn.disabled = true;
            
            const waitingText = aiMode === "fast" ? "Hızla yanıtlıyor..." : "Kerem Düşünüyor...";
            const typingId = "typing-" + Date.now();
            const wrapperId = "wrapper-" + Date.now();
            
            chatContainer.innerHTML += `
                <div class="message-wrapper" id="${wrapperId}">
                    <div id="${typingId}" class="message bot-msg">
                        <div class="thinking"><div class="spinner"></div> ${waitingText}</div>
                    </div>
                </div>`;
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                
                const botMesajKutusu = document.getElementById(typingId);
                botMesajKutusu.innerHTML = ""; 
                
                if (aiMode === "fast") {
                    botMesajKutusu.innerHTML = marked.parse(data.cevap);
                    addCopyButtons(botMesajKutusu);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                } else {
                    await daktiloEfekti(botMesajKutusu, data.cevap);
                }

                const actionsHtml = `
                <div class="msg-actions">
                    <button class="action-icon" onclick="sesliOku(this)" title="Sesli Dinle">🔊</button>
                    <button class="action-icon" onclick="mesajGonder(lastUserMessage)" title="Yeniden Üret">🔄</button>
                </div>`;
                document.getElementById(wrapperId).insertAdjacentHTML('beforeend', actionsHtml);
                
                if(isFirstMessage) {
                    sohbetleriYukle();
                    isFirstMessage = false;
                }

            } catch (error) {
                document.getElementById(typingId).innerHTML = `<span style="color: #ff5252;">Bağlantı hatası oluştu.</span>`;
            }
            
            input.disabled = false; sendBtn.disabled = false; micBtn.disabled = false;
            input.focus();
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

# --- FIREBASE SİDEBAR API ENDPOINTLERİ (GÜNCELLENDİ) ---
@app.route("/api/sohbetler", methods=["GET"])
def sohbetleri_getir():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify({"sohbetler": []})

    try:
        db_client = firestore.client()
        # Sadece bu cihaza ait olan sohbetleri getir
        docs = db_client.collection("web_sohbetler").where("user_id", "==", user_id).stream()
        
        sohbetler = []
        for doc in docs:
            data = doc.to_dict()
            sohbetler.append({"id": doc.id, "baslik": data.get("baslik", "Yeni Sohbet")})
            
        # ID'sine göre tersten sırala (En yeni en üstte)
        sohbetler.sort(key=lambda x: x["id"], reverse=True)
        return jsonify({"sohbetler": sohbetler[:15]})
    except Exception as e:
        print("Sohbet getirme hatası:", e)
        return jsonify({"sohbetler": []})

@app.route("/api/sohbet/<session_id>", methods=["GET"])
def sohbet_getir(session_id):
    try:
        db_client = firestore.client()
        doc = db_client.collection("web_sohbetler").document(session_id).get()
        if doc.exists:
            return jsonify({"mesajlar": doc.to_dict().get("mesajlar", [])})
        return jsonify({"mesajlar": []})
    except:
        return jsonify({"mesajlar": []})

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "web_kullanicisi")
    user_id = request.form.get("user_id", "anonim")
    
    dosya_yolu = None
    if 'dosya' in request.files:
        file = request.files['dosya']
        if file.filename != '':
            dosya_yolu = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(dosya_yolu)
    
    # Session ID'yi ask_ai'ye göndererek bu sohbete özel hafıza yaratıyoruz
    cevap = ask_ai(mesaj, user_id=session_id, image_path=dosya_yolu)
    if dosya_yolu and os.path.exists(dosya_yolu): os.remove(dosya_yolu)

    # Firebase'e Sidebar Verisini Kaydet
    try:
        db_client = firestore.client()
        doc_ref = db_client.collection("web_sohbetler").document(session_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            # Yeni sohbet: user_id etiketini mutlaka ekliyoruz
            baslik = mesaj[:25] + "..." if len(mesaj) > 25 else mesaj
            doc_ref.set({
                "baslik": baslik, 
                "user_id": user_id, 
                "tarih": firestore.SERVER_TIMESTAMP, 
                "mesajlar": []
            })
        
        # Mesajları diziye ekle
        doc_ref.update({
            "mesajlar": firestore.ArrayUnion([
                {"role": "user", "text": mesaj},
                {"role": "bot", "text": cevap}
            ])
        })
    except Exception as e:
        print("Firebase Sidebar Kayıt Hatası:", e)

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
