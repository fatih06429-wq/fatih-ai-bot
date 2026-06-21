import os
import json
import threading
import time
import asyncio
import re
import datetime
import requests
import hashlib
import base64

from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatJoinRequestHandler

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
SUPER_ADMIN_ID = 7082795768  
MAKSIMUM_DOSYA_BOYUTU = 5 * 1024 * 1024 
# Geliştirilmiş Jailbreak / Prompt Injection Listesi
TEHLIKELI_PROMPTLAR = [
    "unut", "ignore", "sistem", "system prompt", "kurallar", "şifre", 
    "bypass", "jailbreak", "sen bir", "önceki talimat", "override", 
    "developer mode", "geliştirici modu", "çekirdek"
]
YASAKLI_KELIMELER = ["bahis", "kumar", "şans oyunu", "illegal", "bet", "casino"]

kullanici_mesaj_zamanlari = {}
aktif_silme_gorevleri = set()
grup_durumlari = {}   

# --- 1. FIREBASE BAŞLATMA ---
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

# 🧠 FIREBASE KALICI HAFIZA (Gruplar ve Kara Liste)
def gruplari_yukle():
    try:
        doc = firestore.client().collection("bot_ayarlar").document("aktif_gruplar").get()
        if doc.exists: return set(doc.to_dict().get("liste", []))
    except: pass
    return set()

def grubu_kaydet(chat_id):
    try:
        firestore.client().collection("bot_ayarlar").document("aktif_gruplar").set({
            "liste": firestore.ArrayUnion([chat_id])
        }, merge=True)
    except: pass

def kara_liste_yukle():
    try:
        doc = firestore.client().collection("bot_ayarlar").document("kara_liste").get()
        if doc.exists: return set(doc.to_dict().get("liste", []))
    except: pass
    return set()

def kara_listeye_ekle(user_id):
    try:
        firestore.client().collection("bot_ayarlar").document("kara_liste").set({
            "liste": firestore.ArrayUnion([user_id])
        }, merge=True)
    except: pass

aktif_gruplar = gruplari_yukle()
kara_liste = kara_liste_yukle()

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
    except Exception: pass

# --- 2. WEB ARAYÜZÜ (Önceki kod ile birebir aynı) ---
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kerem AI - Yapay Zeka Asistani</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #131314; color: #e3e3e3; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .container { text-align: center; }
        h1 { color: #a8c7fa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Kerem AI Aktif 🚀</h1>
        <p>Siber Güvenlik Kalkanları Devrede.</p>
    </div>
</body>
</html>
"""

@app.route("/")
def ana_sayfa(): 
    return render_template_string(HTML_SAYFASI)

# --- 3. TELEGRAM BOT GÜVENLİK VE YÖNETİM FONKSİYONLARI ---

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id == SUPER_ADMIN_ID: return True
    if update.effective_chat.type == 'private': return False
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return chat_member.status in ['administrator', 'creator']

# 🔴 MODÜL 1: GLOBAL BAN (Tüm Ağdan Kalıcı Yasaklama)
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Lütfen yasaklamak istediğiniz kişinin bir mesajını yanıtlayarak /ban yazın.")
    
    target_user = update.message.reply_to_message.from_user
    if target_user.id == SUPER_ADMIN_ID:
        return await update.message.reply_text("⛔ Güvenlik Kalkanı: Sistem kurucusu yasaklanamaz!")

    try:
        # Önce bu gruptan at
        await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_user.id)
        # Firebase Kara Listeye Ekle (Global Ban)
        kara_listeye_ekle(target_user.id)
        kara_liste.add(target_user.id)
        
        await update.message.reply_text(f"🔨 {target_user.first_name} Kerem AI tarafından <b>GLOBAL KARA LİSTEYE</b> eklendi. Artık hiçbir grubumuza giremez.", parse_mode='HTML')
        await rapor_ver(context, "GLOBAL BAN", f"Yönetici, {target_user.first_name} adlı kişiyi global olarak ağdan engelledi.")
    except Exception: pass

async def manuel_ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sadece yöneticiler kullanabilsin
    if not await is_admin(update, context):
        return await update.message.reply_text("⛔ Bu komutu sadece yöneticiler kullanabilir.")

    # Yanıtlanan mesajı kontrol et
    if not update.message.reply_to_message:
        return await update.message.reply_text("Lütfen engelini kaldırmak istediğiniz kişinin bir mesajına yanıt vererek bu komutu kullanın.")

    uye = update.message.reply_to_message.from_user
    
    try:
        # Kısıtlamaları kaldır
        permissions = ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True, 
            can_send_photos=True, can_send_videos=True, can_send_other_messages=True
        )
        await context.bot.restrict_chat_member(update.message.chat_id, uye.id, permissions)
        await update.message.reply_text(f"✅ {uye.first_name} üzerindeki kısıtlamalar manuel olarak kaldırıldı.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata: {e}")

# 🟡 MODÜL 2: ANTI-RAID VE CAPTCHA
# Bu fonksiyonu, hem 'new_chat_members' hem de 'ChatJoinRequest' ile çalışacak şekilde güncelledik.
async def yeni_uye_karsilama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # EĞER İSTEK ÜZERİNE GELDİYSE (Kullanıcı henüz grupta değil, sen onaylayacaksın)
    if update.chat_join_request:
        istek = update.chat_join_request
        # Önce sen manuel onaylamadan bot burayı çalıştırmasın, o yüzden önce onayla
        await context.bot.approve_chat_join_request(chat_id=istek.chat.id, user_id=istek.from_user.id)
        uye = istek.from_user
        chat_id = istek.chat.id
    # EĞER NORMAL GİRİŞ YAPTILARSA (Senin mevcut kodun)
    elif update.message and update.message.new_chat_members:
        uye = update.message.new_chat_members[0]
        chat_id = update.message.chat_id
        if uye.is_bot: return
    else:
        return

    # Kısıtlama ve Buton İşlemleri (Ortak Alan)
    try:
        await context.bot.restrict_chat_member(
            chat_id, uye.id, ChatPermissions(can_send_messages=False)
        )
        keyboard = [[InlineKeyboardButton("✅ Ben bot değilim", callback_data=f"captcha_{uye.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        uyari_mesaji = await context.bot.send_message(
            chat_id=chat_id,
            text=f"Hoş geldin {uye.first_name}! 🛡️\nSohbete dahil olmak için lütfen aşağıdaki butona tıkla:",
            reply_markup=reply_markup
        )
        
        # 60 Saniye Kuralı (Aynı kalıyor)
        async def kural_ihlali():
            await asyncio.sleep(60)
            try:
                member = await context.bot.get_chat_member(chat_id, uye.id)
                if not member.status in ['left', 'kicked', 'restricted']: # Basit bir kontrol
                    await context.bot.ban_chat_member(chat_id, uye.id)
                    await context.bot.unban_chat_member(chat_id, uye.id)
            except Exception: pass
        asyncio.create_task(kural_ihlali())
    except Exception as e:
        print(f"Hata: {e}")

async def captcha_dogrulama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target_id = int(query.data.split("_")[1])
    
    if query.from_user.id != target_id:
        return await query.answer("Bu buton senin için değil!", show_alert=True)
    
    try:
        # Yetkileri geri ver
        permissions = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
        await context.bot.restrict_chat_member(query.message.chat_id, target_id, permissions)
        await query.message.delete()
        await query.answer("Doğrulama başarılı! Aramıza hoş geldin.")
    except Exception: pass

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not update.message or not update.message.text: return
    mesaj = update.message.text.lower()

    # 🟤 MODÜL 4: GELİŞMİŞ JAILBREAK / PROMPT INJECTION KALKANI
    for tehlike in TEHLIKELI_PROMPTLAR:
        if re.search(r'\b' + re.escape(tehlike) + r'\b', mesaj):
            grup_adi = update.message.chat.title if update.message.chat.title else "Özel Sohbet"
            await rapor_ver(context, "Sistem Kırma Girişimi (Jailbreak)", f"{update.message.from_user.first_name}, {grup_adi} içinde şu tehlikeli komutu denedi: '{tehlike}'")
            return await update.message.reply_text("🛡️ <b>Siber Güvenlik Kalkanı:</b> Sistem çekirdeğine müdahale girişimi reddedildi.", parse_mode='HTML')

    bekleme = await update.message.reply_text("🧠 Düşünüyorum...")
    try:
        reply = ask_ai(update.message.text, f"tg_{update.message.from_user.id}")
        if not reply: reply = "⚠️ Yapay zeka bana boş bir yanıt döndürdü."
        await bekleme.edit_text(reply)
    except Exception as e:
        await bekleme.edit_text(f"⚠️ Hata: {str(e)}")

# DOSYA TARAMA MODÜLÜ
async def dosya_al(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.document.file_size > MAKSIMUM_DOSYA_BOYUTU and user_id != SUPER_ADMIN_ID:
        await update.message.reply_text("🛑 Güvenlik Kalkanı: Dosya boyutu çok büyük (Max 5MB).")
        return

    bekleme_mesaji = await update.message.reply_text("🛡️ Dosya Karantinaya Alındı. Virüs Taraması Yapılıyor...")
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        dosya_adi = f"temp_{user_id}_{update.message.document.file_name}"
        await file.download_to_drive(dosya_adi)
        
        vt_api_key = os.environ.get("VIRUSTOTAL_API_KEY")
        if vt_api_key:
            sha256_hash = hashlib.sha256()
            with open(dosya_adi, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""): sha256_hash.update(byte_block)
            
            url = f"https://www.virustotal.com/api/v3/files/{sha256_hash.hexdigest()}"
            headers = {"x-apikey": vt_api_key}
            vt_response = requests.get(url, headers=headers)

            if vt_response.status_code == 200 and vt_response.json()['data']['attributes']['last_analysis_stats']['malicious'] > 0:
                os.remove(dosya_adi) 
                await bekleme_mesaji.edit_text("🚨 <b>KRİTİK UYARI:</b> Zararlı yazılım tespit edildi ve imha edildi!", parse_mode='HTML')
                await rapor_ver(context, "MALWARE TESPİTİ 🦠", f"Kullanıcı virüslü dosya yükledi.")
                return 
                    
        await bekleme_mesaji.edit_text("✅ Temiz. Okunuyor...")
        reply = ask_ai("Bu belgeyi analiz et ve özetle.", f"tg_{user_id}", image_path=dosya_adi)
        await bekleme_mesaji.edit_text(reply)
    except Exception as e:
        await bekleme_mesaji.edit_text(f"⚠️ Hata oluştu.")
    finally:
        if 'dosya_adi' in locals() and os.path.exists(dosya_adi): os.remove(dosya_adi)

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
    if not update.message or not update.message.text: return
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    # 🔴 Global Ban Kontrolü
    if user_id in kara_liste:
        try: 
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await update.message.delete()
        except: pass
        return

    if update.message.chat and update.message.chat.type in ['group', 'supergroup']:
        if chat_id not in aktif_gruplar:
            aktif_gruplar.add(chat_id)
            grubu_kaydet(chat_id)

    mesaj = update.message.text.lower()
    kullanici_adi = update.message.from_user.first_name

    if user_id == SUPER_ADMIN_ID: return

    # Spam Kontrolü
    simdi = time.time()
    if user_id not in kullanici_mesaj_zamanlari: kullanici_mesaj_zamanlari[user_id] = []
    kullanici_mesaj_zamanlari[user_id] = [t for t in kullanici_mesaj_zamanlari[user_id] if simdi - t < 7]
    kullanici_mesaj_zamanlari[user_id].append(simdi)
    if len(kullanici_mesaj_zamanlari[user_id]) >= 5:
        uyari = await context.bot.send_message(chat_id=chat_id, text=f"🛑 {kullanici_adi} spam engeline takıldı!")
        gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
        try: await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=ChatPermissions(can_send_messages=False))
        except: pass
        kullanici_mesaj_zamanlari[user_id] = []
        return

    # Yasaklı Kelime
    if any(kelime in mesaj for kelime in YASAKLI_KELIMELER):
        try: await update.message.delete()
        except: pass
        uyari = await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {kullanici_adi}, yasaklı kelime kullandın!")
        gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
        return

    # 🟢 MODÜL 3: PHISHING VE LİNK ANALİZÖRÜ
    link_sablonu = r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+)"
    bulunan_link = re.search(link_sablonu, mesaj)
    
    if bulunan_link:
        url = bulunan_link.group(0)
        is_user_admin = await is_admin(update, context)
        
        if not is_user_admin:
            try: await update.message.delete()
            except: pass
            uyari = await context.bot.send_message(chat_id=chat_id, text=f"🚫 {kullanici_adi}, grupta izinsiz link paylaşımı yasaktır!")
            gorevi_guvenli_baslat(context.bot, chat_id, uyari.message_id)
            return
        else:
            # Yönetici link attıysa VirusTotal ile Phishing taraması yap
            vt_api_key = os.environ.get("VIRUSTOTAL_API_KEY")
            if vt_api_key:
                try:
                    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
                    vt_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
                    headers = {"x-apikey": vt_api_key}
                    vt_response = requests.get(vt_url, headers=headers)
                    if vt_response.status_code == 200:
                        zararli = vt_response.json()['data']['attributes']['last_analysis_stats']['malicious']
                        if zararli > 0:
                            await update.message.delete()
                            await update.message.reply_text(f"🚨 <b>PHISHING UYARISI:</b> Yönetici bile olsa, paylaşılan '{url}' linkinde zararlı/oltalama aktivitesi tespit edildiği için sistem linki imha etti!", parse_mode='HTML')
                            await rapor_ver(context, "PHISHING TESPİTİ", f"Grupta zararlı bir link engellendi: {url}")
                except Exception: pass

# ⏱️ GECE BEKÇİSİ
async def gece_bekcisi(bot):
    KAPANIS_SAATI = 1  
    ACILIS_SAATI = 8   
    while True:
        try:
            simdi = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            saat = simdi.hour
            gece_mi = KAPANIS_SAATI <= saat < ACILIS_SAATI
            
            for chat_id in list(aktif_gruplar):
                durum = grup_durumlari.get(chat_id, None)
                if durum is None:
                    grup_durumlari[chat_id] = "KAPALI" if gece_mi else "ACIK"
                    if gece_mi: await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                    continue
                if gece_mi and durum != "KAPALI":
                    await bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                    await bot.send_message(chat_id, f"🌙 <b>Saat 0{KAPANIS_SAATI}:00 oldu.</b>\n\nGrup sabah 0{ACILIS_SAATI}:00'a kadar mesaj gönderimine kapatılmıştır. Herkese İyi Geceler!", parse_mode='HTML')
                    grup_durumlari[chat_id] = "KAPALI"
                elif not gece_mi and durum == "KAPALI":
                    permissions = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
                    await bot.set_chat_permissions(chat_id, permissions)
                    await bot.send_message(chat_id, f"☀️ <b>Saat 0{ACILIS_SAATI}:00 oldu.</b>\n\nGrup mesaj gönderimine açılmıştır. Günaydın!", parse_mode='HTML')
                    grup_durumlari[chat_id] = "ACIK"
        except Exception: pass
        await asyncio.sleep(15) 

async def post_init(application: Application):
    asyncio.create_task(gece_bekcisi(application.bot))

def run_telegram_bot():
    print("⏳ Render devir teslimi için 20 saniye bekleniyor (Çakışma önleyici)...", flush=True)
    time.sleep(20)  
    
    token = "8736315853:AAHBp8IoQX4i8GsBFJ96jfZnQCUTFXIHdkQ"
    if not token or "BURAYA" in token:
        print("❌ HATA: Telegram Token'ı kodun içinde tanımlanmamış!", flush=True)
        return
    
    app_bot = Application.builder().token(token).post_init(post_init).build()
    
    app_bot.add_handler(CommandHandler("ban", ban_command))
    app_bot.add_handler(CommandHandler("ac", manuel_ac))
    # Mevcut komutların (ban ve ac) altına şunları ekle:
    app_bot.add_handler(ChatJoinRequestHandler(yeni_uye_karsilama))
    app_bot.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye_karsilama))
    
    # Yeni Üye Karşılama ve CAPTCHA 
    app_bot.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye_karsilama))
    app_bot.add_handler(CallbackQueryHandler(captcha_dogrulama, pattern="^captcha_"))
    
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, otomatik_moderasyon), group=-1)
    
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Kerem AI Hazir.")))
    
    app_bot.add_handler(MessageHandler(filters.Document.ALL, dosya_al))
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

    try:    
        run_telegram_bot()
    except Exception as e:
        print(f"❌ BOT CRITICAL ERROR: {e}", flush=True)
