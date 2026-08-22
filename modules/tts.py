"""Sesli okuma modulu.

Edge-tts ile Turkce metni MP3'e cevirir, pygame mixer ile calar.
'durdur' komutuyla kesilebilir.
"""
from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pygame

from modules import log


SES_KLASORU = Path("output/voices")
# Eski ses dosyalari bu sayidan fazlaysa yenisi okunmadan once temizlenir.
ESIK_DOSYA_SAYISI = 5

_kilit = threading.Lock()
_mixer_hazir = False
# Modul seviyesinde tanimla — yoksa oku() icinde UnboundLocalError olur
_aktif_thread: threading.Thread | None = None


def _eski_dosyalari_temizle(haric: Path | None = None) -> None:
    """SES_KLASORU icindeki eski mp3 dosyalarini sil.

    Haric tutulan dosya (su an calan) silinmez. Klasor ESIK'ten
    fazla dosya iceriyorsa yeniler disinda hepsi temizlenir.
    """
    try:
        dosyalar = sorted(SES_KLASORU.glob("ses_*.mp3"), key=lambda p: p.stat().st_mtime)
        if len(dosyalar) <= ESIK_DOSYA_SAYISI:
            return
        # En yeni ESIK kadar dosya kalsin, gerisini sil
        for dosya in dosyalar[:-ESIK_DOSYA_SAYISI]:
            if haric and dosya.resolve() == haric.resolve():
                continue
            try:
                dosya.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _mixer_hazirla() -> None:
    """pygame mixer'i bir kere baslat."""
    global _mixer_hazir
    if _mixer_hazir:
        return
    try:
        pygame.mixer.init()
        _mixer_hazir = True
    except Exception as e:
        log.yaz("SES", f"mixer baslatma hatasi: {e}")


async def _metni_sese_cevir(metin: str, hedef: Path) -> None:
    """Edge-tts ile MP3 uret."""
    import edge_tts
    konusma = edge_tts.Communicate(metin, voice="tr-TR-AhmetNeural")
    await konusma.save(str(hedef))


def oku(metin: str) -> None:
    """Metni sesli oku. Onceki okuma varsa durdurulur."""
    global _aktif_thread

    if not metin or not metin.strip():
        return

    SES_KLASORU.mkdir(parents=True, exist_ok=True)
    _eski_dosyalari_temizle()

    dosya = SES_KLASORU / f"ses_{int(time.time() * 1000)}.mp3"

    # Onceki okumayi durdur
    with _kilit:
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def _calistir() -> None:
        try:
            _mixer_hazirla()
            asyncio.run(_metni_sese_cevir(metin, str(dosya)))
            if not dosya.exists() or dosya.stat().st_size < 100:
                log.yaz("SES", f"dosya olusturulamadi: {dosya}")
                return
            pygame.mixer.music.load(str(dosya))
            pygame.mixer.music.play()
        except Exception as e:
            log.yaz("SES", f"okuma hatasi: {e}")

    yeni_thread = threading.Thread(target=_calistir, daemon=True)
    yeni_thread.start()
    with _kilit:
        _aktif_thread = yeni_thread


def durdur() -> None:
    """Aktif sesli okumayi durdur."""
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


def aktif_okusu_var() -> bool:
    """Su an ses caliniyor mu?"""
    try:
        return pygame.mixer.get_init() and pygame.mixer.music.get_busy()
    except Exception:
        return False
