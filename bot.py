import os
import json
import threading
import time
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from ai import ask_ai 

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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


# --- MAIL GONDERIM MOTORU ---
def onay_kodu_uret():
    return ''.join(random.choices(string.digits, k=6))

def onay_maili_gonder(alici_mail, kod):
    gonderici_mail = os.environ.get("GMAIL_ADRESIN") 
    gonderici_sifre = os.environ.get("EMAIL_SIFRE")  
    
    if not gonderici_mail or not gonderici_sifre:
        return False, "Sunucu mail ayarları eksik! Lütfen GMAIL_ADRESIN ve EMAIL_SIFRE değişkenlerini ekleyin."

    mesaj = MIMEMultipart()
    mesaj['From'] = f"Kerem AI <{gonderici_mail}>"
    mesaj['To'] = alici_mail
    mesaj['Subject'] = "Kerem AI - Üyelik Onay Kodunuz"

    html_icerik = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; text-align: center;">
        <h2 style="color: #333;">Aramıza Hoş Geldiniz!</h2>
        <p style="color: #666; font-size: 16px;">Kerem AI'a giriş yapmak için tek kullanımlık onay kodunuz aşağıdadır:</p>
        <div style="background-color: #f4f4f4; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h1 style="color: #0b57d0; font-size: 36px; letter-spacing: 5px; margin: 0;">{kod}</h1>
        </div>
        <p style="color: #999; font-size: 12px;">Eğer bu işlemi siz yapmadıysanız, lütfen bu e-postayı dikkate almayın.</p>
    </div>
    """
    mesaj.attach(MIMEText(html_icerik, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gonderici_mail, gonderici_sifre)
        server.send_message(mesaj)
        server.quit()
        return True, "Mail başarıyla gönderildi."
    except Exception as e:
        return False, f"Mail gönderim hatası: {e}"


# --- 2. TAM TASARIMLI ARAYUZ (GEMINI MATERIAL 3 AUTH) ---
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kerem AI - Oturum açın</title>
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
            --google-card-bg: #1f1f1f;
            --google-border: #747775;
            --google-btn-text: #052e59;
        }
        [data-theme="light"] {
            --bg-color: #f0f4f9; 
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
            --google-card-bg: #ffffff;
            --google-border: #747775;
            --google-btn-text: #ffffff;
        }
        body { 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
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

        /* --- GOOGLE MATERIAL 3 AUTH EKRANI CSS --- */
        #auth-screen {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background-color: var(--bg-color);
            display: flex; justify-content: center; align-items: center;
            z-index: 9999; transition: opacity 0.5s;
        }
        .google-card {
            background-color: var(--google-card-bg);
            border-radius: 28px;
            width: 100%; max-width: 448px;
            padding: 48px 40px 36px 40px;
            box-sizing: border-box;
            text-align: left;
            display: flex; flex-direction: column;
        }
        .google-logo svg {
            width: 48px; height: 48px; fill: var(--accent); margin-bottom: 8px;
        }
        .google-title {
            font-size: 32px; font-weight: 400; margin: 16px 0 8px 0; color: var(--text-color);
        }
        .google-subtitle {
            font-size: 16px; font-weight: 400; color: var(--text-color); margin: 0 0 40px 0; opacity: 0.8;
        }
        .google-input-wrapper { position: relative; margin-bottom: 10px; }
        .google-input {
            width: 100%; height: 56px; box-sizing: border-box;
            padding: 16px 14px; border-radius: 4px;
            border: 1px solid var(--google-border);
            background: transparent; color: var(--text-color); font-size: 16px;
            outline: none; transition: 0.2s;
        }
        .google-input:focus {
            border: 2px solid var(--accent); padding: 15px 13px; /* border kalinlasinca paddingi azaltiyoruz */
        }
        .google-input::placeholder { color: transparent; }
        .google-label {
            position: absolute; left: 14px; top: 18px; color: var(--google-border);
            font-size: 16px; transition: 0.2s; pointer-events: none; background: var(--google-card-bg); padding: 0 4px;
        }
        .google-input:focus ~ .google-label, .google-input:not(:placeholder-shown) ~ .google-label {
            top: -9px; left: 10px; font-size: 12px; color: var(--accent);
        }
        .google-input:not(:focus):not(:placeholder-shown) ~ .google-label { color: var(--google-border); }
        
        .google-help-text { font-size: 14px; color: var(--accent); font-weight: 500; cursor: pointer; margin-bottom: 40px; display: inline-block;}
        
        .google-actions {
            display: flex; justify-content: space-between; align-items: center; margin-top: 24px;
        }
        .google-text-btn {
            background: transparent; border: none; color: var(--accent); font-size: 14px;
            font-weight: 500; cursor: pointer; padding: 8px; border-radius: 4px; transition: 0.2s;
        }
        .google-text-btn:hover { background-color: rgba(168, 199, 250, 0.08); }
        .google-primary-btn {
            background-color: var(--accent); color: var(--google-btn-text);
            border: none; border-radius: 100px; padding: 0 24px; height: 40px;
            font-size: 14px; font-weight: 500; cursor: pointer; transition: 0.2s;
            display: flex; align-items: center; justify-content: center;
        }
        .google-primary-btn:hover { opacity: 0.9; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
        
        .auth-spinner { display: none; width: 14px; height: 14px; border: 2px solid var(--google-btn-text); border-top-color: transparent; border-radius: 50%; animation: spin 1s infinite; margin-right: 8px;}
        /* ---------------------- */

        /* Geri kalan sohbet CSS kodlari birebir ayni */
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

    <!-- GOOGLE MATERIAL 3 AUTH EKRANI -->
    <div id="auth-screen">
        <!-- 1. Adim: E-Posta Girisi -->
        <div class="google-card" id="auth-step-1">
            <div class="google-logo">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            </div>
            <h1 class="google-title">Oturum açın</h1>
            <p class="google-subtitle">Kerem AI hesabınıza devam edin</p>
            
            <div class="google-input-wrapper">
                <input type="email" id="auth-email" class="google-input" placeholder=" " onkeypress="if(event.key === 'Enter') mailGonder()">
                <label class="google-label">E-posta veya telefon</label>
            </div>
            <span class="google-help-text" onclick="alert('Demo versiyonu, şimdilik mailinizi girmeniz yeterli.')">E-posta adresinizi mi unuttunuz?</span>
            
            <div class="google-actions">
                <button class="google-text-btn">Hesap oluşturun</button>
                <button class="google-primary-btn" onclick="mailGonder()">
                    <span class="auth-spinner" id="btn1-spinner"></span> İleri
                </button>
            </div>
        </div>
        
        <!-- 2. Adim: Kod Girisi -->
        <div class="google-card" id="auth-step-2" style="display: none;">
            <div class="google-logo">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            </div>
            <h1 class="google-title">2 Adımlı Doğrulama</h1>
            <p class="google-subtitle">Bu e-postaya gönderilen 6 haneli kodu girin</p>
            
            <div class="google-input-wrapper">
                <input type="text" id="auth-code" class="google-input" placeholder=" " maxlength="6" onkeypress="if(event.key === 'Enter') koduDogrula()">
                <label class="google-label">Kodu girin</label>
            </div>
            <span class="google-help-text" onclick="document.getElementById('auth-step-2').style.display='none'; document.getElementById('auth-step-1').style.display='flex';">Geri Dön</span>
            
            <div class="google-actions">
                <button class="google-text-btn">Kodu tekrar gönder</button>
                <button class="google-primary-btn" onclick="koduDogrula()">
                    <span class="auth-spinner" id="btn2-spinner"></span> Onayla
                </button>
            </div>
        </div>
    </div>
    <!-- /AUTH EKRANI -->

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
        <div style="margin-top:auto; padding-top:15px; border-top: 1px solid var(--bot-border); text-align:center; font-size:12px; color:#888;">
            Oturum: <span id="user-email-display"></span><br>
            <a href="#" onclick="cikisYap()" style="color:#ff5252; text-decoration:none;">Çıkış Yap</a>
        </div>
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
                <div class="chips-container">
                    <div class="chip" onclick="hizliSor('AÖF ders notlarımı inceleyip benim için özet çıkarır mısın?')">📚 AOF Ders Ozeti Cikar</div>
                    <div class="chip" onclick="hizliSor('Python kodumda hata alıyorum, mantık hatalarını nasıl ayıklayabilirim?')">💻 Python Hata Ayiklama</div>
                    <div class="chip" onclick="hizliSor('Bana Ammice Arapça (Suudi Arabistan) günlük diyalog kalıplarıyla pratik yaptır.')">🇸🇦 Ammice Arapca Pratik</div>
                    <div class="chip" onclick="hizliSor('Tell me a short story in English to improve my vocabulary.')">🇬🇧 Ingilizce Pratik Yap</div>
                </div>
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
        let userEmail = localStorage.getItem("kerem_user_email");
        
        if (userEmail) {
            document.getElementById('auth-screen').style.display = 'none';
            document.getElementById('user-email-display').innerText = userEmail;
        }

        async function mailGonder() {
            const email = document.getElementById("auth-email").value;
            if(!email.includes("@")) return alert("Lütfen geçerli bir e-posta girin.");
            
            document.getElementById("btn1-spinner").style.display = "inline-block";
            
            try {
                const response = await fetch('/api/kayit_ol', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email })
                });
                const data = await response.json();
                
                if (data.durum === "basarili") {
                    document.getElementById('auth-step-1').style.display = 'none';
                    document.getElementById('auth-step-2').style.display = 'flex'; // Card icin flex gerekiyor
                } else {
                    alert(data.mesaj);
                }
            } catch (error) { alert("Sunucuyla bağlantı kurulamadı."); }
            
            document.getElementById("btn1-spinner").style.display = "none";
        }

        async function koduDogrula() {
            const email = document.getElementById("auth-email").value;
            const kod = document.getElementById("auth-code").value;
            if(!kod) return alert("Lütfen kodu girin.");

            document.getElementById("btn2-spinner").style.display = "inline-block";
            
            try {
                const response = await fetch('/api/kodu_onayla', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, kod: kod })
                });
                const data = await response.json();
                
                if (data.durum === "basarili") {
                    userEmail = email;
                    localStorage.setItem("kerem_user_email", email);
                    
                    if (!deviceId) { 
                        deviceId = "user_" + Math.random().toString(36).substr(2, 9); 
                        localStorage.setItem("kerem_device_id", deviceId); 
                    }
                    
                    document.getElementById('user-email-display').innerText = userEmail;
                    document.getElementById('auth-screen').style.display = 'none';
                    location.reload(); 
                } else {
                    alert(data.mesaj);
                }
            } catch (error) { alert("Sunucuyla bağlantı kurulamadı."); }
            
            document.getElementById("btn2-spinner").style.display = "none";
        }

        function cikisYap() {
            localStorage.removeItem("kerem_user_email");
            location.reload();
        }

        if (!deviceId) { deviceId = "user_" + Math.random().toString(36).substr(2, 9); localStorage.setItem("kerem_device_id", deviceId); }
        let currentSessionId = deviceId + "_" + Date.now();
        let isFirstMessage = true;
        const userInput = document.getElementById("user-input");
        const fileInput = document.getElementById("file-input");

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

        async function sohbetleriYukle() {
            if(!userEmail) return;
            try {
                const res = await fetch('/api/sohbetler?user_id=' + userEmail);
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
                const res = await fetch('/api/sohbet/sil-tum?user_id=' + userEmail, { method: 'DELETE' });
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
            if (fileInput.files.length > 0) { displayMsg = "📎 <b>" + fileInput.files[0].name + "</b>" + (currentMsg ? "<br>" + currentMsg : ""); }
            
            chat.innerHTML += '<div class="message-wrapper"><div class="message user-msg">' + displayMsg + '</div></div>';
            
            const formData = new FormData();
            formData.append("mesaj", currentMsg);
            formData.append("session_id", currentSessionId); 
            formData.append("user_id", userEmail);
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

@app.route('/api/kayit_ol', methods=['POST'])
def kayit_ol():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"durum": "hata", "mesaj": "Lütfen e-posta adresi girin."}), 400

    kod = onay_kodu_uret()
    
    try:
        firestore.client().collection('onay_bekleyenler').document(email).set({
            'kod': kod,
            'email': email,
            'zaman': firestore.SERVER_TIMESTAMP
        })
        
        basarili, mesaj = onay_maili_gonder(email, kod)
        
        if basarili:
            return jsonify({"durum": "basarili", "mesaj": "Kod mailinize gönderildi!"})
        else:
            return jsonify({"durum": "hata", "mesaj": mesaj}), 500
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

@app.route('/api/kodu_onayla', methods=['POST'])
def kodu_onayla():
    data = request.json
    email = data.get('email')
    girilen_kod = data.get('kod')

    try:
        doc_ref = firestore.client().collection('onay_bekleyenler').document(email)
        doc = doc_ref.get()

        if doc.exists and doc.to_dict().get('kod') == girilen_kod:
            firestore.client().collection('aktif_uyeler').document(email).set({
                'email': email,
                'durum': 'onayli',
                'kayit_tarihi': firestore.SERVER_TIMESTAMP
            })
            doc_ref.delete() 
            return jsonify({"durum": "basarili", "mesaj": "Üyeliğiniz onaylandı!"})
        else:
            return jsonify({"durum": "hata", "mesaj": "Geçersiz onay kodu!"}), 400
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

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
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    reply = ask_ai(update.message.text, f"tg_{update.message.from_user.id}")
    await update.message.reply_text(reply)

async def ses_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    bekleme = await update.message.reply_text("🎧 Dinleniyor...")
    dosya_adi = f"temp_{update.message.from_user.id}.ogg"
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        await file.download_to_drive(dosya_adi)
        reply = ask_ai("Bu sesli mesaja yanit ver.", user_id, image_path=dosya_adi)
        await bekleme.edit_text(reply)
    finally:
        if os.path.exists(dosya_adi): os.remove(dosya_adi)

async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    await update.message.reply_text("📥 Dosya alindi, analiz ediliyor...")
    await update.message.reply_text("Dosya analizi tamamlandı.")

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧹 Hafıza zaten RAG ile kaldırıldığı için bu işlem geçersiz kılındı.")

def run_telegram_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ HATA: TELEGRAM_BOT_TOKEN tanımlı değil!", flush=True)
        return
    
    app_bot = Application.builder().token(token).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Kerem AI Hazir.")))
    app_bot.add_handler(CommandHandler("temizle", temizle_command)) 
    app_bot.add_handler(MessageHandler(filters.Document.PDF, dosya_al))
    app_bot.add_handler(MessageHandler(filters.VOICE, ses_al))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    print("🚀 Telegram bot polling başlatılıyor...", flush=True)
    app_bot.run_polling(drop_pending_updates=True)

# --- 5. UYGULAMAYI BAŞLATMA ---
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
        # GEMINI TASARIMI VE MAIL SISTEMI ZORUNLU GUNCELLEME