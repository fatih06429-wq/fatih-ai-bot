import os
import threading
import asyncio
import time
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from ai import ask_ai, hafizayi_temizle
from firebase_admin import firestore

# --- Flask Uygulaması ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# HTML sayfası aynı, buraya dokunmadık.
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>Kerem AI</title></head>
<body><h1>Kerem AI Web Arayüzü</h1></body>
</html>
"""

@app.route("/")
def ana_sayfa(): return render_template_string(HTML_SAYFASI)

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
        hafizayi_temizle(session_id)
        return jsonify({"status": "success"})
    except: return jsonify({"status": "error"}), 500

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    mesaj = request.form.get("mesaj", "")
    session_id = request.form.get("session_id", "")
    user_id = request.form.get("user_id", "")
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

# --- Telegram Bot Fonksiyonları ---
async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"tg_{update.message.from_user.id}"
    bekleme = await update.message.reply_text("📥 İşleniyor...")
    dosya_adi = f"tg_doc_{user_id}_{int(time.time())}.pdf"
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        await file.download_to_drive(dosya_adi)
        reply = ask_ai(update.message.caption or "Analiz et", user_id, image_path=dosya_adi)
        await bekleme.edit_text(reply)
    except Exception as e: await bekleme.edit_text(f"Hata: {e}")
    finally:
        if os.path.exists(dosya_adi): os.remove(dosya_adi)

async def chat(update, context): 
    reply = ask_ai(update.message.text, f"tg_{update.message.from_user.id}")
    await update.message.reply_text(reply)

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app_bot = Application.builder().token("8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0").build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Kerem AI Hazır.")))
    app_bot.add_handler(CommandHandler("temizle", lambda u, c: hafizayi_temizle(f"tg_{u.message.from_user.id}")))
    app_bot.add_handler(MessageHandler(filters.Document.PDF, dosya_al))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app_bot.run_polling()

# --- Uygulama Başlatma ---
if __name__ == '__main__':
    # Flask arka planda çalışacak
    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Telegram botu main thread'de çalışacak
    run_telegram_bot()
