"""Global klavye kisayolu dinleyici.

ornek: ctrl+shift+y gibi kombinasyonlari yakalar ve
callback'i calistirir. 'keyboard' kutuphanesini kullanir.
"""
from __future__ import annotations

from typing import Callable

import keyboard

from modules import log


class Kisayol:
    """Tek bir klavye kisayolu."""

    def __init__(self, kombinasyon: str, callback: Callable[[], None]):
        self._kombinasyon = kombinasyon.strip().lower()
        self._callback = callback
        self._handle = None
        self._aktif = False

    def baslat(self) -> None:
        """Kisayolu dinlemeye basla."""
        if self._aktif:
            return
        try:
            self._handle = keyboard.add_hotkey(
                self._kombinasyon,
                self._guvenli_callback,
                suppress=False,
            )
            self._aktif = True
        except Exception as e:
            log.yaz("HOTKEY", f"'{self._kombinasyon}' baslatilamadi: {e}")

    def durdur(self) -> None:
        """Kisayolu dinlemeyi durdur."""
        if self._handle:
            try:
                keyboard.remove_hotkey(self._handle)
            except Exception:
                pass
            self._handle = None
            self._aktif = False

    def _guvenli_callback(self) -> None:
        """Hata olursa yut, uygulama carpmasini."""
        try:
            self._callback()
        except Exception as e:
            log.yaz("HOTKEY", f"callback hatasi: {e}")