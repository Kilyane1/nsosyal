"""Icerik Tarayici — baslangic noktasi.

Bu program:
  1. Mikrofonu surekli dinler
  2. 'analiz' kelimesi duyulursa ekrani yakalar
  3. Google Gemini ile analiz eder
  4. Turkce sonucu gosterir ve sesli okur
  5. 'durdur' denirse sesli okumayi keser

Calistirmak icin: python tray_app.py
veya cift tikla: IcerikTarayici.exe
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
sys.path.insert(0, str(Path(__file__).parent))

# PyInstaller EXE: dosyalar _internal/ icinde olur, sys._MEIPASS ile erisilir.
# Normal Python: dosyalar cwd'de (proje kok dizini).
if hasattr(sys, "_MEIPASS"):
    PROJE_KOK = Path(sys._MEIPASS)
else:
    PROJE_KOK = Path(__file__).parent

from modules import config, log
from modules.gemini import ekrani_analiz_et
from modules.pipeline import rapor_yaz
from modules.screen import ekrani_yakala
from modules.wake import Uyandirici
from modules.tts import oku, durdur
from modules.app import _uygulama as Uygulama

MODEL_DOSYASI = PROJE_KOK / "models" / "wake_word_model.pkl"


def analiz_et() -> None:
    """Ekrana bak, Gemini'ye gonder, goster ve sesli oku."""
    ayarlar = config.oku()

    if not ayarlar.gemini_api_anahtari:
        Uygulama.durum("⚠ Gemini API key yok — Ayarlar'dan girin")
        return

    Uygulama.mesgul(True)
    Uygulama.durum("📸 Ekran yakalanıyor...")

    try:
        ekran_yolu = ekrani_yakala()
        log.yaz("APP", f"ekran yakalandi: {ekran_yolu}")
    except Exception as e:
        log.yaz("APP", f"ekran hatasi: {e}")
        Uygulama.durum(f"❌ Ekran: {e}")
        Uygulama.mesgul(False)
        return

    Uygulama.durum("🔎 Gemini analiz ediyor...")
    try:
        sonuc = ekrani_analiz_et(ekran_yolu)
        # Raporu diske yaz (sonuc penceresi kapansa bile arsiv kalsin)
        try:
            rapor_yaz(sonuc, Path("output/reports"))
        except Exception as e:
            log.yaz("APP", f"rapor yazma hatasi: {e}")
    except Exception as e:
        log.yaz("APP", f"gemini hatasi: {e}")
        Uygulama.durum(f"❌ Gemini: {e}")
        Uygulama.mesgul(False)
        return

    metin = sonuc.get("metin", "") or sonuc.get("hata", "(icerik yok)")
    Uygulama.durum("✅ Analiz tamamlandi")
    Uygulama.sonuc_goster(metin)
    oku(metin[:2000])
    Uygulama.mesgul(False)


def sesli_komut_geldi(kelime: str) -> None:
    """Wake word callback'i — uyandirildiginda cagrilir."""
    log.yaz("APP", f"WAKE: '{kelime}'")
    temiz = kelime.lower().strip()

    if any(w in temiz for w in ("durdur", "dur", "kes", "sus")):
        durdur()
        Uygulama.durum("🛑 Sesli okuma durduruldu")
        log.yaz("APP", "durdur komutu")
        return

    threading.Thread(target=analiz_et, daemon=True).start()


def main() -> None:
    """Ana giris noktasi."""
    # Tek instance kilidi — iki EXE ayni anda calisamaz.
    # SO_REUSEADDR ile kill'den sonra port tekrar baglanabilir olur,
    # yoksa TIME_WAIT yuzunden birkac dakika acilmaz.
    soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        soket.bind(("127.0.0.1", 47789))
        soket.listen(1)
    except OSError:
        log.yaz("APP", "zaten calisan bir Icerik Tarayici var")
        sys.exit(1)

    ayarlar = config.oku()

    # Wake dinleyici — secili cihazla
    dinleyici = Uyandirici(
        uyandirildiginda=sesli_komut_geldi,
        model_yolu=MODEL_DOSYASI,
        cihaz=ayarlar.mikrofon_cihaz_indeksi if ayarlar.mikrofon_cihaz_indeksi is not None and ayarlar.mikrofon_cihaz_indeksi >= 0 else None,
    )
    dinleyici.baslat()
    Uygulama.set_uyandirici(dinleyici)

    # Global klavye kisayollari
    from modules.hotkey import Kisayol
    Kisayol(ayarlar.kisayol, lambda: sesli_komut_geldi("kisayol")).baslat()
    Kisayol("ctrl+shift+s", Uygulama.ayarlar_penceresi).baslat()

    # App'e callback set et (buton icin)
    Uygulama.set_analiz_callback(sesli_komut_geldi)

    log.yaz("APP", "wake word dinleme basladi")
    Uygulama.baslat()


if __name__ == "__main__":
    main()