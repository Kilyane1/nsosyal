"""Uygulama ayarlari — config.json ile uyumlu sade tutulan yapi.

config.json semasi:
{
  "hotkey": "ctrl+shift+y",
  "auto_close_seconds": 30,
  "wake_words": ["analiz", "durdur"],
  "min_confidence": 0.70,
  "cooldown_seconds": 1.5,
  "gemini_api_key": "",
  "mic_energy_threshold": 0.001,
  "mic_device_index": null
}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


# Tek dogru yer: calisma dizinindeki config.json (cwd).
# Bu sayede:
#   - Kaynak koddan calistirilirsa: <proje>/config.json
#   - EXE icinden calistirilirsa: EXE'yi calistirdigin dizindeki config.json
# Hem yazma hem okuma ayni yerden yapilir, boylece cihaz
# secimi kalici olur (test ile kaynak config esitlenir).
CONFIG_DOSYASI = Path("config.json")


def _paketten_kopyala() -> None:
    """EXE ilk acilisinda _internal/config.json'u cwd'ye kopyala (yoksa).

    PyInstaller --add-data ile EXE icine yerlestirilen _internal/config.json
    read-only sanal dosyadir. Kullanici cihaz degistirince yazma islemi
    calismaz. Bu yuzden ilk acilista gercek dosyaya kopyalayip oradan
    calismak gerekiyor.
    """
    if CONFIG_DOSYASI.exists():
        return
    try:
        # PyInstaller EXE ise sys._MEIPASS ile _internal/config.json'a eris
        meipass = getattr(__import__("sys"), "_MEIPASS", None)
        if not meipass:
            return
        kaynak = Path(meipass) / "config.json"
        if kaynak.exists():
            CONFIG_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_DOSYASI.write_text(
                kaynak.read_text(encoding="utf-8"), encoding="utf-8"
            )
    except Exception:
        pass


@dataclass
class Ayarlar:
    kisayol: str = "ctrl+shift+y"
    uyandirma_kelimeleri: list[str] = field(
        default_factory=lambda: ["analiz", "durdur"]
    )
    guven_esigi: float = 0.70
    coklu_tetik_cooldown_sn: float = 1.5
    otomatik_kapanma_sn: int = 30
    gemini_api_anahtari: str = ""
    mikrofon_enerji_esik: float = 0.001
    mikrofon_cihaz_indeksi: int | None = None


def oku() -> Ayarlar:
    """config.json'dan ayarlari oku. Yoksa varsayilanlari kaydet."""
    anahtar = os.environ.get("GEMINI_API_KEY", "").strip()
    _paketten_kopyala()  # EXE ilk acilisinda _internal/config.json'dan kopyala

    if not CONFIG_DOSYASI.exists():
        ayarlar = Ayarlar(gemini_api_anahtari=anahtar)
        yaz(ayarlar)
        return ayarlar

    try:
        veri = json.loads(CONFIG_DOSYASI.read_text(encoding="utf-8"))
    except Exception:
        veri = {}

    return Ayarlar(
        kisayol=veri.get("hotkey", veri.get("kisayol", "ctrl+shift+y")),
        uyandirma_kelimeleri=veri.get("wake_words",
            veri.get("uyandirma_kelimeleri", Ayarlar().uyandirma_kelimeleri)),
        guven_esigi=float(veri.get("min_confidence",
            veri.get("guven_esigi", 0.70))),
        coklu_tetik_cooldown_sn=float(veri.get("cooldown_seconds",
            veri.get("coklu_tetik_cooldown_sn", 1.5))),
        otomatik_kapanma_sn=int(veri.get("auto_close_seconds",
            veri.get("otomatik_kapanma_sn", 30))),
        gemini_api_anahtari=anahtar or veri.get("gemini_api_key",
            veri.get("gemini_api_anahtari", "")),
        mikrofon_enerji_esik=float(veri.get("mic_energy_threshold",
            veri.get("mikrofon_enerji_esik", 0.001))),
        mikrofon_cihaz_indeksi=veri.get("mic_device_index",
            veri.get("mikrofon_cihaz_indeksi", None)),
    )


def yaz(ayarlar: Ayarlar) -> None:
    """Ayarlari config.json'a yaz."""
    CONFIG_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    veri = {
        "hotkey": ayarlar.kisayol,
        "auto_close_seconds": ayarlar.otomatik_kapanma_sn,
        "wake_words": list(ayarlar.uyandirma_kelimeleri),
        "min_confidence": ayarlar.guven_esigi,
        "cooldown_seconds": ayarlar.coklu_tetik_cooldown_sn,
        "gemini_api_key": ayarlar.gemini_api_anahtari,
        "mic_energy_threshold": ayarlar.mikrofon_enerji_esik,
        "mic_device_index": ayarlar.mikrofon_cihaz_indeksi,
    }
    CONFIG_DOSYASI.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if ayarlar.gemini_api_anahtari:
        os.environ["GEMINI_API_KEY"] = ayarlar.gemini_api_anahtari
