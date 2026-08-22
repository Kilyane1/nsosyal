"""Merkezi loglama — hem EXE hem Python'da calisir.

Tek dosyaya yazar (output/app_log.txt), boyut sinirli (son 100 KB).
Bu sayede:
  - Python'da test ederken dosyaya yazilir, konsola da yazdirilir
  - EXE'de --noconsole oldugu icin sadece dosyaya yazilir
  - Tum moduller ayni yerden log tutar, debug kolaylasir
"""
from __future__ import annotations

import sys
from pathlib import Path

_LOG_DOSYASI = Path("output/app_log.txt")
_MAX_BOYUT = 100 * 1024  # 100 KB


def yaz(etiket: str, mesaj: str) -> None:
    """Log satiri yaz. Dosyaya yazar, varsa konsola da yazdirir."""
    try:
        _LOG_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        satir = f"[{etiket}] {mesaj}\n"
        with open(_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(satir)
        _eskiyi_temizle()
    except Exception:
        pass
    if sys.stdout and getattr(sys.stdout, "write", None):
        try:
            sys.stdout.write(satir)
        except Exception:
            pass


def _eskiyi_temizle() -> None:
    """Log dosyasi MAX_BOYUT'u asarsa ilk yarisini sil."""
    try:
        if _LOG_DOSYASI.exists() and _LOG_DOSYASI.stat().st_size > _MAX_BOYUT:
            icerik = _LOG_DOSYASI.read_text(encoding="utf-8")
            yari = len(icerik) // 2
            # Yari noktasindan sonraki ilk \n'den kes
            kirpma = icerik.find("\n", yari) + 1
            _LOG_DOSYASI.write_text(icerik[kirpma:], encoding="utf-8")
    except Exception:
        pass