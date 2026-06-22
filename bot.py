import os
import json
import threading
import time
import asyncio
import re
import datetime
import requests
import hashlib

from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename

from telegram import Update, ChatPermissions
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# --- ÇEVRE DEĞİŞKENLERİ (.env) ---
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from ai import ask_ai

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==========================================
# 🛡️ SİBER GÜVENLİK VE AYAR KALKANLARI 🛡️
# ==========================================
SUPER_ADMIN_ID = 7082795768  # Sistem Kurucusu ID
MAKSIMUM_DOSYA_BOYUTU = 5 * 1024 * 1024 # 5 MB 
TEHLIKELI_PROMPTLAR = ["unut", "ignore", "sistem", "system prompt", "kurallar", "şifre", "bypass", "jailbreak", "sen bir"]
YASAKLI_KELIMELER = ["bahis", "kumar", "şans oyunu", "illegal"]

kullanici_mesaj_zamanlari = {}
aktif_silme_gorevleri = set()
grup_durumlari = {}   

# --- 1. FIREBASE BASLATMA ---
try:
    firebase_json_str = os.environ.get("FIREBASE_JSON")
    if firebase_json_str:
        cred_dict = json.loads(firebase_json_str)
        cred = credentials.Certificate(cred_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        print("✅ Firebase basariyla baslatildi.", flush=True)
except Exception as e:
    print(f"❌ Firebase baslatma hatasi: {e}", flush=True)

# 🧠 FIREBASE KALICI GRUP HAFIZASI (Bot Asla Unutmaz)
def gruplari_yukle():
    try:
        doc = firestore.client().collection("bot_ayarlar").document("aktif_gruplar").get()
        if doc.exists:
            return set(doc.to_dict().get("liste", []))
    except: pass
    return set()

def grubu_kaydet(chat_id):
    try:
        firestore.client().collection("bot_ayarlar").document("aktif_gruplar").set({
            "liste": firestore.ArrayUnion([chat_id])
        }, merge=True)
    except: pass

aktif_gruplar = gruplari_yukle() # Bot başlarken veritabanından hatırlar

# 🚨 SESSİZ İSTİHBARAT SİSTEMİ
async def rapor_ver(context: ContextTypes.DEFAULT_TYPE, baslik: str, detay: str):
    try:
        mesaj = (
            f"🚨 <b>SİBER GÜVENLİK UYARISI</b> 🚨\n\n"
            f"🛡️ <b>Kalkan:</b> {baslik}\n"
            f"👤 <b>Detay:</b> {detay}\n\n"
            f"<i>Kerem AI duruma müdahale etti ve işlemi durdurdu.</i>"
        )
        await context.bot.send_message(chat_id=SUPER_ADMIN_ID, text=mesaj, parse_mode='HTML')
    except Exception as e:
        pass


# --- 2. TAM TASARIMLI ARAYUZ (AUTH YOK) ---
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kerem AI - Yapay Zeka Asistani</title>

    <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());

      gtag('config', 'G-6FCWEJ4KGN');
    </script>
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
            -webkit-user-select: none;
            user-select: none;
        }
        
        input, .message { -webkit-user-select: text; user-select: text; }

        .sidebar { width: 260px; background-color: var(--sidebar-bg); border-right: 1px solid var(--bot-border); display: flex; flex-direction: column; padding: 15px; z-index: 20;}
        .new-chat-btn { background-color: var(--hover-bg); border: 1px solid var(--bot-border); color: var(--text-color); padding: 12px 15px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 20px; transition: 0.2s; width: 100%; box-sizing: border-box;}
        .new-chat-btn:hover { border-color: var(--accent); }
        .history-list { display: flex; flex-direction: column; gap: 5px; overflow-y: auto; flex: 1; padding-right: 5px; }
        
        .history-row { display: flex; align-items: center; justify-content: space-between; border-radius: 8px; transition: 0.2s; }
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
        .listening { animation: pulse-mic 1s infinite; background-color: #ff5252 !important; color: white !important; }
        @keyframes pulse-mic { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }

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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 0 5px;">
            <div style="font-size:12px; color:#888; font-weight:bold;">GECMIS SOHBETLER</div>
            <button onclick="tumSohbetleriSil()" style="background:transparent; border:none; color:#ff5252; cursor:pointer; font-size:12px; opacity:0.8; font-weight:bold;" title="Tum Sohbetleri Sil">🗑️ Tumunu Sil</button>
        </div>
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
        <h1 style="font-size:38px; margin-bottom:10px; font-weight:600; background: linear-gradient(45deg, #a8c7fa, #ffb6c1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Merhaba, bugun ne kesfedelim?</h1>
        <div class="chips-container" id="dynamic-chips"></div>
    </div>
</div>
        
        <div id="input-container">
            <input type="file" id="file-input" style="display:none" accept="image/*, .pdf">
            <div class="input-capsule">
                <button class="capsule-btn" onclick="document.getElementById('file-input').click()" title="Dosya veya Gorsel Ekle">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                </button>
                
                <input type="text" id="user-input" placeholder="Kerem'e bir sey sor..." autocomplete="off" onkeypress="if(event.key === 'Enter') mesajGonder()">
                
                <select id="ai-mode" class="capsule-select" title="Yanit Hizini Sec">
                    <option value="thinking">🧠 Dusunen Mod</option>
                    <option value="fast">⚡ Hizli Mod</option>
                </select>
                
                <button class="capsule-btn" id="mic-btn" title="Basili Tutarak Konus">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg>
                </button>
                
                <button class="capsule-btn" onclick="mesajGonder()" title="Mesaji Gonder">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </div>
            <div class="disclaimer-text">Kerem AI bir yapay zeka modeli oldugu icin hata yapabilir.</div>
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
        const fileInput = document.getElementById("file-input");
        let recognition;
        let isListening = false;
        let isSpeaking = false;
        let currentSpeakingBtn = null;

        const kaydedilenTema = localStorage.getItem("kerem_theme") || "dark";
        if (kaydedilenTema === "light") {
            document.body.setAttribute('data-theme', 'light');
            document.getElementById("theme-btn").innerHTML = '🌙';
        }

        fileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name;
            if (fileName) {
                userInput.placeholder = "📎 " + fileName + " secildi (Gonder'e bas)...";
                userInput.focus();
            }
        });

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

        function stripMarkdown(text) { return text.replace(/[*#`~_]/g, ''); }

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
                s.lang = 'tr-TR';
                s.onend = s.onerror = () => { btn.innerHTML = '🔊 Dinle'; isSpeaking = false; currentSpeakingBtn = null; };
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
                userInput.placeholder = "Dinliyorum, konusun ve birakin..."; 
            };
            
            recognition.onresult = (e) => { 
                let interimTranscript = '';
                let finalTranscript = '';
                for (let i = e.resultIndex; i < e.results.length; ++i) {
                    if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript;
                    else interimTranscript += e.results[i][0].transcript;
                }
                if(finalTranscript) userInput.value = (userInput.value + " " + finalTranscript).trim();
                else if(interimTranscript) userInput.placeholder = interimTranscript; 
            };
            
            recognition.onend = () => { 
                isListening = false; 
                micBtn.classList.remove("listening"); 
                userInput.placeholder = "Kerem'e bir sey sor..."; 
                if (userInput.value.trim() !== "") mesajGonder(); 
            };
            
            const startRecord = (e) => { e.preventDefault(); if(!isListening) { try { recognition.start(); } catch(err){} } };
            const stopRecord = (e) => { e.preventDefault(); if(isListening) { recognition.stop(); } };

            micBtn.addEventListener('mousedown', startRecord);
            micBtn.addEventListener('mouseup', stopRecord);
            micBtn.addEventListener('mouseleave', stopRecord); 
            micBtn.addEventListener('touchstart', startRecord);
            micBtn.addEventListener('touchend', stopRecord);
            
        } else { micBtn.style.display = "none"; }

        async function sohbetleriYukle() {
            try {
                const res = await fetch('/api/sohbetler?user_id=' + deviceId);
                const data = await res.json();
                const list = document.getElementById('sidebar-list');
                list.innerHTML = '';
                if(data.sohbetler.length===0) return list.innerHTML = '<div style="color:#888; font-size:13px; text-align:center; margin-top:20px;">Henuz sohbet yok.</div>';
                
                data.sohbetler.forEach(s => {
                    const row = document.createElement('div');
                    row.className = 'history-row ' + (s.id===currentSessionId?'active':'');
                    row.innerHTML = '<button class="history-item" onclick="sohbetAc(\\'' + s.id + '\\', this.parentElement)">' + s.baslik + '</button>' +
                                    '<button class="delete-btn" onclick="sohbetSil(\\'' + s.id + '\\', event)" title="Sohbeti Sil">' +
                                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>' +
                                    '</button>';
                    list.appendChild(row);
                });
            } catch(e) {}
        }
        window.onload = sohbetleriYukle;

        async function sohbetSil(sessionId, event) {
            event.stopPropagation();
            if(!confirm("Bu sohbet gecmisini silmek istiyor musunuz?")) return;
            try {
                const res = await fetch('/api/sohbet/sil?session_id=' + sessionId, { method: 'DELETE' });
                const data = await res.json();
                if(data.status === "success") {
                    if(currentSessionId === sessionId) yeniSohbet();
                    else sohbetleriYukle();
                }
            } catch(e) { alert("Hata olustu."); }
        }

        async function tumSohbetleriSil() {
            if(!confirm("Tum sohbet gecmisini kalici olarak silmek istediginize emin misiniz? Bu islem geri alinamaz!")) return;
            try {
                const res = await fetch('/api/sohbet/sil-tum?user_id=' + deviceId, { method: 'DELETE' });
                const data = await res.json();
                if(data.status === "success") { yeniSohbet(); }
            } catch(e) { alert("Silme islemi sirasinda hata olustu."); }
        }

        async function sohbetAc(id, rowElement) {
            currentSessionId = id; isFirstMessage = false;
            document.querySelectorAll('.history-row').forEach(r => r.classList.remove('active'));
            if(rowElement) rowElement.classList.add('active');
            const container = document.getElementById("chat-container");
            container.innerHTML = '<div style="text-align:center; padding: 20px;"><div class="spinner"></div> Yukleniyor...</div>';
            try {
                const res = await fetch('/api/sohbet/' + id); const data = await res.json();
                container.innerHTML = '';
                data.mesajlar.forEach(msg => {
                    const msgClass = msg.role === 'user' ? 'user-msg' : 'bot-msg';
                    const msgContent = msg.role === 'user' ? msg.text : marked.parse(msg.text);
                    container.innerHTML += '<div class="message-wrapper"><div class="message ' + msgClass + '">' + msgContent + '</div></div>';
                });
                container.scrollTop = container.scrollHeight;
            } catch(e) { container.innerHTML = '<div style="color:#ff5252;">Hata olustu.</div>'; }
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
            
            let displayMsg = currentMsg;
            if (fileInput.files.length > 0) {
                displayMsg = "📎 <b>" + fileInput.files[0].name + "</b>" + (currentMsg ? "<br>" + currentMsg : "");
            }
            
            chat.innerHTML += '<div class="message-wrapper"><div class="message user-msg">' + displayMsg + '</div></div>';
            
            const formData = new FormData();
            formData.append("mesaj", currentMsg);
            formData.append("session_id", currentSessionId); 
            formData.append("user_id", deviceId);
            formData.append("mode", document.getElementById("ai-mode").value);
            
            if (fileInput.files.length > 0) formData.append("dosya", fileInput.files[0]);
            
            userInput.value = ""; fileInput.value = "";
            userInput.placeholder = "Kerem'e bir sey sor...";
            userInput.disabled = true; 
            
            const typingId = "type-" + Date.now();
            chat.innerHTML += '<div class="message-wrapper"><div id="' + typingId + '" class="message bot-msg"><div class="spinner"></div> Kerem dusunuyor...</div></div>';
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const response = await fetch("/api/sor", { method: "POST", body: formData });
                const data = await response.json();
                const botBox = document.getElementById(typingId);
                
                botBox.innerHTML = "";
                await daktiloEfekti(botBox, data.cevap);
                botBox.innerHTML += '<div class="msg-actions"><button class="action-icon btn-dinle" onclick="sesliOkuElement(this)">🔊 Dinle</button></div>';
                if(isFirstMessage) { sohbetleriYukle(); isFirstMessage = false; }
            } catch (error) { document.getElementById(typingId).innerHTML = "Baglanti hatasi."; }
            
            userInput.disabled = false;
            userInput.focus();
        }
    </script>
</body>
</html>
"""

# --- 3. FLASK ROUTE'LARI ---
@app.route("/")
def ana_sayfa(): 
    return render_template_string(HTML_SAYFASI)

@app.route("/api/sohbetler", methods=["GET"])
def sohbetleri_getir():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify({"sohbetler": []})
    try:
        docs = firestore.client().collection("web_sohbetler").where("user_id", "==", user_id).stream()
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

@app.route("/api/sohbet/sil", methods=["DELETE"])
def sohbet_sil():
    session_id = request.args.get("session_id")
    if not session_id: return jsonify({"status": "error"}), 400
    try:
        firestore.client().collection("web_sohbetler").document(session_id).delete()
        return jsonify({"status": "success"})
    except: return jsonify({"status": "error"}), 500

@app.route("/api/sohbet/sil-tum", methods=["DELETE"])
def sohbet_sil_tum():
    user_id = request.args.get("user_id")
    if not user_id: return jsonify({"status": "error"}), 400
    try:
        db_client = firestore.client()
        docs = db_client.collection("web_sohbetler").where("user_id", "==", user_id).stream()
        for doc in docs:
            doc.reference.delete()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "default")
    user_id = request.form.get("user_id", "default")
    
    dosya_yolu = None
    if 'dosya' in request.files and request.files['dosya'].filename:
        dosya_yolu = os.path.join(UPLOAD_FOLDER, secure_filename(request.files['dosya'].filename))
        request.files['dosya'].save(dosya_yolu)
    
    if dosya_yolu and not mesaj.strip():
        mesaj = "Lütfen içeriğini metin olarak sana sunduğum bu dokümanı analiz et ve detaylı bir özetini çıkar."

    cevap = ask_ai(mesaj, user_id=session_id, image_path=dosya_yolu)
    
    if dosya_yolu and os.path.exists(dosya_yolu): os.remove(dosya_yolu)
    
    try:
        doc_ref = firestore.client().collection("web_sohbetler").document(session_id)
        if not doc_ref.get().exists: doc_ref.set({"baslik": mesaj[:25], "user_id": user_id, "mesajlar": []})
        doc_ref.update({"mesajlar": firestore.ArrayUnion([{"role": "user", "text": mesaj}, {"role": "bot", "text": cevap}])})
    except: pass
    return jsonify({"cevap": cevap})


# --- 4. TELEGRAM BOT FONKSIYONLARI ---

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id == SUPER_ADMIN_ID:
        return True
    if update.effective_chat.type == 'private':
        return False
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return chat_member.status in ['administrator', 'creator']

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("⛔ Bu komutu sadece yöneticiler kullanabilir.")
    if not update.message.reply_to_message:
        return await update.message.reply_text("Lütfen yasaklamak istediğiniz kişinin bir mesajını yanıtlayarak /ban yazın.")
    
    target_user = update.message.reply_to_message.from_user
    if target_user.id == SUPER_ADMIN_ID:
        return await update.message.reply_text("⛔ Güvenlik Kalkanı: Sistem kurucusu yasaklanamaz!")

    try:
        await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id)
        await update.message.reply_text(f"🔨 {target_user.first_name} Kerem AI tarafından gruptan kalıcı olarak yasaklandı.")
    except Exception:
        await update.message.reply_text("Bu işlemi yapmaya yetkim yok.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return await update.message.reply_text("Bir mesajı yanıtlayın.")
    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id, only_if_banned=True)
        await update.message.reply_text(f"✅ {target_user.first_name} adlı kişinin yasağı kaldırıldı.")
    except Exception: pass

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return await update.message.reply_text("Bir mesajı yanıtlayın.")
    target_user = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id)
        await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id)
        await update.message.reply_text(f"👢 {target_user.first_name} gruptan atıldı (tekrar katılabilir).")
    except Exception: pass

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return await update.message.reply_text("Bir mesajı yanıtlayın.")
    target_user = update.message.reply_to_message.from_user
    if target_user.id == SUPER_ADMIN_ID:
        return await update.message.reply_text("⛔ Güvenlik Kalkanı: Sistem kurucusu sessize alınamaz!")

    try:
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id, permissions=permissions)
        await update.message.reply_text(f"🤐 {target_user.first_name} sessize alındı. Artık mesaj gönderemez.")
    except Exception: pass

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return await update.message.reply_text("Bir mesajı yanıtlayın.")
    target_user = update.message.reply_to_message.from_user
    try:
        permissions = ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id, permissions=permissions)
        await update.message.reply_text(f"🔊 {target_user.first_name} artık konuşabilir.")
    except Exception: pass

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not update.message or not update.message.text: return
        
    mesaj = update.message.text.lower()

    if "yaz okulu" in mesaj:
        cevap = "☀️ <b>Yaz Okulu Tarihleri:</b>\n\n• <b>Anadolu AÖF:</b> Yaz Okulu Başvuru 29 Haziran - 3 Temmuz 2026. Yaz Okulu sınav tarihi 22 Ağustos 2026.\n• <b>Ata AÖF:</b> Yaz okulu sınav tarihi 13 Eylül 2026."
        return await update.message.reply_text(cevap, parse_mode='HTML')
    elif "ikinci üniversite" in mesaj:
        cevap = "🎓 <b>İkinci Üniversite Kayıtları:</b>\n\n• <b>Anadolu AÖF:</b> 17 Ağustos - 19 Ekim 2026.\n• <b>Ata AÖF:</b> 25 Ağustos - 03 Ekim 2025."
        return await update.message.reply_text(cevap, parse_mode='HTML')
    elif "bütünleme" in mesaj:
        cevap = "📝 <b>Bütünleme Sınavları:</b>\n\n• <b>Ata AÖF:</b> 01 Ağustos - 02 Ağustos 2026.\n• <b>AUZEF:</b> 04 - 05 Temmuz 2026.\n• <b>ANKUZEF:</b> 04-05 Temmuz 2026."
        return await update.message.reply_text(cevap, parse_mode='HTML')
    elif any(kelime in mesaj for kelime in ["üç ders", "3 ders", "mezuniyet"]):
        cevap = "🎓 <b>Mezuniyet İçin Üç Ders Sınavı:</b>\n\n• <b>Ata AÖF:</b> 13 Eylül 2026.\n• <b>AUZEF:</b> 05 Eylül 2026.\n• <b>ANKUZEF:</b> 20 Temmuz 2026."
        return await update.message.reply_text(cevap, parse_mode='HTML')

    if any(tehlike in mesaj for tehlike in TEHLIKELI_PROMPTLAR):
        return await update.message.reply_text("🛡️ Siber Güvenlik Kalkanı: Bu tür şüpheli komutları işlemem yasaktır.")

    bekleme = await update.message.reply_text("🧠 Düşünüyorum...")
    try:
        reply = ask_ai(update.message.text, f"tg_{update.message.from_user.id}")
        if not reply:
            reply = "⚠️ Yapay zeka bana boş bir yanıt döndürdü."
        await bekleme.edit_text(reply)
    except Exception as e:
        await bekleme.edit_text(f"⚠️ Yapay Zeka ile bağlantı koptu!\n\nHata: {str(e)}")

async def ses_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    bekleme = await update.message.reply_text("🎧 Dinleniyor...")
    dosya_adi = f"temp_{update.message.from_user.id}.ogg"
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        await file.download_to_drive(dosya_adi)
        reply = ask_ai("Bu sesli mesaja yanit ver.", user_id, image_path=dosya_adi)
        if not reply: reply = "⚠️ Ses anlaşılamadı veya boş yanıt geldi."
        await bekleme.edit_text(reply)
    except Exception as e:
        await bekleme.edit_text(f"⚠️ Hata oluştu: {str(e)}")
    finally:
        if os.path.exists(dosya_adi): os.remove(dosya_adi)

async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if update.message.document.file_size > 20 * 1024 * 1024:
        return await update.message.reply_text("🛑 Telegram Kalkanı: Telegram botları güvenlik ve altyapı gereği 20 MB'tan büyük dosyaları indiremez. Lütfen dosyayı küçültüp tekrar gönderin.")

    if update.message.document.file_size > MAKSIMUM_DOSYA_BOYUTU and user_id != SUPER_ADMIN_ID:
        await update.message.reply_text("🛑 Güvenlik Kalkanı: Dosya boyutu çok büyük (Max 5MB). İstek reddedildi.")
        grup_adi = update.message.chat.title if update.message.chat.title else "Özel Sohbet"
        await rapor_ver(context, "Hafıza Bombası (Büyük Dosya)", f"{update.message.from_user.first_name}, {grup_adi} konumunda 5MB'ı aşan bir dosya yüklemeye çalıştı.")
        return

    bekleme_mesaji = await update.message.reply_text("🛡️ Dosya alındı. Karantinada güvenlik taramasından geçiriliyor...")
    
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        dosya_adi = f"temp_{user_id}_{update.message.document.file_name}"
        await file.download_to_drive(dosya_adi)
        
        vt_api_key = os.environ.get("VIRUSTOTAL_API_KEY")
        if vt_api_key:
            sha256_hash = hashlib.sha256()
            with open(dosya_adi, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            dosya_hash = sha256_hash.hexdigest()

            url = f"https://www.virustotal.com/api/v3/files/{dosya_hash}"
            headers = {"x-apikey": vt_api_key}
            vt_response = requests.get(url, headers=headers)

            if vt_response.status_code == 200:
                sonuclar = vt_response.json()
                zararli_sayisi = sonuclar['data']['attributes']['last_analysis_stats']['malicious']
                
                if zararli_sayisi > 0:
                    os.remove(dosya_adi) 
                    await bekleme_mesaji.edit_text("🚨 <b>KRİTİK UYARI:</b> Yüklediğiniz dosyada zararlı yazılım tespit edildi. Dosya imha edildi!", parse_mode='HTML')
                    grup_adi = update.message.chat.title if update.message.chat.title else "Özel Sohbet"
                    await rapor_ver(context, "MALWARE TESPİTİ 🦠", f"{update.message.from_user.first_name}, {grup_adi} grubuna virüslü bir dosya ({update.message.document.file_name}) yükledi. Bot dosyayı sistemden sildi.")
                    return 
                    
        await bekleme_mesaji.edit_text("✅ Güvenlik taraması temiz. Yapay zeka dosyayı okuyor...")
        
        reply = ask_ai("Bu belgeyi analiz et ve özetle.", f"tg_{user_id}", image_path=dosya_adi)
        if not reply: reply = "⚠️ Dosya başarıyla okundu ancak yapay zeka boş bir yanıt üretti."
        await bekleme_mesaji.edit_text(reply)
        
    except Exception as e:
        await bekleme_mesaji.edit_text(f"⚠️ İşlem sırasında bir hata oluştu: {e}")
    finally:
        if 'dosya_adi' in locals() and os.path.exists(dosya_adi):
            os.remove(dosya_adi)

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧹 Yeni bir sayfa açtık! Bana yeni bir soru sorabilirsin.")

async def sinavtarihi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "📅 <b>2026 YILI AÖF SINAV TAKVİMİ</b>\n\n"
        "📘 <b>ANADOLU AÖF</b>\n"
        "• Yaz Okulu Sınavı: 22 Ağustos 2026\n\n"
        "📕 <b>ATA AÖF</b>\n"
        "• Bütünleme Sınavı: 1 - 2 Ağustos 2026\n"
        "• Yaz Okulu ve 3 Ders Sınavı: 13 Eylül 2026\n\n"
        "📗 <b>AUZEF</b>\n"
        "• Bütünleme Sınavı: 4 - 5 Temmuz 2026\n"
        "• Mezuniyet İçin 3 Ders Sınavı: 5 Eylül 2026\n\n"
        "📙 <b>ANKUZEF</b>\n"
        "• Bütünleme Sınavı: 4 - 5 Temmuz 2026\n"
        "• Mezuniyete 3 Ders Sınavı: 25 Temmuz 2026"
    )
    await update.message.reply_text(mesaj, parse_mode='HTML')

async def kayit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "📝 <b>2026 YILI AÖF KAYIT VE EĞİTİM DÖNEMLERİ</b>\n\n"
        "📘 <b>ANADOLU AÖF</b>\n"
        "• Yaz Okulu Kayıtları: 29 Haziran - 3 Temmuz 2026\n"
        "• Yaz Okulu Süreci: 29 Haziran - 22 Ağustos 2026 <i>(8 Hafta)</i>\n\n"
        "📙 <b>ANKUZEF</b>\n"
        "• Mezuniyete 3 Ders Sınavı Başvurusu: 20 Temmuz 2026\n\n"
        "<i>💡 Not: Diğer üniversitelerin kayıt detayları açıklandığında listeye eklenecektir.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode='HTML')

async def iletisim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "📞 <b>İLETİŞİM VE DESTEK</b>\n\n"
        "Grup kuralları, reklam işbirlikleri, şikayet veya önerileriniz için aktif grup yöneticilerimizden birine doğrudan özel mesaj gönderebilirsiniz.\n\n"
        "🤖 <i>Ben Kerem AI, derslerinizle ilgili sorularınıza gruptan yanıt vermeye devam edeceğim. Başarılar dilerim!</i>"
    )
    await update.message.reply_text(mesaj, parse_mode='HTML')

# ⏱️ GECE BEKÇİSİ - SAAT GÜNCELLEMESİ
async def gece_bekcisi(bot):
    KAPANIS_SAATI = 0  # Gece 12 (00:00) olarak ayarlandı
    ACILIS_SAATI = 8   
    while True:
        try:
            simdi = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            saat = simdi.hour
            gece_mi = KAPANIS_SAATI <= saat < ACILIS_SAATI
            
            for chat_id in list(aktif_gruplar):
                try:
                    durum = grup_durumlari.get(chat_id, None)
                    if durum is None:
                        grup_durumlari[chat_id] = "KAPALI" if gece_mi else "ACIK"
                        if gece_mi: await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                        continue
                    
                    if gece_mi and durum != "KAPALI":
                        await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                        await bot.send_message(chat_id, f"🌙 <b>Saat 0{KAPANIS_SAATI}:00 oldu.</b>\n\nGrup sabah 0{ACILIS_SAATI}:00'a kadar mesaj gönderimine kapatılmıştır. Yöneticiler harici mesaj atılamaz. Herkese İyi Geceler!", parse_mode='HTML')
                        grup_durumlari[chat_id] = "KAPALI"
                        
                    elif not gece_mi and durum == "KAPALI":
                        permissions = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
                        await bot.set_chat_permissions(chat_id, permissions)
                        await bot.send_message(chat_id, f"☀️ <b>Saat 0{ACILIS_SAATI}:00 oldu.</b>\n\nGrup mesaj gönderimine açılmıştır. Günaydın!", parse_mode='HTML')
                        grup_durumlari[chat_id] = "ACIK"
                        
                except Exception as e:
                    print(f"⚠️ Gece Bekçisi Hatası | Grup ID: {chat_id} | Hata: {e}", flush=True)
                    pass 
                    
        except Exception as e: 
            print(f"Gece Bekçisi Ana Döngü Hatası: {e}", flush=True)
            pass
            
        await asyncio.sleep(15)

async def post_init(application: Application):
    asyncio.create_task(gece_bekcisi(application.bot))

async def gecikmeli_sil(bot, chat_id, message_id):
    try:
        await asyncio.sleep(10)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except: pass

def gorevi_guvenli_baslat(bot, chat_id, message_id):
    gorev = asyncio.create_task(gecikmeli_sil(bot, chat_id, message_id))
    aktif_silme_gorevleri.add(gorev)
    gorev.add_done_callback(aktif_silme_gorevleri.discard)

async def otomatik_moderasyon(update, context):
    if not update.message or not update.message.chat: return
    chat_id = update.message.chat_id
    
    # 🧠 GÜÇLENDİRİLMİŞ HAFIZA: Grubu anında hafızaya ve veritabanına ekle
    if chat_id not in aktif_gruplar:
        print(f"Yeni grup tespit edildi, hafızaya alınıyor: {chat_id}", flush=True)
        aktif_gruplar.add(chat_id)  # RAM'deki set'i güncelle
        grubu_kaydet(chat_id)       # Firebase'deki veritabanını güncelle

    user_id = update.message.from_user.id
    mesaj = update.message.text.lower()
    kullanici_adi = update.message.from_user.first_name

    if user_id == SUPER_ADMIN_ID: return

    if any(kelime in mesaj for kelime in YASAKLI_KELIMELER):
        try: await update.message.delete()
        except: pass
        uyari = await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {kullanici_adi}, bu grupta yasaklı kelime kullanamazsın!")
        gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
        grup_adi = update.message.chat.title
        await rapor_ver(context, "Yasaklı Kelime", f"{kullanici_adi}, {grup_adi} grubunda yasaklı kelime kullandı.")
        return

    link_sablonu = r"(https?://|t\.me/|www\.)"
    if re.search(link_sablonu, mesaj):
        try: await update.message.delete()
        except: pass
        uyari = await context.bot.send_message(chat_id=chat_id, text=f"🚫 {kullanici_adi}, grupta izinsiz link paylaşımı yasaktır!")
        gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
        return

    simdi = time.time()
    if user_id not in kullanici_mesaj_zamanlari: kullanici_mesaj_zamanlari[user_id] = []
    kullanici_mesaj_zamanlari[user_id] = [t for t in kullanici_mesaj_zamanlari[user_id] if simdi - t < 7]
    kullanici_mesaj_zamanlari[user_id].append(simdi)

    if len(kullanici_mesaj_zamanlari[user_id]) >= 5:
        uyari = await context.bot.send_message(chat_id=chat_id, text=f"🛑 {kullanici_adi} spam limiti aşıldı! Otomatik kısıtlama uygulanıyor...")
        gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
        try: await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=ChatPermissions(can_send_messages=False))
        except: pass
        kullanici_mesaj_zamanlari[user_id] = []

def run_telegram_bot():
    token = "8736315853:AAHBp8IoQX4i8GsBFJ96jfZnQCUTFXIHdkQ"
    if not token or "BURAYA" in token:
        print("❌ HATA: Telegram Token'ı kodun içinde tanımlanmamış!", flush=True)
        return
    
    app_bot = Application.builder().token(token).post_init(post_init).build()
    
    app_bot.add_handler(CommandHandler("ban", ban_command))
    app_bot.add_handler(CommandHandler("unban", unban_command))
    app_bot.add_handler(CommandHandler("kick", kick_command))
    app_bot.add_handler(CommandHandler("mute", mute_command))
    app_bot.add_handler(CommandHandler("unmute", unmute_command))
    
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, otomatik_moderasyon), group=-1)
    
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Kerem AI Hazir.")))
    app_bot.add_handler(CommandHandler("temizle", temizle_command)) 
    app_bot.add_handler(CommandHandler("sinavtarihi", sinavtarihi_command))
    app_bot.add_handler(CommandHandler("kayit", kayit_command))
    app_bot.add_handler(CommandHandler("iletisim", iletisim_command))
    
    app_bot.add_handler(MessageHandler(filters.Document.ALL, dosya_al))
    app_bot.add_handler(MessageHandler(filters.VOICE, ses_al))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    print("🚀 Telegram bot polling başlatılıyor...", flush=True)
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    def start_flask():
        try:
            port = int(os.environ.get("PORT", 10000))
            print(f"🌐 Web sunucusu {port} portunda başlatılıyor...", flush=True)
            app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"❌ Web sunucusu hatası: {e}", flush=True)

    web_thread = threading.Thread(target=start_flask, daemon=True)
    web_thread.start()
    time.sleep(2)

    try:    
        run_telegram_bot()
    except Exception as e:
        print(f"❌ BOT CRITICAL ERROR: {e}", flush=True)
