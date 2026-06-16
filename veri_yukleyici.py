import os
import json
import fitz  # PyMuPDF
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. FIREBASE BAĞLANTISI ---
# Kendi bilgisayarında çalıştıracağın için ortam değişkenini (Environment Variable)
# Windows CMD veya PowerShell üzerinden set etmen gerekebilir.
# Veya direkt json dosyasının yolunu verebilirsin: cred = credentials.Certificate("firebase_kimlik.json")
try:
    firebase_json_str = os.environ.get("FIREBASE_JSON")
    if firebase_json_str:
        cred_dict = json.loads(firebase_json_str)
        cred = credentials.Certificate(cred_dict)
    else:
        # Eğer ortam değişkeni yoksa, aynı klasördeki json dosyasını arar
        cred = credentials.Certificate("firebase_kimlik.json") 
        
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase bağlantısı başarılı!")
except Exception as e:
    print(f"❌ Firebase hatası: {e}")
    exit()

# --- 2. PDF PARÇALAMA VE YÜKLEME FONKSİYONU ---
def pdf_yukle(pdf_yolu, universite_adi, ders_adi, sayfa_araligi=15):
    """
    Büyük PDF'leri Gemini'nin çökmemesi için belirli sayfa aralıklarıyla (örn. 15 sayfa) 
    böler ve Firebase'e kaydeder.
    """
    if not os.path.exists(pdf_yolu):
        print(f"❌ Dosya bulunamadı: {pdf_yolu}")
        return

    print(f"📚 {ders_adi} ({universite_adi}) yükleniyor...")
    
    try:
        doc = fitz.open(pdf_yolu)
        toplam_sayfa = len(doc)
        
        # Koleksiyon yapısı: kutuphane -> anadolu_aof -> dersler -> unix_sistem_yonetimi -> bolumler
        ders_ref = db.collection("kutuphane").document(universite_adi).collection("dersler").document(ders_adi)
        
        # Dersin üst bilgilerini kaydet
        ders_ref.set({
            "baslik": ders_adi.replace("_", " ").title(),
            "toplam_sayfa": toplam_sayfa,
            "universite": universite_adi.upper()
        })

        bolum_no = 1
        metin_havuzu = ""
        baslangic_sayfasi = 1

        for i, sayfa in enumerate(doc):
            metin_havuzu += sayfa.get_text() + "\n"
            
            # Belirlenen sayfa aralığına (chunk) ulaştığımızda veya belge bittiğinde kaydet
            if (i + 1) % sayfa_araligi == 0 or (i + 1) == toplam_sayfa:
                bitis_sayfasi = i + 1
                
                # Metin çok kısaysa (boş sayfa vs.) atla
                if len(metin_havuzu.strip()) > 50:
                    bolum_id = f"bolum_{bolum_no}"
                    ders_ref.collection("bolumler").document(bolum_id).set({
                        "bolum_no": bolum_no,
                        "sayfa_araligi": f"{baslangic_sayfasi}-{bitis_sayfasi}",
                        "icerik": metin_havuzu
                    })
                    print(f"  -> BÖLÜM {bolum_no} kaydedildi (Sayfa {baslangic_sayfasi}-{bitis_sayfasi})")
                
                # Sonraki döngü için sıfırla
                bolum_no += 1
                metin_havuzu = ""
                baslangic_sayfasi = bitis_sayfasi + 1
                
        print(f"✅ {ders_adi} başarıyla parçalandı ve Firebase'e yüklendi!\n")

    except Exception as e:
        print(f"❌ Yükleme sırasında hata oluştu: {e}")

# --- 3. ÇALIŞTIRMA ALANI ---
if __name__ == '__main__':
    # Kullanım Örneği:
    # 1. Aynı klasöre yüklemek istediğin PDF'i koy.
    # 2. Aşağıdaki bilgileri kendine göre düzenle ve çalıştır.
    
    pdf_yukle("Unix Sistem Yönetimi.pdf", "anadolu_aof", "unix_sistem_yonetimi")
    pdf_yukle("veri_yapilari.pdf", "auzef", "veri_yapilari")
    
    print("Yukarıdaki yorum satırlarını (pdf_yukle) kendi dosyana göre düzenleyip çalıştırabilirsin.")