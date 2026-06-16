import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# 6 haneli rastgele onay kodu üretici
def onay_kodu_uret():
    return ''.join(random.choices(string.digits, k=6))

# Kullanıcıya mail gönderme fonksiyonu
def onay_maili_gonder(alici_mail, kod):
    gonderici_mail = os.environ.get("GMAIL_ADRESIN") # Kendi mailin
    gonderici_sifre = os.environ.get("EMAIL_SIFRE")  # Az önce aldığın 16 haneli şifre
    
    if not gonderici_mail or not gonderici_sifre:
        return False, "Mail ayarları (GMAIL_ADRESIN veya EMAIL_SIFRE) eksik!"

    mesaj = MIMEMultipart()
    mesaj['From'] = f"Kerem AI Destek <{gonderici_mail}>"
    mesaj['To'] = alici_mail
    mesaj['Subject'] = "Uygulama Üyelik Onay Kodunuz"

    html_icerik = f"""
    <html>
      <body>
        <h2>Aramıza Hoş Geldiniz!</h2>
        <p>Üyeliğinizi tamamlamak için lütfen aşağıdaki onay kodunu sisteme giriniz:</p>
        <h1 style="color: #4CAF50; font-size: 32px; letter-spacing: 4px;">{kod}</h1>
        <p>Eğer bu işlemi siz yapmadıysanız, lütfen bu e-postayı dikkate almayın.</p>
      </body>
    </html>
    """
    mesaj.attach(MIMEText(html_icerik, 'html'))

    try:
        # Gmail SMTP sunucusuna bağlanıp maili ateşliyoruz
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gonderici_mail, gonderici_sifre)
        server.send_message(mesaj)
        server.quit()
        return True, "Mail başarıyla gönderildi."
    except Exception as e:
        return False, f"Mail gönderim hatası: {e}"
