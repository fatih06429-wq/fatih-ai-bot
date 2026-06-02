import os
import json
import requests
import fitz  
import PIL.Image
from google import genai
from google.genai import types

from hafiza import hafizaya_ekle, hafizadan_getir, hafizayi_temizle 

# --- SİSTEM AYARLARI ---
NGROK_LINK = "https://couch-customary-affair.ngrok-free.dev/api/generate" 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- MASTER SİSTEM TALİMATLARI (PRO & OPUS SEVİYESİ) ---
SISTEM_KIMLIGI_YAZICI = """
Sen, dünya çapında uzman, 'Claude Code Opus 4.8' ve 'Gemini Pro' zeka seviyesinde bir Kıdemli Yazılım Geliştirici ve Sistem Mimarı olan Kerem AI'sın.
Görevin, kullanıcının isteklerine yönelik en optimal, performanslı, güvenli ve temiz kod (Clean Code) mimarisini üretmektir.
Yazdığın kodlar production-ready (canlıya alınmaya hazır) olmalı, hiçbir eksik, 'mevcut kodlar buraya gelecek' gibi geçiştirmeler barındırmamalıdır.
 Her zaman Türkçe yanıt vermelisin.
"""

SISTEM_KIMLIGI_ELESTIRMEN = """
Sen, dünya çapında acımasız ve ultra titiz bir Kıdemli Baş Yazılım Denetçisi (Principal Code Reviewer) ve Siber Güvenlik Uzmanısın.
Görevin, sana verilen kod taslağını şu kriterlere göre incelemektir:
1. Mantık hataları (Logic bugs) ve çalışma zamanı çökmeleri (Runtime errors).
2. Algoritmik karmaşıklık (Zaman ve hafıza optimizasyonu - Big O).
3. Güvenlik açıkları (SQL Injection, XSS, Gizli Veri İhlalleri).
4. Eksik bırakılmış, yorum satırı ile geçiştirilmiş bloklar.
İnceleme sonucunda eğer kod kusursuzsa sadece 'KUSURSUZ' yazmalısın. Eğer hata veya geliştirme alanı varsa, bunları detaylı bir rapor halinde sunmalısın.
"""

class UltraReasoningAgent:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.0-flash' # Sistem kararlılığı için en güncel ana motor

    def _execute_call(self, system_instruction, prompt, contents, temperature):
        """Gemini API katmanına güvenli ve izole çağrı yapar."""
        combined_contents = list(contents)
        combined_contents.append(prompt)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature
        )
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=combined_contents,
            config=config
        )
        return response.text

    def process_request(self, user_message, context_history, file_contents, mode):
        """Üretici -> Eleştirmen -> Düzeltici ajan döngüsünü yöneten ana metot."""
        
        # Temel bağlam oluşturuluyor
        base_prompt = f"Geçmiş Bağlam:\n{context_history}\n\nKullanıcı İletisi: {user_message}"
        
        # Eğer mod hızlı ise döngüye girmeden doğrudan yanıt üretilir (Zaman optimizasyonu)
        if mode == "fast":
            print("⚡ Hızlı Mod: Tek aşamalı üretim yapılıyor...", flush=True)
            return self._execute_call(SISTEM_KIMLIGI_YAZICI, base_prompt, file_contents, temperature=0.5)
            
        print("🧠 Düşünen Mod: 3 Aşamalı Ajan Döngüsü Başlatıldı...", flush=True)
        
        # ADIM 1: İlk Kod ve Çözüm Taslağının Üretilmesi (Draft Generation)
        print("-> [Ajan 1] Çözüm taslağı oluşturuluyor...", flush=True)
        ilk_taslak = self._execute_call(SISTEM_KIMLIGI_YAZICI, base_prompt, file_contents, temperature=0.2)
        
        # ADIM 2: Kodun Eleştirmen Ajan Tarafından Denetlenmesi (Code Review)
        print("-> [Ajan 2] Kod denetimi ve güvenlik analizi yapılıyor...", flush=True)
        elestiri_prompt = f"Denetlenecek Kod ve Çözüm:\n{ilk_taslak}\n\nOrijinal Kullanıcı İsteği: {user_message}"
        elestiri_raporu = self._execute_call(SISTEM_KIMLIGI_ELESTIRMEN, elestiri_prompt, [], temperature=0.1)
        
        if "KUSURSUZ" in elestiri_raporu.upper() and len(elestiri_raporu.strip()) < 20:
            print("✅ Eleştirmen onay verdi: Kod kusursuz!", flush=True)
            return ilk_taslak
            
        print(f"🚨 Eleştirmen kusurlar buldu! Yeniden düzenleme aşamasına geçiliyor.\nRapor:\n{elestiri_raporu}", flush=True)
        
        # ADIM 3: Eleştiri Raporuna Göre Kodun Refaktör Edilmesi (Refinement)
        print("-> [Ajan 3] Eleştiri raporu doğrultusunda kod yeniden yapılandırılıyor...", flush=True)
        duzeltme_prompt = (
            f"Orijinal Kullanıcı İsteği: {user_message}\n\n"
            f"İlk Yazılan Hatalı/Eksik Kod:\n{ilk_taslak}\n\n"
            f"Kıdemli Denetçinin Raporu ve Düzeltilmesi Gereken Yerler:\n{elestiri_raporu}\n\n"
            f"Lütfen denetçi raporundaki tüm uyarıları dikkate alarak, kodu tamamen baştan yaz ve eksiksiz, mükemmel çalışan nihai sürümü üret."
        )
        
        nihai_cozum = self._execute_call(SISTEM_KIMLIGI_YAZICI, duzeltme_prompt, file_contents, temperature=0.1)
        print("✅ Nihai çözüm başarıyla optimize edildi ve üretildi.", flush=True)
        return nihai_cozum

def ask_ai(mesaj, user_id="default_user", image_path=None, mode="thinking"):
    """Giriş noktası fonksiyonu. Dosya okuma, hafıza yönetimi ve ajan tetiklemesini koordine eder."""
    gecmis = hafizadan_getir(mesaj)
    hafizaya_ekle(mesaj, kaynak_adi=user_id)
    
    contents = []
    
    # Dosya girdilerinin asistan bağlamına dahil edilmesi
    if image_path and os.path.exists(image_path):
        if image_path.lower().endswith(".pdf"):
            pdf_metin = ""
            try:
                doc = fitz.open(image_path)
                for sayfa in doc:
                    pdf_metin += sayfa.get_text() + "\n"
                if pdf_metin.strip():
                    contents.append(f"[PDF DOSYA İÇERİĞİ]:\n{pdf_metin}")
            except Exception as e:
                contents.append(f"[PDF OKUMA HATASI]: {e}")
        else:
            try:
                img = PIL.Image.open(image_path)
                contents.append(img)
            except:
                pass

    try:
        # Ajan döngüsü başlatılıyor
        agent = UltraReasoningAgent(api_key=GEMINI_API_KEY)
        cevap = agent.process_request(mesaj, gecmis, contents, mode)
        
        hafizaya_ekle(cevap, kaynak_adi=user_id)
        return cevap

    except Exception as gemini_err:
        print(f"🚨 Ana Beyin Hatası: {gemini_err}. Yedek hatta geçiliyor...", flush=True)
        try:
            # Yedek motor (Ollama / Qwen-Coder) hattı
            payload = {
                "model": "qwen2.5-coder:7b",
                "prompt": f"{SISTEM_KIMLIGI_YAZICI}\n\nBağlam:\n{gecmis}\n\nMesaj: {mesaj}",
                "stream": False
            }
            res = requests.post(NGROK_LINK, json=payload, timeout=60)
            if res.status_code == 200:
                cevap = res.json().get("response", "Yerel model yanıt üretemedi.")
                hafizaya_ekle(cevap, kaynak_adi=user_id)
                return cevap
            else:
                return f"⚠️ Yedek motor sunucu hatası verdi (HTTP {res.status_code}).\nAna Beyin Hatası: {gemini_err}"
        except Exception as ollama_err:
            return f"⚠️ Kritik Sistem Çökmesi. Ana beyin ve yedek motor yanıt vermiyor.\nGemini: {gemini_err}\nOllama: {ollama_err}"
