import os
import sys
from google import genai

# RENDER YAMASI: Eski SQLite hatasını atlamak için sanal kütüphane yönlendirmesi
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import chromadb

CHROMA_DATA_PATH = "vektor_hafiza"
os.makedirs(CHROMA_DATA_PATH, exist_ok=True)

_client = None
_koleksiyon = None

def get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key)

def metin_gom(metin):
    """Metni Google GenAI API kullanarak 100% ücretsiz ve ultra hızlı şekilde vektöre çevirir."""
    try:
        client = get_gemini_client()
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=metin
        )
        if isinstance(metin, list):
            return [emb.values for emb in response.embeddings]
        return response.embeddings[0].values
    except Exception as e:
        print(f"Embedding hatası: {e}")
        return None

def koleksiyonu_getir():
    global _client, _koleksiyon
    if _koleksiyon is None:
        _client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
        _koleksiyon = _client.get_or_create_collection(name="kerem_bilgi_bankasi")
    return _koleksiyon

def metin_parcala(metin, max_kelime=150):
    kelimeler = metin.split()
    parcalar = []
    for i in range(0, len(kelimeler), max_kelime):
        parca = " ".join(kelimeler[i:i+max_kelime])
        parcalar.append(parca)
    return parcalar

def hafizaya_ekle(metin, kaynak_adi="belge"):
    parcalar = metin_parcala(metin)
    if not parcalar:
        return False
    
    vektorler = metin_gom(parcalar)
    if not vektorler:
        return False

    ids = [f"{kaynak_adi}_{i}_{os.urandom(4).hex()}" for i in range(len(parcalar))]
    metadatalar = [{"kaynak": kaynak_adi} for _ in parcalar]
    
    try:
        kol = koleksiyonu_getir()
        kol.add(
            embeddings=vektorler,
            documents=parcalar,
            metadatas=metadatalar,
            ids=ids
        )
        print(f"✅ {kaynak_adi} başarıyla bulut embedding hafızasına eklendi! ({len(parcalar)} vektör)")
        return True
    except Exception as e:
        print(f"Hafızaya ekleme hatası: {e}")
        return False

def hafizadan_getir(soru, n_sonuc=3):
    try:
        kol = koleksiyonu_getir()
        if kol.count() == 0:
            return ""
        
        sorgu_vektoru = metin_gom(soru)
        if not sorgu_vektoru:
            return ""

        sonuclar = kol.query(
            query_embeddings=[sorgu_vektoru],
            n_results=n_sonuc
        )
        bulunan_metinler = sonuclar['documents'][0]
        if bulunan_metinler:
            return "\n---\n".join(bulunan_metinler)
        return ""
    except Exception as e:
        print(f"Hafızadan okuma hatası: {e}")
        return ""