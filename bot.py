import sys
import traceback
import time

try:
    import os
    import json
    import threading
    import asyncio
    from flask import Flask, request, jsonify, render_template_string
    from werkzeug.utils import secure_filename
    from telegram import Update
    from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

    # Modüller
    from ai import ask_ai
    from hafiza import hafizayi_temizle
    import firebase_admin
    from firebase_admin import credentials, firestore

    app = Flask(__name__)
    UPLOAD_FOLDER = 'uploads'
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    # 1. Firebase Başlatma
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

    # 2. Telegram Fonksiyonları
    async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
        reply = ask_ai(update.message.text, f"tg_{update.message.from_user.id}", mode="thinking")
        await update.message.reply_text(reply)
        
    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Kerem AI Hazır.")

    def run_telegram_bot():
        print("🚀 Telegram bot hazirlaniyor...", flush=True)
        token = "8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0"
        app_bot = Application.builder().token(token).build()
        app_bot.add_handler(CommandHandler("start", start_cmd))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
        print("🚀 Telegram bot polling baslatildi.", flush=True)
        app_bot.run_polling()

    # 3. Web Arayüzü
    HTML_SAYFASI = """<!DOCTYPE html><html><body><h1>Kerem AI Aktif</h1></body></html>"""

    @app.route("/")
    def ana_sayfa(): return HTML_SAYFASI

    @app.route("/api/sor", methods=["POST"])
    def soru_cevapla():
        mesaj = request.form.get("mesaj", "")
        session_id = request.form.get("session_id", "default")
        user_id = request.form.get("user_id", "default")
        secilen_mod = request.form.get("mode", "thinking")
        cevap = ask_ai(mesaj, user_id=session_id, mode=secilen_mod)
        return jsonify({"cevap": cevap})

    # 4. Başlatma Bloğu
    if __name__ == '__main__':
        print("🚀 Flask sunucusu baslatiliyor...", flush=True)
        def run_flask():
            port = int(os.environ.get("PORT", 10000))
            app.run(host="0.0.0.0", port=port, use_reloader=False)
        
        threading.Thread(target=run_flask, daemon=True).start()
        run_telegram_bot()

except Exception as e:
    # EĞER ÇÖKERSE SEBEBİNİ ZORLA YAZDIRIYORUZ
    print("\n" + "="*50, flush=True)
    print("!!! KRITIK COKME HATASI !!!", flush=True)
    print("="*50, flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    time.sleep(5) # Render'ın logu ekrana basması için zaman veriyoruz
    sys.exit(1)
