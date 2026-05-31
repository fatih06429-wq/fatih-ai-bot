from google.genai import types
import os
import json
import PIL.Image
from google import genai
from duckduckgo_search import DDGS
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Başlatma
try:
    firebase_json = os.environ.get("FIREBASE_JSON")
    cred = credentials.Certificate(json.loads(firebase_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Veri Tabanı Bağlantısı Başarılı!")
except Exception as e:
    print(f"❌ Firebase başlatılamadı: {e}")
    db = None

sohbet_gecmisi = {}

# Gemini API Başlatma
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)
uygun_model = "gemini-2.5-flash" 

def arama_gerekli_mi(metin):
    guncel_kelimeler = ["hava", "maç", "skor", "haber", "dolar", "euro", "fiyat", "bugün", "tarih", "saat", "deprem"]
    return any(kelime in metin.lower() for kelime in guncel_kelimeler)

def internette_ara(sorgu):
    try:
        with DDGS() as ddgs:
            sonuclar = list(ddgs.text(sorgu, region='tr-tr', safesearch='off', max_results=3))
            return "\n".join([f"- {s['title']}: {s['body']}" for s in sonuclar]) if sonuclar else ""
    except: return ""

def ask_ai(text, user_id, image_path=None):
    bugun = datetime.datetime.now().strftime("%d %B %Y")
    
    # HAFIZA YÜKLEME (Katı Kurallı Sistem - Uydurmayı Engeller)
    if user_id not in sohbet_gecmisi:
        sohbet_gecmisi[user_id] = [
            {"role": "user", "parts": [{"text": f"Sistem: Bugünün tarihi {bugun}. Sen profesyonel, güvenilir ve tarafsız bir yapay zeka asistanısın. En önemli kuralın: BİLMEDİĞİN ŞEYLERİ UYDURMA. Sadece %100 emin olduğun, kanıtlanabilir gerçekleri söyle. Eğer bir sorunun cevabını tam olarak bilmiyorsan, dürüstçe 'Bu konuda kesin bir bilgim yok' veya 'İnternetten kontrol etmem daha sağlıklı olur' de. Her zaman Türkçe yaz."}]},
            {"role": "model", "parts": [{"text": "Anladım. Size sadece doğrulanmış ve kesin bilgiler sunacağım. Bilmediğim konularda dürüstçe belirteceğim ve asla uydurma bilgi vermeyeceğim."}]}
        ]

    # Arama
    arama_sonucu = internette_ara(text) if arama_gerekli_mi(text) else ""
    full_text = f"İnternet verileri: {arama_sonucu}\n\nSoru: {text}" if arama_sonucu else text

    try:
        # Fotoğraf mı Metin mi?
        if image_path:
            with PIL.Image.open(image_path) as img:
                # Gerçekçilik kilidi eklendi (temperature=0.2)
                response = client.models.generate_content(
                    model=uygun_model, 
                    contents=[img, full_text],
                    config=types.GenerateContentConfig(temperature=0.2)
                )
        else:
            sohbet_gecmisi[user_id].append({"role": "user", "parts": [{"text": full_text}]})
            # Gerçekçilik kilidi eklendi (temperature=0.2)
            response = client.models.generate_content(
                model=uygun_model, 
                contents=sohbet_gecmisi[user_id],
                config=types.GenerateContentConfig(temperature=0.2)
            )
        
        cevap = response.text
        sohbet_gecmisi[user_id].append({"role": "model", "parts": [{"text": cevap}]})
        
        # Firebase'e kaydet (Son 20 mesajı sakla ki sınır aşılmasın)
        if db:
            db.collection("sohbetler").document(str(user_id)).set({"gecmis": sohbet_gecmisi[user_id][-20:]})
        return cevap
        
    except Exception as e:
        # Hata alırsak son eklediğimiz kullanıcı mesajını sil ki hafıza sırası bozulmasın
        if sohbet_gecmisi[user_id] and sohbet_gecmisi[user_id][-1]["role"] == "user":
            sohbet_gecmisi[user_id].pop()
        return f"Hata: {e}"

def hafizayi_temizle(user_id):
    if user_id in sohbet_gecmisi: del sohbet_gecmisi[user_id]
    if db: db.collection("sohbetler").document(str(user_id)).delete()
