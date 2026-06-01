from google.genai import types
import os
import json
import PIL.Image
import fitz  
import requests 
from google import genai
from duckduckgo_search import DDGS
import datetime
from hafiza import hafizaya_ekle, hafizadan_getir
import firebase_admin
from firebase_admin import credentials, firestore

# --- AYARLAR ---
# DİKKAT: Ngrok'u her açtığında buradaki linki yenilemen gerekir!
NGROK_LINK = "https://couch-customary-affair.ngrok-free.dev/api/generate"

try:
    firebase_json = os.environ.get("FIREBASE_JSON")
    cred = credentials.Certificate(json.loads(firebase_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Bağlantısı Başarılı!")
except Exception as e:
    print(f"❌ Firebase başlatılamadı: {e}")
    db = None

sohbet_gecmisi = {}
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

def fallback_ollama(mesaj):
    try:
        sistem_talimati = """Sen Kerem AI'sın. Çok dilli (multilingual), profesyonel bir asistansın."""
        payload = {"model": "qwen2.5:7b", "prompt": f"{sistem_talimati}\n\nSoru: {mesaj}", "stream": False}
        headers = {"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"}
        
        response = requests.post(NGROK_LINK, json=payload, headers=headers, timeout=120)
        if response.status_code == 200:
            return f"*(Yerel Sistem)*\n{response.json().get('response', '')}"
        
        # 404 veya 502 hatalarında kullanıcıyı bilgilendir
        if response.status_code == 404 or response.status_code == 502:
             return "Yedek motor bağlantısı koptu. Lütfen sistem yöneticisinden Ngrok linkini güncellemesini isteyin."
             
        return f"Yedek motor meşgul. (Hata: {response.status_code})"
    except Exception as e:
        return f"Bağlantı hatası: {e}"

def ask_ai(text, user_id, image_path=None):
    bugun = datetime.datetime.now().strftime("%d %B %Y")
    
    if user_id not in sohbet_gecmisi:
        sohbet_gecmisi[user_id] = [
            {"role": "user", "parts": [{"text": f"Sistem: Bugün {bugun}. Sen dünya çapında her dili bilen profesyonel bir asistansın. Kullanıcı seninle hangi dilde iletişim kurarsa, anadili gibi o dilde yanıt ver."}]},
            {"role": "model", "parts": [{"text": "Anladım. İstenilen dilde yardımcı olmaya hazırım."}]}
        ]

    vektor_bilgisi = hafizadan_getir(text)
    arama_sonucu = internette_ara(text) if arama_gerekli_mi(text) else ""
    
    full_text = text
    if arama_sonucu or vektor_bilgisi:
        full_text = f"Önceki Öğrenilmiş Bilgiler (Hafıza):\n{vektor_bilgisi}\n\nİnternet Verileri:\n{arama_sonucu}\n\nKullanıcının Sorusu: {text}"

    try:
        model_contents = []
        if image_path:
            if image_path.lower().endswith('.pdf'):
                doc = fitz.open(image_path)
                pdf_text = "\n".join([page.get_text() for page in doc])
                hafizaya_ekle(pdf_text, kaynak_adi=os.path.basename(image_path))
                
                # ÇÖZÜM: PDF içeriğini sadece okuma, sohbet geçmişine (kısa hafızaya) de kaydet!
                pdf_baglami = f"Kullanıcı bir belge yükledi. Belge İçeriği Özeti:\n{pdf_text[:10000]}\n\nKullanıcının Notu: {full_text}"
                sohbet_gecmisi[user_id].append({"role": "user", "parts": [{"text": pdf_baglami}]})
                model_contents = sohbet_gecmisi[user_id]
            else:
                img = PIL.Image.open(image_path)
                # Görseli de sohbet geçmişine "görsel yüklendi" notuyla ekle
                sohbet_gecmisi[user_id].append({"role": "user", "parts": [{"text": f"[Kullanıcı bir görsel yükledi] {full_text}"}]})
                model_contents = [img, full_text]
        else:
            sohbet_gecmisi[user_id].append({"role": "user", "parts": [{"text": full_text}]})
            model_contents = sohbet_gecmisi[user_id]

        response = client.models.generate_content(
            model=uygun_model, 
            contents=model_contents,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        cevap = response.text
        if not image_path or image_path.lower().endswith('.pdf'):
            # Modeli cevabını da kısa süreli hafızaya mutlaka yaz
            sohbet_gecmisi[user_id].append({"role": "model", "parts": [{"text": cevap}]})
        
        if db: db.collection("sohbetler").document(str(user_id)).set({"gecmis": sohbet_gecmisi[user_id][-20:]})
        return cevap
        
    except Exception as e:
        print(f"Hata oluştu, yedek sisteme geçiliyor: {e}")
        if not image_path and sohbet_gecmisi.get(user_id) and sohbet_gecmisi[user_id][-1]["role"] == "user":
            sohbet_gecmisi[user_id].pop()
        return fallback_ollama(text)

def hafizayi_temizle(user_id):
    if user_id in sohbet_gecmisi: del sohbet_gecmisi[user_id]
    if db: db.collection("sohbetler").document(str(user_id)).delete()
