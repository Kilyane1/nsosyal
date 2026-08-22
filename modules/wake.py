"""Sesli uyandirma dinleyicisi.

Arka planda mikrofonu dinler, belirli kelimeler
duyuldugunda (analiz, durdur) callback calistirir.

Kullanilan teknik: ses -> MFCC ozellikleri -> sklearn model.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import joblib
import numpy as np
import sounddevice as sd

from modules import log


def _log(mesaj: str) -> None:
    """Merkezi log uzerinden WAKE etiketiyle yaz."""
    log.yaz("WAKE", mesaj)


# Ses ayarlari
ORNEKLEME_HIZI = 16000  # 16 kHz
CERCEVE_SURESI = 0.5    # saniye (500 ms — 'tara' gibi kisa kelimeler icin)
HOP_SURESI    = 0.25    # saniye (250 ms hop — kelime yakalanma sansini arttirir)
COK_SESI_BEKLETME = 1.2  # ayni kelime icin minimum bekleme (false-positive engelleme)
FARKLI_KELIME_COOLDOWN = 0.3  # farkli kelime icin minimum bekleme (analiz sonrasi durdurur hemen calissin)
GUVEN_ESIK = 0.65        # minimum tahmin guveni
ENERJI_ESIK = 0.005      # varsayilan enerji esigi (kalibrasyon sonrasi guncellenir)
KALIBRASYON_SURESI = 1.5 # ilk acilista ortam gurultusu olcme suresi (saniye)
KALIBRASYON_KATSAYI = 3  # ortam gurultusunun kac kati esik olsun


class Uyandirici:
    """Arka planda mikrofonu dinleyen wake word motoru."""

    def __init__(
        self,
        uyandirildiginda: Callable[[str], None],
        model_yolu: Path,
        cihaz: Optional[int] = None,
    ):
        self._callback = uyandirildiginda
        self._model_yolu = Path(model_yolu)
        self._cihaz = cihaz
        self._siniflar: list[str] = []
        self._scaler = None
        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._akış = None
        self._calisiyor = False
        self._duraklatildi = False
        self._son_tetikleme = 0.0
        self._son_kelime = ""

    def _modeli_yukle(self) -> None:
        """Pickle dosyasindan model + scaler oku."""
        if not self._model_yolu.exists():
            raise FileNotFoundError(
                f"Model bulunamadi: {self._model_yolu}\n"
                "Once 'train_wake_word.py' calistir."
            )
        veri = joblib.load(self._model_yolu)
        # Model iki sekilde kaydedilmis olabilir
        if isinstance(veri, dict):
            self._scaler = veri.get("scaler")
            self._model = veri.get("clf") or veri.get("classifier")
            self._siniflar = list(veri.get("words", veri.get("labels", [])))
        else:
            self._scaler = None
            self._model = veri
            self._siniflar = list(getattr(veri, "classes_", []))
        self._siniflar = [
            s for s in self._siniflar if not str(s).startswith("__")
        ]
        if self._model is None:
            raise RuntimeError("Model icinde 'clf' / 'classifier' bulunamadi")

    def _cihaz_bul(self) -> int:
        """Kullanilabilir ilk mikrofonu sec.

        Onemli: MME (hostapi=0) mikrofonlarin stream acma sorunu
        yoktur; WASAPI/DS (hostapi=1) bazi ses kartlarinda
        'PaErrorCode -9983 Stream is stopped' hatasi verir.

        Bu yuzden kullanici hangi cihazi secti olursa olsun,
        MME Realtek mikrofon (varsa) onceliklendirilir.
        Kullanici sadece MME'de olmayan bir cihaz istediyse (ornek:
        cihaz 7 'Mikrofon Dizisi Realtek Audio' WASAPI), ayni
        isimde MME versiyonu varsa o kullanilir.
        """
        try:
            tum = sd.query_devices()
        except Exception:
            return 0

        # Kullanici sectiyse once onun istegini kontrol et
        if self._cihaz is not None and self._cihaz >= 0:
            try:
                info = sd.query_devices(self._cihaz)
                if info.get("max_input_channels", 0) > 0:
                    secilen_hostapi = info.get("hostapi", 0)
                    secilen_ad = info.get("name", "")
                    # WASAPI/DS ise ayni isimde MME (hostapi=0) bul.
                    # sd.query_devices bazen isimleri keser — substring eslestirmesi kullan.
                    if secilen_hostapi != 0:
                        for i, d in enumerate(tum):
                            if (d.get("max_input_channels", 0) > 0
                                and d.get("hostapi", 0) == 0):
                                ad = d.get("name", "")
                                if (secilen_ad in ad or ad in secilen_ad
                                    or secilen_ad.split("(")[0].strip() == ad.split("(")[0].strip()):
                                    _log(f"[WAKE] cihaz[{self._cihaz}] WASAPI/DS — MME alternatife gecildi: [{i}] {ad}")
                                    return i
                        # Fallback bulunamadi — MME Realtek mikrofon tercih et
                        _log(f"[WAKE] cihaz[{self._cihaz}] WASAPI/DS icin MME alternatif yok — MME Realtek aranacak")
                    else:
                        # MME ise ve ad "Realtek" iceriyorsa dogrudan dön — en iyi secim
                        return self._cihaz
            except Exception:
                pass

        # 1) MME hostapi Realtek mikrofon (en iyi secim)
        for i, d in enumerate(tum):
            if (d.get("max_input_channels", 0) > 0
                and d.get("hostapi", 0) == 0
                and "Realtek" in d.get("name", "")):
                return i
        # 2) MME herhangi bir mikrofon
        for i, d in enumerate(tum):
            if (d.get("max_input_channels", 0) > 0
                and d.get("hostapi", 0) == 0):
                return i
        # 3) Son sans — kullanici sectigi cihaz WASAPI ise zaten 1. adimda
        #    fallback denendi, yoksa kullanici cihazini dön.
        if self._cihaz is not None and self._cihaz >= 0:
            return self._cihaz
        # 4) Herhangi bir giris cihazi
        for i, d in enumerate(tum):
            if d.get("max_input_channels", 0) > 0:
                return i
        return 0

    def baslat(self) -> None:
        """Dinlemeye basla (arka plan thread'i)."""
        if self._calisiyor:
            return
        try:
            self._modeli_yukle()
        except Exception as e:
            _log(f"[WAKE] Model yuklenemedi: {e}")
            return

        self._calisiyor = True
        self._duraklatildi = False
        self._cihaz = self._cihaz_bul()
        self._thread = threading.Thread(target=self._dongu, daemon=True)
        self._thread.start()
        _log(f"[WAKE] basladi: cihaz=[{self._cihaz}] siniflar={self._siniflar}")

    def durdur(self) -> None:
        """Dinlemeyi tamamen durdur."""
        self._calisiyor = False
        if self._akış is not None:
            try:
                self._akış.stop()
                self._akış.close()
            except Exception:
                pass
            self._akış = None

    def duraklat(self) -> None:
        """Gecici olarak duraklat (mikrofon test gibi durumlar icin)."""
        self._duraklatildi = True

    def devam_et(self) -> None:
        """Duraklatmayi kaldir, tekrar dinlemeye basla."""
        self._duraklatildi = False

    def _kalibre_et(self, akış) -> float:
        """Ilk acilista ortam gurultusunu olc, dinamik enerji esigi doner.

        1.5 saniye sessizlik dinler, ortalama enerjiyi olcer, bunun KALIBRASYON_KATSAYI
        katini yeni esik olarak ayarlar. Boylece sessiz ortamda bile arka plan
        sesleri false-positive tetiklemez.
        """
        global ENERJI_ESIK
        try:
            ornek_sayisi = int(KALIBRASYON_SURESI * ORNEKLEME_HIZI)
            hop_boyutu = int(HOP_SURESI * ORNEKLEME_HIZI)
            tampon = np.zeros(ornek_sayisi, dtype=np.float32)
            toplam = 0.0
            sayac = 0
            sure_ms = int(KALIBRASYON_SURESI * 1000)
            parcalar = sure_ms // (int(HOP_SURESI * 1000))
            for _ in range(parcalar):
                parca, _ = akış.read(hop_boyutu)
                if parca.size == 0:
                    break
                toplam += float(np.abs(parca).mean())
                sayac += 1
            if sayac == 0:
                return ENERJI_ESIK
            ortalama = toplam / sayac
            yeni_esik = max(0.005, ortalama * KALIBRASYON_KATSAYI)
            _log(f"[WAKE] kalibrasyon: ortam={ortalama:.4f}, yeni esik={yeni_esik:.4f}")
            ENERJI_ESIK = yeni_esik
            return yeni_esik
        except Exception as e:
            _log(f"[WAKE] kalibrasyon hatasi: {e}")
            return ENERJI_ESIK

    def _dongu(self) -> None:
        """Ana dinleme dongusu — sliding window ile.

        Her HOP_SURESI (250 ms) kadar yeni ses al, son CERCEVE_SURESI (500 ms)
        uzunlugundaki pencereyi tahmin et. Boylece kisa kelime ('analiz')
        pencere ortasinda olsa bile yakalanir.

        Cooldown mantigi (en son tetiklenen kelimeye gore degisir):
          - Ayni kelime arka arkaya gelirse: 1.2 sn icinde yok say
          - Farkli kelime gelirse: 0.3 sn icinde yok say

        Bu sayede kullanici 'analiz durdur' diyebilir, ama 'analiz' sesi
        700 ms suruyor ve sliding window 3-4 pencere uretiyor; bunlardan
        sadece ilki tetikleme yapar (cunku 0.4 sn icinde ayni kelime yok).
        """
        _log(f"[WAKE] dongu basladi cihaz=[{self._cihaz}]")
        cerceve_boyutu = int(CERCEVE_SURESI * ORNEKLEME_HIZI)
        hop_boyutu = int(HOP_SURESI * ORNEKLEME_HIZI)
        tampon = np.zeros(cerceve_boyutu, dtype=np.float32)
        try:
            self._akış = sd.InputStream(
                samplerate=ORNEKLEME_HIZI,
                channels=1,
                dtype="float32",
                device=self._cihaz,
                blocksize=hop_boyutu,
            )
            self._akış.start()
            # Ilk acilista ortam gurultusunu olc — false-positive engelleme
            self._kalibre_et(self._akış)
            while self._calisiyor:
                if self._duraklatildi:
                    time.sleep(0.1)
                    continue
                parca, _ = self._akış.read(hop_boyutu)
                if parca.size == 0:
                    continue
                # Sliding: yeni parcayi tamponun sonuna kaydir, bas tarafi at
                tampon = np.roll(tampon, -hop_boyutu)
                tampon[-hop_boyutu:] = parca.flatten()

                enerji = float(np.abs(tampon).mean())
                if enerji < ENERJI_ESIK:
                    continue

                tahmin = self._tahmin_et(tampon.copy())
                if tahmin is None:
                    continue
                kelime, guven = tahmin
                if guven < GUVEN_ESIK:
                    continue
                # 'negatif' sinifi sadece sessizlik demek — tetikleme yapma
                if kelime == "negatif":
                    continue

                # Cooldown: ayni kelime mi yoksa farkli mi?
                gecen_sure = time.time() - self._son_tetikleme
                if self._son_kelime:
                    if kelime == self._son_kelime and gecen_sure < COK_SESI_BEKLETME:
                        continue  # ayni kelime 0.4 sn icinde tekrar yok say
                    if kelime != self._son_kelime and gecen_sure < FARKLI_KELIME_COOLDOWN:
                        continue  # farkli kelime 1 sn icinde yok say

                self._son_tetikleme = time.time()
                self._son_kelime = kelime
                _log(f"[WAKE] TETIK: '{kelime}' guven={guven:.2f} enerji={enerji:.3f}")
                try:
                    self._callback(kelime)
                except Exception as e:
                    _log(f"[WAKE] callback hatasi: {e}")
        except sd.PortAudioError as e:
            _log(f"[WAKE] PortAudio hatasi: {e}")
            _log(f"[WAKE] Bu cihaz 16 kHz desteklemiyor olabilir. Mikrofon Test'ten farkli bir cihaz secin.")
            self._calisiyor = False
        except Exception as e:
            _log(f"[WAKE] ses hatasi: {e}")
            self._calisiyor = False
        finally:
            if self._akış is not None:
                try:
                    self._akış.stop()
                    self._akış.close()
                except Exception:
                    pass
                self._akış = None

    def _tahmin_et(self, ses: np.ndarray) -> Optional[tuple[str, float]]:
        """Ses cercevesinden kelime ve guven tahmin et."""
        try:
            ozellikler = self._mfcc_ozellik_cikar(ses)
            if ozellikler is None:
                return None
            if self._scaler is not None:
                ozellikler = self._scaler.transform([ozellikler])[0]
            olasiliklar = self._model.predict_proba([ozellikler])[0]
            en_iyi = int(np.argmax(olasiliklar))
            kelime = str(self._model.classes_[en_iyi])
            guven = float(olasiliklar[en_iyi])
            return (kelime, guven)
        except Exception:
            return None

    def _mfcc_ozellik_cikar(self, ses: np.ndarray) -> Optional[np.ndarray]:
        """Sesten 78 ozellik cikar: 13 MFCC mean+std + delta + delta-delta.

        train_wake_word.py ile birebir ayni olmali — aksi halde scaler uyumsuzlugu olur
        ve tum tahminler yanlis cikar.
        """
        try:
            import librosa
            with __import__("warnings").catch_warnings():
                __import__("warnings").simplefilter("ignore")
                mfcc = librosa.feature.mfcc(y=ses, sr=ORNEKLEME_HIZI, n_mfcc=13, n_fft=512, hop_length=160)
                d1 = librosa.feature.delta(mfcc)
                d2 = librosa.feature.delta(mfcc, order=2)
            return np.concatenate(
                [mfcc.mean(axis=1), mfcc.std(axis=1),
                 d1.mean(axis=1), d1.std(axis=1),
                 d2.mean(axis=1), d2.std(axis=1)]
            ).astype(np.float32)
        except Exception:
            return None