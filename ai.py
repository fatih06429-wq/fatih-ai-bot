import os
import json
import requests
import fitz  
import PIL.Image
import datetime
from google import genai
from google.genai import types
from duckduckgo_search import DDGS

from hafiza import hafizaya_ekle, hafizadan_getir, hafizayi_temizle 

import firebase_admin
from firebase_admin import credentials, firestore
from scrapers import aof_duyurulari_cek

# --- AYARLAR VE BAĞLANTILAR ---
NGROK_LINK = "https://couch-customary-affair.ngrok-free.dev/api/generate"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

try:
    firebase_json = os.environ.get("FIREBASE_JSON")
    if firebase_json:
        cred = credentials.Certificate(json.loads(firebase_json))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Bağlantısı Başarılı!", flush=True) 
    else:
        db = None
except Exception as e:
    print(f"❌ Firebase başlatılamadı: {e}", flush=True)
    db = None

# --- CLAUDE CODE SEVİYESİNDE SİSTEM İSTEMİ (SYSTEM PROMPT) ---
SISTEM_KIMLIGI = """
Sen, dünya çapında uzman, 'Claude Code' seviyesinde bir Kıdemli Yazılım Geliştirici (Senior Software Engineer) ve Sistem Mimarı olan Kerem AI'sın. Her zaman Türkçe dilinde yanıt vermelisin.

Kesinlikle Uyman Gereken Kodlama Kuralları:
1. TAM VE EKSİKSİZ KOD: Bir kod yazdığında veya güncellediğinde ASLA özetleme, kısaltma veya atlama yapma. Kod binlerce satır olsa dahi "// ...mevcut kodlar..." veya "# ...buralar aynı kalacak..." gibi ifadeler kullanmak KESİNLİKLE YASAKTIR. Kullanıcının doğrudan kopyalayıp yapıştırabileceği şekilde tam kodu ver.
2. TEKNİK DERİNLİK: Karşılaştığın hataların (error) sadece çözümünü değil, kök nedenini (root cause) teknik bir dille, profesyonelce açıkla.
3. BEST PRACTICES: Her zaman en iyi uygulamaları (best practices), temiz kod (clean code) prensiplerini ve güvenlik önlemlerini göz önünde bulundurarak kod yaz. Mimari kararlarının arkasındaki mantığı kısaca belirt.
4. ÇÖZÜM ODAKLILIK: Bir hata logu veya bug iletildiğinde, önce sorunun kaynağını algoritmik olarak düşün, sonra doğrudan çözüme odaklan.
"""

# PARAMETRE GÜNCELLEMESİ: mode eklendi
def ask_ai(mesaj, user_id="default_user", image_path=None, mode="thinking"):
    gecmis = hafizadan_getir(mesaj)
    hafizaya_ekle(mesaj, kaynak_adi=user_id)
    
    contents = []
    
    if image_path and os.path.exists(image_path):
        if image_path.lower().endswith(".pdf"):
            pdf_metin = ""
            try:
                doc = fitz.open(image_path)
                for sayfa in doc:
                    pdf_metin += sayfa.get_text() + "\n"
                if pdf_metin.strip():
                    contents.append(f"[PDF İÇERİĞİ]: {pdf_metin}")
            except Exception as e:
                contents.append(f"[PDF OKUMA HATASI]: {e}")
        else:
            try:
                img = PIL.Image.open(image_path)
                contents.append(img)
            except: pass

    tam_metin = f"Önceki Bağlam:\n{gecmis}\n\nKullanıcının Yeni Mesajı: {mesaj}"
    contents.append(tam_metin)

    # MOD SEÇİMİNE GÖRE MOTOR VE SICAKLIK AYARI
    if mode == "fast":
        secilen_model = 'gemini-1.5-flash'
        sicaklik = 0.5 # Hızlı modda standart esneklik
    else:
        secilen_model = 'gemini-1.5-pro'
        sicaklik = 0.2 # Kodlama ve derin analiz için halüsinasyonu engelleyen düşük sıcaklık

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            system_instruction=SISTEM_KIMLIGI,
            temperature=sicaklik 
        )
        
        response = client.models.generate_content(
            model=secilen_model,
            contents=contents,
            config=config
        )
        cevap = response.text
        
        hafizaya_ekle(cevap, kaynak_adi=user_id)
        return cevap

    except Exception as gemini_err:
        # ASIL HATAYI TERMİNALE YAZDIRIYORUZ Kİ SORUNU GÖREBİLESİN
        print(f"🚨 Kök Neden (Gemini API Çöktü): {gemini_err}", flush=True)
        print(f"🔄 Yedeğe (Ollama/Ngrok) geçiliyor...", flush=True)
        
        try:
            payload = {
                "model": "qwen2.5-coder:7b",
                "prompt": f"{SISTEM_KIMLIGI}\n\n{tam_metin}",
                "stream": False
            }
            res = requests.post(NGROK_LINK, json=payload, timeout=60)
            if res.status_code == 200:
                cevap = res.json().get("response", "Yerel model yanıt veremedi.")
                hafizaya_ekle(cevap, kaynak_adi=user_id)
                return cevap
            else:
                return f"⚠️ Yedek motor sunucu hatası verdi. (HTTP Kod: {res.status_code}). Ngrok tünelinizin güncel adresini ve Ollama'nın çalıştığını kontrol edin. Ana hata şuydu: {gemini_err}"
        except requests.exceptions.ConnectionError:
            return f"⚠️ Yedek motora ulaşılamıyor (Bağlantı reddedildi). Ngrok URL'sini kontrol edin.\nAna Beyin (Gemini) hatası: {gemini_err}"
        except Exception as ollama_err:
            return f"⚠️ Hem ana beyin hem de yedek motor tamamen çöktü.\nGemini Hatası: {gemini_err}\nOllama Hatası: {ollama_err}"
