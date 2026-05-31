import whisper

print("⏳ Whisper modeli yükleniyor (Bu işlem ilk açılışta biraz zaman alabilir)...")
# 'base' modeli ortalama bir bilgisayarda hem hızlı çalışır hem de Türkçe performansı iyidir.
model = whisper.load_model("small")
print("✅ Whisper modeli başarıyla yüklendi!")

def sesi_metne_cevir(dosya_yolu):
    try:
        # Ses dosyasını Türkçe olarak çözümlüyoruz
        sonuc = model.transcribe(dosya_yolu, language="tr")
        return sonuc["text"].strip()
    except Exception as e:
        return f"HATA: {e}"