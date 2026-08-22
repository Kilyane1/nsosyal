"""Analiz pipeline — sadece Gemini'yi cagirir.

Onceki versiyonlarda OCR/BLIP/Yandex gibi bircok modul vardi.
Simdi sadece tek bir AI kullaniliyor (Gemini Flash) — daha temiz,
daha hizli ve daha kaliteli sonuc.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from modules.gemini import ekrani_analiz_et


def analiz_et(resim_yolu: Path) -> Dict[str, Any]:
    """Ekran goruntusunu Gemini ile analiz et."""
    basla = time.time()
    sonuc = ekrani_analiz_et(resim_yolu)
    sonuc["sure_sn"] = round(time.time() - basla, 2)
    sonuc["resim"] = str(resim_yolu)
    return sonuc


def rapor_yaz(sonuc: Dict[str, Any], hedef_klasor: Path) -> Dict[str, Path]:
    """Markdown + JSON rapor olarak kaydet."""
    hedef_klasor.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_dosya = hedef_klasor / f"rapor_{ts}.md"
    json_dosya = hedef_klasor / f"rapor_{ts}.json"

    md = (
        f"# Analiz Raporu — {ts}\n\n"
        f"**Kaynak:** `{sonuc.get('resim', '?')}`\n"
        f"**Sure:** {sonuc.get('sure_sn', 0)} saniye\n\n"
        f"---\n\n"
        f"{sonuc.get('metin', '(icerik yok)')}\n"
    )
    if sonuc.get("hata"):
        md += f"\n\n## Hata\n\n{sonuc['hata']}\n"

    md_dosya.write_text(md, encoding="utf-8")
    json_dosya.write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"markdown": md_dosya, "json": json_dosya}