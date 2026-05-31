import whisper

print("⏳ Whisper modeli yükleniyor (Bu işlem biraz zaman alabilir)...", flush=True)
# RAM sorunu yaşamamak için en hafif model olan 'tiny' kullanıyoruz.
model = whisper.load_model("tiny")
print("✅ Whisper modeli başarıyla yüklendi!", flush=True)

def sesi_metne_cevir(dosya_yolu):
    try:
        # Ses dosyasını Türkçe olarak çözümlüyoruz
        sonuc = model.transcribe(dosya_yolu, language="tr")
        return sonuc["text"].strip()
    except Exception as e:
        return f"HATA: {e}"
