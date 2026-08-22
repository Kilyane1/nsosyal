"""Ekran goruntusu alma — mss kutuphanesi ile.

Ana ekranin goruntusunu yakalar, JPEG olarak kaydeder ve yolunu doner.
Eski dosyalar (son 5 disinda) otomatik temizlenir.
"""
from __future__ import annotations

import time
from pathlib import Path

import mss
from PIL import Image


EKRAN_KLASORU = Path("output/screens")
# Eski ekran goruntuleri bu sayidan fazlaysa yenisi alinmadan once temizlenir.
ESIK_DOSYA_SAYISI = 5


def _eski_dosyalari_temizle(haric: Path | None = None) -> None:
    """EKRAN_KLASORU icindeki eski ekran goruntulerini sil."""
    try:
        dosyalar = sorted(EKRAN_KLASORU.glob("ekran_*.png"), key=lambda p: p.stat().st_mtime)
        if len(dosyalar) <= ESIK_DOSYA_SAYISI:
            return
        for dosya in dosyalar[:-ESIK_DOSYA_SAYISI]:
            if haric and dosya.resolve() == haric.resolve():
                continue
            try:
                dosya.unlink()
            except Exception:
                pass
    except Exception:
        pass


def ekrani_yakala() -> Path:
    """Ana ekranin goruntusunu al ve JPEG olarak kaydet. Dosya yolunu doner."""
    EKRAN_KLASORU.mkdir(parents=True, exist_ok=True)
    _eski_dosyalari_temizle()
    dosya = EKRAN_KLASORU / f"ekran_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    with mss.mss() as yakalayici:
        ana_ekran = yakalayici.monitors[1]
        goruntu = yakalayici.grab(ana_ekran)
        resim = Image.frombytes("RGB", goruntu.size, goruntu.bgra, "raw", "BGRX")
        resim.save(dosya, "JPEG", quality=70)
    return dosya
