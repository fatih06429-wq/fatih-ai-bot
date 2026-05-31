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
uygun_model = "gemini-2.0-flash" 

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
    
    # Hafıza Yükleme
    if user_id not in sohbet_gecmisi:
        sohbet_gecmisi[user_id] = [{"role": "user", "parts": [{"text": f"Bugünün tarihi: {bugun}. Sen Fatih'in asistansın."}]}]

    # Arama
    arama_sonucu = internette_ara(text) if arama_gerekli_mi(text) else ""
    full_text = f"İnternet verileri: {arama_sonucu}\n\nSoru: {text}" if arama_sonucu else text

    # Fotoğraf mı Metin mi?
    try:
        if image_path:
            with PIL.Image.open(image_path) as img:
                response = client.models.generate_content(model=uygun_model, contents=[img, full_text])
        else:
            sohbet_gecmisi[user_id].append({"role": "user", "parts": [{"text": full_text}]})
            response = client.models.generate_content(model=uygun_model, contents=sohbet_gecmisi[user_id])
        
        cevap = response.text
        sohbet_gecmisi[user_id].append({"role": "model", "parts": [{"text": cevap}]})
        
        # Firebase'e kaydet
        if db:
            db.collection("sohbetler").document(str(user_id)).set({"gecmis": sohbet_gecmisi[user_id]})
        return cevap
        
    except Exception as e:
        return f"Hata: {e}"

def hafizayi_temizle(user_id):
    if user_id in sohbet_gecmisi: del sohbet_gecmisi[user_id]
    if db: db.collection("sohbetler").document(str(user_id)).delete()
