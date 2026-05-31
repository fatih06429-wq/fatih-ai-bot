print("--- ADIM 1: bot.py İLK SATIR ÇALIŞTI ---", flush=True)
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import os

from ai import ask_ai, hafizayi_temizle
from db import save
from ses import sesi_metne_cevir
print("ADIM 1: Kütüphaneler yüklendi")

TOKEN = "8864490425:AAH8Xm4buW-DfeUgTkMYTKdPJ8mQNLx59q0"
print("ADIM 2: Token alındı")
print(f"--- ADIM 2: Token okundu ---", flush=True)

print("🔥 BOT BAŞLADI")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    mesaj = "Merhaba! Ben yapay zeka asistanınım. Benimle dilediğin konuda sohbet edebilirsin. Neler yapmak istersin?"
    print(f"KOMUT GELDİ (ID: {user_id}): /start")
    await update.message.reply_text(mesaj)
    save(user_id, "/start", mesaj)

async def yardim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    mesaj = "Bana doğrudan bir mesaj yazarak sohbet edebilirsin. Hafızam var, önceki konuştuklarımızı hatırlarım!\n\nKomutlar:\n/start - Botu yeniden başlatır\n/yardim - Bu menüyü gösterir\n/temizle - Sohbet geçmişini sıfırlar"
    print(f"KOMUT GELDİ (ID: {user_id}): /yardim")
    await update.message.reply_text(mesaj)

async def temizle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    hafizayi_temizle(user_id)
    mesaj = "🧹 Hafızam tamamen temizlendi! Artık yepyeni bir sayfa açtık. Ne konuşalım?"
    print(f"KOMUT GELDİ (ID: {user_id}): /temizle")
    await update.message.reply_text(mesaj)
    save(user_id, "/temizle", mesaj)

async def ses_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    bekleme_mesaji = await update.message.reply_text("🎧 Sesli mesajın dinleniyor...")
    dosya_adi = f"ses_{user_id}.ogg"
    
    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        await file.download_to_drive(dosya_adi)
        print(f"SES GELDİ (ID: {user_id}) - İndiriliyor...")

        kullanici_metni = sesi_metne_cevir(dosya_adi)
        print(f"SESTEN ÇEVRİLEN METİN: {kullanici_metni}")

        if kullanici_metni.startswith("HATA:") or not kullanici_metni:
            await bekleme_mesaji.edit_text("Sesini tam anlayamadım, tekrar dener misin?")
        else:
            await bekleme_mesaji.edit_text(f"🗣️ *Sen:* {kullanici_metni}\n\n🧠 Düşünüyorum...", parse_mode="Markdown")
            reply = ask_ai(kullanici_metni, user_id)
            print("AI CEVAP:", reply)
            await update.message.reply_text(reply)
            save(user_id, f"(Ses) {kullanici_metni}", reply)
            
    finally:
        if os.path.exists(dosya_adi):
            os.remove(dosya_adi)

# YENİ EKLENEN FONKSİYON: Fotoğrafları yakalar
async def fotograf_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    # Fotoğrafla birlikte gönderilen bir metin var mı kontrol ediyoruz
    caption = update.message.caption if update.message.caption else "Bu fotoğrafta ne görüyorsun? Lütfen Türkçe açıkla."
    
    bekleme_mesaji = await update.message.reply_text("📸 Fotoğraf inceleniyor (Bu işlem biraz sürebilir)...")
    dosya_adi = f"foto_{user_id}.jpg"
    
    try:
        # Telegram fotoğrafları farklı boyutlarda gönderir, en yüksek kalitedekini (sonuncuyu) alıyoruz
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        await file.download_to_drive(dosya_adi)
        print(f"FOTOĞRAF GELDİ (ID: {user_id}) - İndirildi.")

        # ai.py'deki fonksiyona fotoğraf yolunu da gönderiyoruz
        reply = ask_ai(caption, user_id, image_path=dosya_adi)
        print("AI CEVAP (Fotoğraf):", reply)

        await bekleme_mesaji.edit_text(reply)
        save(user_id, f"(Fotoğraf) {caption}", reply)

    finally:
        # Depolama dolmasın diye fotoğrafı siliyoruz
        if os.path.exists(dosya_adi):
            os.remove(dosya_adi)

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.message.from_user.id) 
    print(f"MESAJ GELDİ (ID: {user_id}): {user_text}")

    reply = ask_ai(user_text, user_id)
    print("AI CEVAP:", reply)

    await update.message.reply_text(reply)
    save(user_id, user_text, reply)

print("--- ADIM 3: Bot uygulaması başlatılıyor ---", flush=True)
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("yardim", yardim_command))
app.add_handler(CommandHandler("temizle", temizle_command))
app.add_handler(MessageHandler(filters.VOICE, ses_al))

# YENİ: Fotoğrafları (PHOTO) yakalayacak dinleyici eklendi
app.add_handler(MessageHandler(filters.PHOTO, fotograf_al))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("RUNNING...")
app.run_polling()
