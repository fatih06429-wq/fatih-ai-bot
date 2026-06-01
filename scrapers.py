import requests
from bs4 import BeautifulSoup

def aof_duyurulari_cek():
    try:
        url = "https://www.anadolu.edu.tr/acikogretim" # AÖF ana sayfası
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        duyurular = []
        # AÖF sayfasındaki duyuru başlıklarını içeren HTML etiketlerini buluyoruz
        for item in soup.find_all('a', class_='news-item')[:5]:
            baslik = item.get_text(strip=True)
            link = "https://www.anadolu.edu.tr" + item['href']
            duyurular.append(f"{baslik} - (Detay: {link})")
            
        return "\n".join(duyurular) if duyurular else "Şu an AÖF sitesinde yeni bir duyuru görünmüyor."
    except Exception as e:
        return f"Duyurulara ulaşılamadı: {e}"