import os
import threading
import asyncio
import time
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

# Modülleri temiz bir şekilde import ediyoruz
from ai import ask_ai
from hafiza import hafizayi_temizle
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Firebase'i başlatırken hata yakalama
try:
    firebase_json = os.environ.get("FIREBASE_JSON")
    if firebase_json:
        cred = credentials.Certificate(json.loads(firebase_json))
        firebase_admin.initialize_app(cred)
        print("✅ Firebase basariyla baslatildi.", flush=True)
except Exception as e:
    print(f"❌ Firebase baslatma hatasi: {e}", flush=True)

# --- WEB ARAYÜZÜ HTML ---
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>Kerem AI</title></head>
<body><h1>Kerem AI Aktif</h1></body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "default")
    user_id = request.form.get("user_id", "default")
    secilen_mod = request.form.get("mode", "thinking")
    cevap = ask_ai(mesaj, user_id=session_id, mode=secilen_mod)
    return jsonify({"cevap": cevap})

# --- UYGULAMAYI BAŞLATMA ---
if __name__ == '__main__':
    # 1. Flask sunucusunu bir thread'de başlat
    def run_flask():
        try:
            port = int(os.environ.get("PORT", 10000))
            app.run(host="0.0.0.0", port=port, use_reloader=False)
        except Exception as e:
            print(f"❌ Flask hatası: {e}", flush=True)
            
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # 2. Telegram botu ana süreçte başlat
    print("🚀 Telegram bot başlatılıyor...", flush=True)
    try:
        run_telegram_bot()
    except Exception as e:
        print(f"❌ Bot başlatma hatası: {e}", flush=True)
