import os
import json
import requests
from google import genai
import PIL.Image
from duckduckgo_search import DDGS
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Başlatma
try:
    # 1. Render'daki gizli değişkeni çek
    firebase_json = os.environ.get("FIREBASE_JSON")
    
    # 2. O değişkeni JSON'a çevirip cred (kimlik) olarak ayarla
    cred = credentials.Certificate(json.loads(firebase_json))
    
    # 3. Firebase'i bu kimlikle başlat
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Veri Tabanı Bağlantısı Başarılı!")
except Exception as e:
    print(f"❌ Firebase başlatılamadı: {e}")
    db = None

sohbet_gecmisi = {}

# Gemini API
api_key = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

uygun_model = "gemini-2.0-flash" 
try:
    for m in client.models.list():
        if '2.5-flash' in m.name:
            uygun_model = m.name
            break
        elif '2.0-flash' in m.name:
            uygun_model = m.name
except:
    pass

def arama_gerekli_mi(metin):
    """Kullanıcının mesajında anlık internet bilgisi gerekip gerekmediğini kontrol eder."""
    guncel_kelimeler = [
        "hava", "maç", "skor", "haber", "gündem", "dolar", "euro", "borsa", 
        "fiyat", "bugün", "tarih", "saat", "lig", "puan", "kim kazandı", 
        "son dakika", "vizyondaki", "deprem", "trafik"
    ]
    # Mesajı küçük harfe çevirip anahtar kelimeleri arıyoruz
    metin_lowercase = metin.lower()
    return any(kelime in metin_lowercase for kelime in guncel_kelimeler)

def internette_ara(sorgu):
    print(f"🌐 İnternette aranıyor: {sorgu}")
    try:
        with DDGS() as ddgs:
            sonuclar = list(ddgs.text(sorgu, region='tr-tr', safesearch='off', max_results=3))
            if not sonuclar:
                print("⚠️ Arama sonucu bulunamadı.")
                return ""
            ozet = "\n".join([f"- {s['title']}: {s['body']}" for s in sonuclar])
            print(f"✅ {len(sonuclar)} web sonucu bulundu ve yapay zekaya iletildi.")
            return ozet
    except Exception as e:
        print(f"❌ Arama sırasında hata: {e}")
        return ""

def ask_ai(text, user_id, image_path=None):
    bugun = datetime.datetime.now().strftime("%d %B %Y")
    
    # FIREBASE HAFIZA KONTROLÜ
    if user_id not in sohbet_gecmisi:
        if db:
            doc_ref = db.collection("sohbetler").document(str(user_id))
            doc = doc_ref.get()
            if doc.exists:
                sohbet_gecmisi[user_id] = doc.to_dict().get("gecmis", [])
                print(f"☁️ {user_id} geçmişi Firebase'den başarıyla çekildi.")
            else:
                sohbet_gecmisi[user_id] = [
                    {"role": "system", "content": f"Senin adın Fatih'in Yapay Zekası. Doğrudan Türkçe düşünen uzman bir asistansın. Bugünün tarihi: {bugun}. Sana internet verisi verilirse onu kullan, verilmezse kendi bilgilerini ve sohbet geçmişini kullan."}
                ]
        else:
             sohbet_gecmisi[user_id] = [{"role": "system", "content": "Sen uzman bir asistansın."}]

    # FOTOĞRAF ANALİZİ
    if image_path:
        try:
            with PIL.Image.open(image_path) as img:
                prompt = text if text else "Bu fotoğrafta ne görüyorsun? Lütfen detaylıca Türkçe açıkla."
                response = client.models.generate_content(model=uygun_model, contents=[img, prompt])
                cevap = response.text
            
            sohbet_gecmisi[user_id].append({"role": "user", "content": f"(Fotoğraf gönderdim): {prompt}"})
            sohbet_gecmisi[user_id].append({"role": "assistant", "content": cevap})
            if db:
                db.collection("sohbetler").document(str(user_id)).set({"gecmis": sohbet_gecmisi[user_id]})
            return cevap
        except Exception as e:
            return f"Fotoğraf analiz edilirken hata: {e}"

    # AKILLI İNTERNET ARAMASI KONTROLÜ
    arama_sonucu = ""
    if arama_gerekli_mi(text):
        arama_sonucu = internette_ara(text)
    else:
        print("⚡ Filtre Devreye Girdi: Bu soru için internet aramasına gerek duyulmadı.")

    sohbet_gecmisi[user_id].append({"role": "user", "content": text})

    if arama_sonucu:
        gizli_bilgi = f"Kullanıcının sorusu: '{text}'\n\nİnternet verileri:\n{arama_sonucu}\n\nBu bilgileri kullanarak doğalca cevap ver."
        gemma_mesajlari = sohbet_gecmisi[user_id][:-1] + [{"role": "user", "content": gizli_bilgi}]
    else:
        gemma_mesajlari = sohbet_gecmisi[user_id]

    # GEMMA 2 ÇAĞRISI
    try:
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "gemma2", "messages": gemma_mesajlari, "stream": False, "options": {"temperature": 0.4}},
            timeout=60 
        )
        r.raise_for_status()
        cevap = r.json()["message"]["content"]
        
        sohbet_gecmisi[user_id].append({"role": "assistant", "content": cevap})
        if db:
            db.collection("sohbetler").document(str(user_id)).set({"gecmis": sohbet_gecmisi[user_id]})
        return cevap
        
    except Exception as e:
        if sohbet_gecmisi[user_id]: sohbet_gecmisi[user_id].pop()
        return f"Hata: {e}"

def hafizayi_temizle(user_id):
    if user_id in sohbet_gecmisi: del sohbet_gecmisi[user_id]
    if db: db.collection("sohbetler").document(str(user_id)).delete()
