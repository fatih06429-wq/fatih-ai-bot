import os
import json
import requests
import fitz  
import PIL.Image
import datetime
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
from hafiza import hafizaya_ekle, hafizadan_getir
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
        print("✅ Firebase Bağlantısı Başarılı!")
    else:
        db = None
except Exception as e:
    print(f"❌ Firebase başlatılamadı: {e}")
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

def ask_ai(mesaj, user_id="default_user", image_path=None):
    # 1. Geçmiş hafızayı getir
    gecmis = hafizadan_getir(user_id)
    
    # 2. Yeni mesajı hafızaya ekle
    hafizaya_ekle(user_id, "user", mesaj)
    
    # Tüm içeriği topla
    contents = []
    
    # Görsel veya PDF varsa ekle
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

    # Geçmiş bağlamı ve mevcut mesajı ekle
    tam_metin = f"Önceki Bağlam:\n{gecmis}\n\nKullanıcının Yeni Mesajı: {mesaj}"
    contents.append(tam_metin)

    # 3. Gemini API ile bağlan (Kodlama için gemini-1.5-pro tavsiye edilir)
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Sistem kimliğini yapılandırma olarak ekliyoruz
        config = types.GenerateContentConfig(
            system_instruction=SISTEM_KIMLIGI,
            temperature=0.3 # Kodlamada halüsinasyonu önlemek için düşük sıcaklık
        )
        
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=contents,
            config=config
        )
        cevap = response.text
        
        # Cevabı hafızaya al ve döndür
        hafizaya_ekle(user_id, "model", cevap)
        return cevap

    # 4. YEDEK MOTOR (Ollama - Ngrok)
    except Exception as gemini_err:
        print(f"Gemini API Hatası, yedeğe geçiliyor: {gemini_err}")
        try:
            # Ngrok üzerinden Ollama'ya istek at
            payload = {
                "model": "qwen2.5-coder:7b", # Veya kullandığın yerel modelin adı
                "prompt": f"{SISTEM_KIMLIGI}\n\n{tam_metin}",
                "stream": False
            }
            res = requests.post(NGROK_LINK, json=payload, timeout=60)
            if res.status_code == 200:
                cevap = res.json().get("response", "Yerel model yanıt veremedi.")
                hafizaya_ekle(user_id, "model", cevap)
                return cevap
            else:
                return f"Yedek motor hata verdi. (Kod: {res.status_code})"
        except Exception as ollama_err:
            return f"Hem ana beyin hem de yedek motor meşgul. Lütfen daha sonra tekrar deneyin."
