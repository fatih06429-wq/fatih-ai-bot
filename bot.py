HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yapay Zeka Asistanı</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        h2 { color: #4CAF50; }
        #chat-container { width: 100%; max-width: 700px; background-color: #1e1e1e; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); padding: 20px; display: flex; flex-direction: column; height: 70vh; }
        #chat-box { flex: 1; overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 15px; }
        .message { padding: 12px 16px; border-radius: 12px; max-width: 80%; line-height: 1.4; word-wrap: break-word; }
        .user-msg { background-color: #2196F3; align-self: flex-end; border-bottom-right-radius: 2px; }
        .bot-msg { background-color: #333333; align-self: flex-start; border-bottom-left-radius: 2px; }
        #input-area { display: flex; gap: 10px; margin-top: 20px; }
        input[type="text"] { flex: 1; padding: 15px; border-radius: 8px; border: 1px solid #444; background-color: #2d2d2d; color: white; font-size: 16px; outline: none; }
        input[type="text"]:focus { border-color: #4CAF50; }
        button { padding: 15px 25px; border-radius: 8px; border: none; background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { background-color: #45a049; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1e1e1e; }
        ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
    </style>
</head>
<body>
    <h2>🤖 Yapay Zeka Asistanı</h2>
    <div id="chat-container">
        <div id="chat-box">
            <div class="message bot-msg"><b>Asistan:</b> Merhaba! Sana nasıl yardımcı olabilirim?</div>
        </div>
        <div id="input-area">
            <input type="text" id="user-input" placeholder="Mesajını yaz..." onkeypress="if(event.key === 'Enter') mesajGonder()">
            <button onclick="mesajGonder()">Gönder</button>
        </div>
    </div>
    <script>
        async function mesajGonder() {
            const inputElement = document.getElementById("user-input");
            const mesaj = inputElement.value.trim();
            if (!mesaj) return;
            
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML += `<div class="message user-msg"><b>Sen:</b> ${mesaj}</div>`;
            inputElement.value = "";
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch("/api/sor", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mesaj: mesaj })
                });
                const data = await response.json();
                chatBox.innerHTML += `<div class="message bot-msg"><b>Asistan:</b> ${data.cevap}</div>`;
            } catch (error) {
                chatBox.innerHTML += `<div class="message bot-msg" style="color: red;"><b>Hata:</b> Bağlantı kurulamadı.</div>`;
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def ana_sayfa():
    return render_template_string(HTML_SAYFASI)

@app.route("/api/sor", methods=["POST"])
def soru_cevapla():
    veri = request.json
    gelen_mesaj = veri.get("mesaj", "")
    # Web kullanıcılarını Firebase'de ayrı bir ID ile tutuyoruz
    cevap = ask_ai(gelen_mesaj, user_id="web_kullanicisi")
    return jsonify({"cevap": cevap})

def web_sunucusunu_baslat():
    port = int(os.environ.get("PORT", 10000))
    # use_reloader=False parametresi Thread içinde çökmeyi engeller
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# Arka planda gerçek web sunucusunu çalıştırıyoruz
sunucu_thread = threading.Thread(target=web_sunucusunu_baslat, daemon=True)
sunucu_thread.start()
print("--- GERÇEK WEB SUNUCUSU AÇILDI VE RENDER SUSTURULDU ---", flush=True)

# --- TELEGRAM VE AI BAĞLANTILARI ---
print("--- TELEGRAM VE OS BAŞARIYLA YÜKLENDİ ---", flush=True)

from ai import ask_ai, hafizayi_temizle
print("--- AI.PY BAŞARIYLA YÜKLENDİ ---", flush=True)

from db import save
print("--- DB.PY BAŞARIYLA YÜKLENDİ ---", flush=True)

print("ADIM 1 TAMAM: Tüm kütüphaneler yüklendi!", flush=True)

# Güvenlik Notu: Token'ını herkese açık yerlerde paylaşmamaya dikkat et.
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

async def fotograf_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    caption = update.message.caption if update.message.caption else "Bu fotoğrafta ne görüyorsun? Lütfen Türkçe açıkla."
    bekleme_mesaji = await update.message.reply_text("📸 Fotoğraf inceleniyor (Bu işlem biraz sürebilir)...")
    dosya_adi = f"foto_{user_id}.jpg"
    
    try:
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        await file.download_to_drive(dosya_adi)
        print(f"FOTOĞRAF GELDİ (ID: {user_id}) - İndirildi.")

        reply = ask_ai(caption, user_id, image_path=dosya_adi)
        print("AI CEVAP (Fotoğraf):", reply)

        await bekleme_mesaji.edit_text(reply)
        save(user_id, f"(Fotoğraf) {caption}", reply)

    finally:
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
app_telegram = Application.builder().token(TOKEN).build()

app_telegram.add_handler(CommandHandler("start", start_command))
app_telegram.add_handler(CommandHandler("yardim", yardim_command))
app_telegram.add_handler(CommandHandler("temizle", temizle_command))
#app_telegram.add_handler(MessageHandler(filters.VOICE, ses_al))
app_telegram.add_handler(MessageHandler(filters.PHOTO, fotograf_al))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("RUNNING...")
app_telegram.run_polling()
