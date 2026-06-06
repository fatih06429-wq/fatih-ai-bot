import os
import base64
import requests
import fitz 

SISTEM_KIMLIGI_YAZICI = "Sen, uzman bir yapay zeka asistanı olan Kerem AI'sın. Sana verilen metni analiz edip en önemli noktaları maddeler halinde özetle."

class KeremAI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.model_name = 'llama-3.3-70b-versatile'
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def pdf_metni_cikar(self, pdf_path):
        doc = fitz.open(pdf_path)
        parcalar = []
        parca = ""
        # 3000 karakterlik parçalar halinde bölüyoruz (Token limitini aşmamak için)
        for page in doc:
            metin = page.get_text()
            parca += metin
            if len(parca) > 8000:
                parcalar.append(parca)
                parca = ""
        if parca: parcalar.append(parca)
        return parcalar

    def ozetle(self, metin_parcasi):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": SISTEM_KIMLIGI_YAZICI}, {"role": "user", "content": f"Bu kısmı özetle: {metin_parcasi}"}],
            "temperature": 0.3
        }
        response = requests.post(self.url, headers=headers, json=payload)
        return response.json()["choices"][0]["message"]["content"] if response.status_code == 200 else "Özetlenemedi."

    def process_request(self, prompt, file_path=None):
        if file_path and file_path.lower().endswith('.pdf'):
            parcalar = self.pdf_metni_cikar(file_path)
            tum_ozetler = ""
            for p in parcalar:
                tum_ozetler += self.ozetle(p) + "\n\n"
            
            # Tüm parçaların özetini final bir özetleme işlemine sok
            final_payload = {
                "model": self.model_name,
                "messages": [{"role": "system", "content": "İşte dokümanın farklı parçalarından gelen özetler. Bunları birleştirip kapsamlı bir genel özet çıkar."}, 
                             {"role": "user", "content": tum_ozetler}],
                "temperature": 0.3
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            res = requests.post(self.url, headers=headers, json=final_payload)
            return res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else "Final özeti oluşturulamadı."
        
        # Dosya yoksa veya PDF değilse normal devam et
        # ... (Önceki metin işleme kodunla aynı kalacak)