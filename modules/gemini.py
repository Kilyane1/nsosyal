"""Google Gemini ile gorsel analiz.

Uc sey yapar:
  1. Ekran goruntusunu kucultur (hiz kazandirir)
  2. Gemini'ye gonderir (varsayilan: gemini-3-flash-preview)
  3. Turkce ozet alip doner
"""
from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PIL import Image


ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3-flash-preview:generateContent"
)

KULLANIM_DOSYASI = Path("output/gemini_kullanim.json")
GUNLUK_UCRETSIZ_LIMIT = 1500

PROMPT = (
    "Gorev: Ekran goruntusunu Turkce kisaca ozetle.\n\n"
    "KURALLAR:\n"
    "- Sadece markdown, baslik ve madde isareti kullan.\n"
    "- Gereksiz giris yok. Direkt bilgi ver.\n"
    '- "belirsiz" yaz, uydurma.\n'
    "- Her bolum 1 satir.\n\n"
    "FORMAT:\n"
    "**Ozet:** <1 cumle>\n\n"
    "**Yazi:** <ekrandaki onemli metinler>\n\n"
    "**Niyet:** <kullanici ne yapiyor, 1 cumle>\n\n"
    "**Risk:** <risk/yanlis bilgi varsa, yoksa 'yok'>\n\n"
    "Maks 200 kelime."
)


def _bugunun_kullanimini_kaydet(basarili: bool) -> None:
    """Bugunun tarihi icin basari/hata sayisini tutar."""
    KULLANIM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    bugun = datetime.now().strftime("%Y-%m-%d")
    veri = {}
    if KULLANIM_DOSYASI.exists():
        try:
            veri = json.loads(KULLANIM_DOSYASI.read_text(encoding="utf-8"))
        except Exception:
            veri = {}
    if veri.get("tarih") != bugun:
        veri = {"tarih": bugun, "basarili": 0, "hatali": 0}
    anahtar = "basarili" if basarili else "hatali"
    veri[anahtar] += 1
    KULLANIM_DOSYASI.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def kullanim_durumu() -> dict:
    """Bugunku API kullanimini sozluk olarak doner."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    if not KULLANIM_DOSYASI.exists():
        return {"kullanilan": 0, "limit": GUNLUK_UCRETSIZ_LIMIT}
    try:
        veri = json.loads(KULLANIM_DOSYASI.read_text(encoding="utf-8"))
        if veri.get("tarih") != bugun:
            return {"kullanilan": 0, "limit": GUNLUK_UCRETSIZ_LIMIT}
        toplam = veri.get("basarili", 0) + veri.get("hatali", 0)
        return {"kullanilan": toplam, "limit": GUNLUK_UCRETSIZ_LIMIT}
    except Exception:
        return {"kullanilan": 0, "limit": GUNLUK_UCRETSIZ_LIMIT}


def ekrani_analiz_et(resim_yolu: Path) -> dict:
    """Ekran goruntusunu Gemini'ye gonderir ve Turkce ozet alir.

    Donus:
      {"metin": str, "hata": Optional[str], "kullanim": dict}
    """
    api_anahtari = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_anahtari:
        _bugunun_kullanimini_kaydet(basarili=False)
        return {
            "metin": "",
            "hata": "API anahtari yok. Ayarlar'dan girin.",
            "kullanim": kullanim_durumu(),
        }

    if not Path(resim_yolu).exists():
        return {"metin": "", "hata": f"Dosya yok: {resim_yolu}"}

    try:
        # Gorseli kucult ve JPEG olarak gonder (hiz icin)
        resim = Image.open(resim_yolu).convert("RGB")
        resim.thumbnail((512, 512))
        tampon = io.BytesIO()
        resim.save(tampon, format="JPEG", quality=60)
        resim_b64 = base64.b64encode(tampon.getvalue()).decode("ascii")

        # API istegi
        url = f"{ENDPOINT}?key={api_anahtari}"
        veri = {
            "contents": [{
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": resim_b64,
                        }
                    },
                ]
            }]
        }

        yanit = requests.post(url, json=veri, timeout=20)

        if yanit.status_code != 200:
            _bugunun_kullanimini_kaydet(basarili=False)
            return {
                "metin": "",
                "hata": f"HTTP {yanit.status_code}: {yanit.text[:200]}",
                "kullanim": kullanim_durumu(),
            }

        try:
            metin = yanit.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            _bugunun_kullanimini_kaydet(basarili=False)
            return {
                "metin": "",
                "hata": f"Beklenmedik yanit formati: {e}",
                "kullanim": kullanim_durumu(),
            }

        _bugunun_kullanimini_kaydet(basarili=True)
        return {
            "metin": metin,
            "hata": None,
            "kullanim": kullanim_durumu(),
        }

    except requests.exceptions.Timeout:
        _bugunun_kullanimini_kaydet(basarili=False)
        return {"metin": "", "hata": "Gemini zaman asimina ugradi (20 sn)."}
    except Exception as e:
        _bugunun_kullanimini_kaydet(basarili=False)
        return {"metin": "", "hata": f"{type(e).__name__}: {e}"}