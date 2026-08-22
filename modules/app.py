"""Tkinter arayuzu — tum pencereler tek dosyada.

Icerik:
  - Ana pencere (butonlar, durum, API key bilgisi)
  - Sonuc penceresi (analiz sonucu)
  - Ayar penceresi (kisayol, kelimeler, API key, mikrofon)
  - Mikrofon test penceresi (ayri dosyada)

Bu modul singleton bir Uygulama nesnesi sunar.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from modules import config
from modules.gemini import kullanim_durumu, GUNLUK_UCRETSIZ_LIMIT


# === Sonuc Penceresi ===

class SonucPenceresi:
    """Analiz sonucunu gosteren pencere. Tek bir ornek kullanilir."""

    _tek = None

    @classmethod
    def goster(cls, ebeveyn: tk.Tk, metin: str) -> None:
        if cls._tek is None or not cls._tek._hayatta():
            cls._tek = SonucPenceresi(ebeveyn)
            cls._tek._olustur()
        cls._tek._guncelle(metin)

    def __init__(self, ebeveyn: tk.Tk):
        self.ebeveyn = ebeveyn
        self.pencere: Optional[tk.Toplevel] = None
        self.metin_alani: Optional[scrolledtext.ScrolledText] = None
        self._kapanis_id: Optional[str] = None

    def _hayatta(self) -> bool:
        try:
            return bool(self.pencere and self.pencere.winfo_exists())
        except Exception:
            return False

    def _olustur(self) -> None:
        pencere = tk.Toplevel(self.ebeveyn)
        pencere.title("Analiz Sonucu")
        pencere.geometry("720x520+150+100")
        pencere.configure(bg="#f8fafc")
        pencere.protocol("WM_DELETE_WINDOW", self._gizle)

        tk.Label(
            pencere, text="📊 Analiz Sonucu",
            font=("Segoe UI", 13, "bold"),
            fg="#1e40af", bg="#f8fafc",
        ).pack(pady=(12, 8))

        metin_alani = scrolledtext.ScrolledText(
            pencere, wrap="word",
            font=("Segoe UI", 10),
            bg="#ffffff", fg="#0f172a",
            padx=10, pady=10,
        )
        metin_alani.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.pencere = pencere
        self.metin_alani = metin_alani

    def _guncelle(self, metin: str) -> None:
        if not self.metin_alani:
            return
        try:
            # Gizliyse geri getir
            self.pencere.deiconify()
            self.pencere.lift()
        except Exception:
            pass
        self.metin_alani.delete("1.0", "end")
        self.metin_alani.insert("1.0", metin)
        self._otomatik_kapanma_ayarla()

    def _otomatik_kapanma_ayarla(self) -> None:
        if self._kapanis_id:
            try:
                self.pencere.after_cancel(self._kapanis_id)
            except Exception:
                pass
        try:
            icerik = self.metin_alani.get("1.0", "end") if self.metin_alani else ""
            # ~200 karakter/dakika okuma hizi + 5 dk guvenlik payi
            karakter = len(icerik)
            sure_sn = max(120, min(900, karakter // 4 + 60))
            self._kapanis_id = self.pencere.after(sure_sn * 1000, self._gizle)
        except Exception:
            pass

    def _gizle(self) -> None:
        try:
            self.pencere.withdraw()
        except Exception:
            pass


# === Ayar Penceresi ===

class AyarPenceresi:
    """Kullanici ayarlarini degistirdigi pencere."""

    _tek = None

    @classmethod
    def goster(cls, ebeveyn: tk.Tk, kaydedildi_callback=None) -> None:
        if cls._tek is None or not cls._tek._hayatta():
            cls._tek = AyarPenceresi(ebeveyn, kaydedildi_callback)
            cls._tek._olustur()
        cls._tek._one_getir()

    def __init__(self, ebeveyn: tk.Tk, kaydedildi_callback):
        self.ebeveyn = ebeveyn
        self.kaydedildi_callback = kaydedildi_callback
        self.pencere: Optional[tk.Toplevel] = None
        self.ayarlar = config.oku()
        self._onceki_mikrofon = self.ayarlar.mikrofon_cihaz_indeksi

    def _hayatta(self) -> bool:
        try:
            return bool(self.pencere and self.pencere.winfo_exists())
        except Exception:
            return False

    def _one_getir(self) -> None:
        try:
            self.pencere.lift()
            self.pencere.focus_force()
        except Exception:
            pass

    def _olustur(self) -> None:
        pencere = tk.Toplevel(self.ebeveyn)
        pencere.title("Ayarlar")
        pencere.geometry("640x520+150+150")
        pencere.configure(bg="#f8fafc")
        pencere.protocol("WM_DELETE_WINDOW", pencere.destroy)
        self.pencere = pencere

        tk.Label(
            pencere, text="Icerik Tarayici Ayarlari",
            font=("Segoe UI", 14, "bold"),
            fg="#1e40af", bg="#f8fafc",
        ).pack(pady=(16, 4))

        tk.Label(
            pencere, text="Degisiklik yap ve 'Uygula' tikla.",
            font=("Segoe UI", 9), fg="#64748b", bg="#f8fafc",
        ).pack()

        # Aktif degerler
        aktif_frame = ttk.LabelFrame(pencere, text="Su an Aktif", padding=10)
        aktif_frame.pack(fill="x", padx=20, pady=12)
        aktif_metin = tk.StringVar()
        aktif_lbl = ttk.Label(
            aktif_frame, textvariable=aktif_metin,
            font=("Consolas", 9), justify="left", background="#f8fafc",
        )
        aktif_lbl.pack(anchor="w")

        def aktif_yenile():
            anahtar = self.ayarlar.gemini_api_anahtari
            maskeli = (anahtar[:6] + "..." + anahtar[-4:]) if len(anahtar) > 12 else (anahtar[:4] + "..." if anahtar else "(yok)")
            mikrofon = f"[{self.ayarlar.mikrofon_cihaz_indeksi}]" if self.ayarlar.mikrofon_cihaz_indeksi is not None and self.ayarlar.mikrofon_cihaz_indeksi >= 0 else "(otomatik)"
            aktif_metin.set(
                f"Kisayol:      {self.ayarlar.kisayol}\n"
                f"Uyandirma:    {', '.join(self.ayarlar.uyandirma_kelimeleri)}\n"
                f"Mikrofon:     {mikrofon}\n"
                f"API key:      {maskeli}"
            )

        aktif_yenile()

        # Form
        form = ttk.LabelFrame(pencere, text="Degistir", padding=10)
        form.pack(fill="x", padx=20)

        tk.Label(form, text="Kisayol (orn: ctrl+shift+y):", background="#f8fafc").grid(row=0, column=0, sticky="w", pady=4)
        kisayol_var = tk.StringVar(value=self.ayarlar.kisayol)
        ttk.Entry(form, textvariable=kisayol_var, width=30).grid(row=0, column=1, sticky="ew", padx=6)

        tk.Label(form, text="Uyandirma kelimeleri:", background="#f8fafc").grid(row=1, column=0, sticky="w", pady=4)
        kelimeler_var = tk.StringVar(value=", ".join(self.ayarlar.uyandirma_kelimeleri))
        ttk.Entry(form, textvariable=kelimeler_var, width=40).grid(row=1, column=1, sticky="ew", padx=6)

        # Mikrofon combobox — tum giris cihazlarini listele
        import sounddevice as sd
        mikrofon_etiketleri = ["(otomatik)"]
        mikrofon_idleri = [None]
        try:
            for i, d in enumerate(sd.query_devices()):
                if d.get("max_input_channels", 0) > 0:
                    mikrofon_etiketleri.append(f"[{i}] {d['name'][:50]}")
                    mikrofon_idleri.append(i)
        except Exception:
            pass
        mevcut_idx = 0
        if self.ayarlar.mikrofon_cihaz_indeksi is not None:
            try:
                mevcut_idx = mikrofon_idleri.index(self.ayarlar.mikrofon_cihaz_indeksi)
            except ValueError:
                mevcut_idx = 0
        mikrofon_var = tk.StringVar(value=mikrofon_etiketleri[mevcut_idx])

        tk.Label(form, text="Mikrofon:", background="#f8fafc").grid(row=2, column=0, sticky="w", pady=4)
        mikrofon_combo = ttk.Combobox(
            form, textvariable=mikrofon_var,
            values=mikrofon_etiketleri, state="readonly", width=48,
        )
        mikrofon_combo.grid(row=2, column=1, sticky="ew", padx=6)

        tk.Label(form, text="Gemini API key:", background="#f8fafc").grid(row=3, column=0, sticky="w", pady=4)
        anahtar_var = tk.StringVar(value=self.ayarlar.gemini_api_anahtari)
        anahtar_entry = ttk.Entry(form, textvariable=anahtar_var, width=50, show="*")
        anahtar_entry.grid(row=3, column=1, sticky="ew", padx=6)

        goster_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form, text="Goster",
            variable=goster_var,
            command=lambda: anahtar_entry.config(show="" if goster_var.get() else "*"),
        ).grid(row=4, column=1, sticky="w")

        form.columnconfigure(1, weight=1)

        # Butonlar
        buton_frame = tk.Frame(pencere, bg="#f8fafc")
        buton_frame.pack(pady=12)

        def kaydet():
            # Secilen mikrofonun cihaz idsini bul
            secilen_mikrofon_id = mikrofon_idleri[mikrofon_etiketleri.index(mikrofon_var.get())]
            yeni = config.Ayarlar(
                kisayol=kisayol_var.get().strip().lower() or "ctrl+shift+y",
                uyandirma_kelimeleri=[w.strip() for w in kelimeler_var.get().split(",") if w.strip()],
                guven_esigi=self.ayarlar.guven_esigi,
                coklu_tetik_cooldown_sn=self.ayarlar.coklu_tetik_cooldown_sn,
                otomatik_kapanma_sn=self.ayarlar.otomatik_kapanma_sn,
                gemini_api_anahtari=anahtar_var.get().strip(),
                mikrofon_enerji_esik=self.ayarlar.mikrofon_enerji_esik,
                mikrofon_cihaz_indeksi=secilen_mikrofon_id,
            )
            config.yaz(yeni)
            self.ayarlar = yeni
            aktif_yenile()
            uygula_buton.config(text="✓ Kaydedildi!", bg="#16a34a")
            pencere.after(2000, lambda: uygula_buton.config(text="Uygula", bg="#1e40af"))
            if self.kaydedildi_callback:
                self.kaydedildi_callback()
            # Mikrofon degisti ise wake'i yeniden baslat
            if secilen_mikrofon_id != self._onceki_mikrofon:
                self._onceki_mikrofon = secilen_mikrofon_id
                Uygulama.mikrofon_degisti(secilen_mikrofon_id)

        uygula_buton = tk.Button(
            buton_frame, text="Uygula", command=kaydet,
            bg="#1e40af", fg="white",
            activebackground="#1d4ed8",
            font=("Segoe UI", 10, "bold"), relief="flat",
            padx=20, pady=8, cursor="hand2",
        )
        uygula_buton.pack(side="left", padx=4)

        tk.Button(
            buton_frame, text="Kapat", command=pencere.destroy,
            bg="#e2e8f0", fg="#0f172a",
            font=("Segoe UI", 10), relief="flat",
            padx=20, pady=8, cursor="hand2",
        ).pack(side="left", padx=4)

        tk.Label(
            pencere,
            text="Ucretsiz Gemini API key: aistudio.google.com/app/apikey",
            font=("Segoe UI", 9), fg="#94a3b8", bg="#f8fafc",
        ).pack(pady=(0, 12))


# === Ana Uygulama ===

class Uygulama:
    """Ana pencere ve thread-safe erisim noktasi."""

    def __init__(self):
        self.kok: Optional[tk.Tk] = None
        self.durum_var: Optional[tk.StringVar] = None
        self.analiz_buton: Optional[tk.Button] = None
        self.api_etiket: Optional[tk.Label] = None
        self.ayarlar = config.oku()
        self._analiz_callback: Optional[Callable[[str], None]] = None
        self._uyandirici = None  # mic test duraklatmasi icin (wake.Uyandirici)

    # --- Disaridan cagrilan metodlar ---

    def durum(self, metin: str) -> None:
        if self.kok:
            try:
                self.kok.after(0, lambda: self._durum_ayarla(metin))
            except Exception:
                pass

    def mesgul(self, aktif: bool) -> None:
        if self.kok:
            try:
                self.kok.after(0, lambda: self._mesgul_uygula(aktif))
            except Exception:
                pass

    def sonuc_goster(self, metin: str) -> None:
        if self.kok:
            try:
                self.kok.after(0, lambda: SonucPenceresi.goster(self.kok, metin))
            except Exception:
                pass

    def ayarlar_penceresi(self) -> None:
        if self.kok:
            try:
                self.kok.after(0, lambda: AyarPenceresi.goster(self.kok, self._ayarlar_kaydedildi))
            except Exception:
                pass

    def mikrofon_degisti(self, cihaz_no: Optional[int]) -> None:
        """Kullanici ayarlardan mikrofon degistirdi — wake'i yeniden baslat."""
        from modules.wake import Uyandirici
        import sys as _sys
        # EXE icinde sys._MEIPASS, normalde proje kok
        _kok = Path(_sys._MEIPASS) if hasattr(_sys, "_MEIPASS") else Path(__file__).parent.parent
        eski = self.get_uyandirici()
        if eski:
            try:
                eski.durdur()
            except Exception:
                pass
        yeni = Uyandirici(
            uyandirildiginda=_sesli_komut_callback(),
            model_yolu=_kok / "models" / "wake_word_model.pkl",
            cihaz=cihaz_no,
        )
        yeni.baslat()
        self.set_uyandirici(yeni)

    # --- Dahili ---

    def baslat(self) -> None:
        self.kok = tk.Tk()
        self.kok.title("Icerik Tarayici")
        self.kok.geometry("680x460+200+150")
        self.kok.configure(bg="#f8fafc")
        self.kok.protocol("WM_DELETE_WINDOW", _cikis)

        self._arayuzu_kur()
        self._api_etiket_guncelle()
        self._kullanim_dongusu()

        self.kok.mainloop()

    def _arayuzu_kur(self) -> None:
        tk.Label(
            self.kok, text="Icerik Tarayici",
            font=("Segoe UI", 16, "bold"),
            fg="#1e40af", bg="#f8fafc",
        ).pack(pady=(20, 4))

        tk.Label(
            self.kok,
            text="Mikrofon veya kisayol ile ekrani analiz eder",
            font=("Segoe UI", 10),
            fg="#475569", bg="#f8fafc",
        ).pack(pady=(0, 16))

        self.analiz_buton = tk.Button(
            self.kok,
            text="🔍 Yeni Analiz Yap",
            font=("Segoe UI", 11, "bold"),
            bg="#1e40af", fg="white",
            activebackground="#1d4ed8", activeforeground="white",
            relief="flat",
            padx=24, pady=12, cursor="hand2",
            command=self._analiz_buton_tiklandi,
        )
        self.analiz_buton.pack(pady=6, fill="x", padx=40)

        bilgi = tk.Frame(self.kok, bg="#f8fafc")
        bilgi.pack(pady=(12, 0), padx=40, fill="x")

        tk.Label(
            bilgi, text=f"Kisayol: {self.ayarlar.kisayol.replace('+', ' + ').upper()}",
            font=("Segoe UI", 9), fg="#64748b", bg="#f8fafc", anchor="w",
        ).pack(fill="x")
        tk.Label(
            bilgi, text=f"Sesli: {', '.join(self.ayarlar.uyandirma_kelimeleri)}",
            font=("Segoe UI", 9), fg="#64748b", bg="#f8fafc", anchor="w",
        ).pack(fill="x")
        tk.Label(
            bilgi, text="Ayarlar: CTRL + SHIFT + S",
            font=("Segoe UI", 9), fg="#64748b", bg="#f8fafc", anchor="w",
        ).pack(fill="x")

        self.api_etiket = tk.Label(
            bilgi, font=("Segoe UI", 9, "bold"), bg="#f8fafc", anchor="w",
        )
        self.api_etiket.pack(fill="x", pady=(6, 0))

        # Alt butonlar
        alt = tk.Frame(self.kok, bg="#f8fafc")
        alt.pack(side="bottom", fill="x", padx=20, pady=15)

        tk.Button(
            alt, text="⚙ Ayarlar",
            font=("Segoe UI", 9), relief="flat",
            bg="#e2e8f0", fg="#0f172a",
            activebackground="#cbd5e1",
            padx=12, pady=5, cursor="hand2",
            command=self.ayarlar_penceresi,
        ).pack(side="left", padx=2)

        tk.Button(
            alt, text="✕ Cikis",
            font=("Segoe UI", 9), relief="flat",
            bg="#fee2e2", fg="#b91c1c",
            activebackground="#fecaca",
            padx=12, pady=5, cursor="hand2",
            command=_cikis,
        ).pack(side="right")

        # Durum cubugu
        self.durum_var = tk.StringVar(value="Hazir — dinlemede")
        tk.Label(
            self.kok, textvariable=self.durum_var,
            font=("Segoe UI", 10, "bold"),
            fg="#1e40af", bg="#dbeafe",
            anchor="w", padx=10, pady=6,
        ).pack(side="bottom", fill="x", padx=10, pady=(0, 10))

    def _durum_ayarla(self, metin: str) -> None:
        if self.durum_var:
            self.durum_var.set(metin)

    def _mesgul_uygula(self, aktif: bool) -> None:
        if self.analiz_buton:
            try:
                self.analiz_buton.config(state="disabled" if aktif else "normal")
            except Exception:
                pass

    def _api_etiket_guncelle(self) -> None:
        if not self.api_etiket:
            return
        anahtar = self.ayarlar.gemini_api_anahtari
        if anahtar:
            maskeli = anahtar[:6] + "..." + anahtar[-4:] if len(anahtar) > 12 else anahtar[:4] + "..."
            self.api_etiket.config(text=f"🔑 Gemini API: {maskeli}", fg="#16a34a")
        else:
            self.api_etiket.config(
                text="⚠ Gemini API key yok — Ayarlar'dan girin",
                fg="#dc2626",
            )

    def _kullanim_dongusu(self) -> None:
        """Her 30 saniyede API kullanim sayisini goster."""
        if not self.kok:
            return
        try:
            durum = kullanim_durumu()
            self._api_etiket_guncelle()
            self.kok.after(30000, self._kullanim_dongusu)
        except Exception:
            pass

    def _analiz_buton_tiklandi(self) -> None:
        if self._analiz_callback:
            threading.Thread(
                target=lambda: self._analiz_callback("buton"),
                daemon=True,
            ).start()

    def set_analiz_callback(self, callback) -> None:
        """tray_app.py bu metodu cagirarak callback'i set eder."""
        self._analiz_callback = callback

    def set_uyandirici(self, dinleyici) -> None:
        """Wake dinleyici referansini set et (mic test duraklatmasi icin)."""
        self._uyandirici = dinleyici

    def get_uyandirici(self):
        """Wake dinleyiciyi doner (mic test ve diger moduller icin)."""
        return self._uyandirici

    def _ayarlar_kaydedildi(self) -> None:
        """Ayarlar kaydedildikten sonra config'i yeniden oku."""
        self.ayarlar = config.oku()
        self._api_etiket_guncelle()


# === Yardimci ===

def _sesli_komut_callback():
    """tray_app.sesli_komut_geldi'a gec donduren proxy.

    Ayarlardan mikrofon degistirildiginde wake yeniden baslatilir
    ve ayni callback tekrar kullanilir.
    """
    from tray_app import sesli_komut_geldi
    return sesli_komut_geldi


# === Cikis ===

def _cikis() -> None:
    try:
        from modules.tts import durdur
        durdur()
    except Exception:
        pass
    import sys
    sys.exit(0)


# === Singleton ===

_uygulama = Uygulama()


# Geriye uyumluluk icin eski isim
App = _uygulama