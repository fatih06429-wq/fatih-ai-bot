import os
import sys

# RENDER YAMASI: Eski SQLite hatasını atlamak için sanal kütüphane yönlendirmesi
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DATA_PATH = "vektor_hafiza"
os.makedirs(CHROMA_DATA_PATH, exist_ok=True)

# Global değişkenler (Başlangıçta boş bırakıyoruz ki site hızlı açılsın)
_client = None
_koleksiyon = None

def koleksiyonu_getir():
    """Modeli uygulamanın başında değil, sadece ilk ihtiyaç duyulduğunda yükler (Lazy Load)."""
    global _client, _koleksiyon
    if _koleksiyon is None:
        print("⏳ Derin Öğrenme modeli yükleniyor... (Bu işlem ilk seferde biraz sürebilir)")
        _client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
        
        # Modeli indir ve kur
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        
        _koleksiyon = _client.get_or_create_collection(
            name="kerem_bilgi_bankasi",
            embedding_function=sentence_transformer_ef
        )
        print("✅ Vektör Veritabanı Hazır!")
    
    return _koleksiyon

def metin_parcala(metin, max_kelime=150):
    """Uzun metinleri yapay zekanın yutabileceği küçük parçalara ayırır."""
    kelimeler = metin.split()
    parcalar = []
    for i in range(0, len(kelimeler), max_kelime):
        parca = " ".join(kelimeler[i:i+max_kelime])
        parcalar.append(parca)
    return parcalar

def hafizaya_ekle(metin, kaynak_adi="belge"):
    """Metni vektörlere dönüştürüp ChromaDB'ye kaydeder."""
    parcalar = metin_parcala(metin)
    if not parcalar:
        return False
    
    ids = [f"{kaynak_adi}_{i}_{os.urandom(4).hex()}" for i in range(len(parcalar))]
    metadatalar = [{"kaynak": kaynak_adi} for _ in parcalar]
    
    try:
        # Modeli burada çağırıyoruz
        kol = koleksiyonu_getir()
        kol.add(documents=parcalar, metadatas=metadatalar, ids=ids)
        print(f"✅ {kaynak_adi} başarıyla derin öğrenme hafızasına eklendi! ({len(parcalar)} vektör)")
        return True
    except Exception as e:
        print(f"Hafızaya ekleme hatası: {e}")
        return False

def hafizadan_getir(soru, n_sonuc=3):
    """Kullanıcının sorusuna en çok benzeyen bilgileri getirir."""
    try:
        kol = koleksiyonu_getir()
        
        # Eğer hafıza tamamen boşsa arama yapıp hata vermesini engelliyoruz
        if kol.count() == 0:
            return ""
            
        sonuclar = kol.query(query_texts=[soru], n_results=n_sonuc)
        bulunan_metinler = sonuclar['documents'][0]
        if bulunan_metinler:
            return "\n---\n".join(bulunan_metinler)
        return ""
    except Exception as e:
        print(f"Hafızadan okuma hatası: {e}")
        return ""