import os
import json
import requests
import fitz  
import PIL.Image
from google import genai
from google.genai import types

from hafiza import hafizaya_ekle, hafizadan_getir, hafizayi_temizle 

# --- AYARLAR ---
NGROK_LINK = "https://couch-customary-affair.ngrok-free.dev/api/generate" 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- SISTEM ISTEMI ---
SISTEM_KIMLIGI = """
Sen, dunya capinda uzman, 'Claude Code' seviyesinde bir Kidemli Yazilim Gelistirici (Senior Software Engineer) ve Sistem Mimari olan Kerem AI'sin. Her zaman Turkce dilinde yanit vermelisin.

Kesinlikle Uyman Gereken Kodlama Kurallari:
1. TAM VE EKSIKSIZ KOD: Bir kod yazdiginda ASLA ozetleme, kisaltma yapma. Tam kodu ver.
2. TEKNIK DERINLIK: Hatalarin kok nedenini (root cause) acikla.
3. BEST PRACTICES: Temiz kod prensiplerini uygula.
4. COZUM ODAKLILIK: Algoritmik dusun ve dogrudan cozume odaklan.
"""

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
                    contents.append(f"[PDF ICERIGI]: {pdf_metin}")
            except Exception as e:
                contents.append(f"[PDF OKUMA HATASI]: {e}")
        else:
            try:
                img = PIL.Image.open(image_path)
                contents.append(img)
            except: pass

    tam_metin = f"Onceki Baglam:\n{gecmis}\n\nKullanicinin Yeni Mesaji: {mesaj}"
    contents.append(tam_metin)

    # 404 KABUSUNU BITIREN KESIN COZUM: 
    # API'nin en stabil kabul ettigi 1.5-flash motoru her iki mod icin standartlastirildi.
    secilen_model = 'gemini-1.5-flash'
    
    # Zeka ve Hiz farkini Temperature ile belirliyoruz
    if mode == "fast":
        sicaklik = 0.6 
    else:
        sicaklik = 0.1 

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
        print(f"🚨 Kök Neden (Gemini API Coktu): {gemini_err}", flush=True)
        print(f"🔄 Yedege (Ollama/Ngrok) geciliyor...", flush=True)
        
        try:
            payload = {
                "model": "qwen2.5-coder:7b",
                "prompt": f"{SISTEM_KIMLIGI}\n\n{tam_metin}",
                "stream": False
            }
            res = requests.post(NGROK_LINK, json=payload, timeout=60)
            if res.status_code == 200:
                cevap = res.json().get("response", "Yerel model yanit veremedi.")
                hafizaya_ekle(cevap, kaynak_adi=user_id)
                return cevap
            else:
                return f"⚠️ Yedek motor sunucu hatasi verdi. (HTTP Kod: {res.status_code}). Ngrok tunelinizi kontrol edin.\nAna Beyin Hatasi: {gemini_err}"
        except requests.exceptions.ConnectionError:
            return f"⚠️ Yedek motora ulasilamiyor (Baglanti reddedildi). Ngrok URL'sini guncelleyin.\nAna Beyin (Gemini) hatasi: {gemini_err}"
        except Exception as ollama_err:
            return f"⚠️ Hem ana beyin hem de yedek motor tamamen coktu.\nGemini Hatasi: {gemini_err}\nOllama Hatasi: {ollama_err}"
