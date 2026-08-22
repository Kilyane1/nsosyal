"""EXE olusturma - sadece kullanilan paketleri dahil et.

requirements.txt'te torch/transformers/easyocr/faster_whisper/streamlit var
AMA biz artik bunlari kullanmiyoruz (sadece Gemini API + sklearn wake word).
PyInstaller bunlari transitively dahil ediyordu — exclude ile disari birak.
"""
import subprocess
import sys
import os
import time
from pathlib import Path

os.chdir(r"C:\Users\ntstu\Desktop\icerik-dogrulama")

import shutil
for d in ["build", "dist"]:
    p = Path(d)
    if p.exists():
        try:
            shutil.rmtree(p)
        except PermissionError:
            pass
for f in Path(".").glob("*.spec"):
    f.unlink()

# Dahil et: kullanilan paketler
HIDDEN = [
    "tkinter", "tkinter.ttk", "tkinter.scrolledtext", "tkinter.messagebox",
    "sounddevice", "mss",
    "keyboard",
    "requests",
    "PIL", "PIL.Image",
    "pygame", "pygame.mixer",
    "edge_tts",
    "librosa", "librosa.feature", "librosa.effects",
    "numpy",
    # scipy: joblib.load() icindeki sklearn modeli scipy.special'e bagimli
    # ve lazy import yapiyor — PyInstaller onu goremiyor, hata veriyor.
    "scipy", "scipy.signal", "scipy.special", "scipy.integrate",
    "scipy.interpolate", "scipy.fftpack", "scipy.io", "scipy.linalg",
    "scipy.spatial", "scipy.stats", "scipy.odr",
    # sklearn: joblib modelin tamami
    "sklearn", "sklearn.base", "sklearn.linear_model", "sklearn.preprocessing",
    "sklearn.utils", "sklearn.metrics", "sklearn.exceptions",
    "joblib", "joblib.numpy_pickle",
    "asyncio", "threading",
    "json", "csv", "dataclasses",
]

# Disari birak: kullanilmayan agir paketler
EXCLUDE = [
    "torch", "torchvision", "torchaudio",
    "transformers", "huggingface_hub",
    "easyocr", "cv2",
    "faster_whisper", "whisper",
    "streamlit",
    "pandas", "numpy.distutils",
    "IPython", "jupyter",
    "pytest",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "matplotlib",
    "sympy",
]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--noconsole", "--onedir",
    "--name", "IcerikTarayici",
    "--add-data", "config.json;.",
    "--add-data", "modules;modules",
    "--add-data", "models;models",
    # Strip — sembol tablosunu cikar, EXE küçülür
    "--noupx",
]
for h in HIDDEN:
    cmd.extend(["--hidden-import", h])
for e in EXCLUDE:
    cmd.extend(["--exclude-module", e])
cmd.append("tray_app.py")

print(f"PyInstaller baslatiliyor")
print(f"  Hidden-import: {len(HIDDEN)}")
print(f"  Exclude-module: {len(EXCLUDE)}")
print(f"  Toplam arguman: {len(cmd)}")

t0 = time.time()
with open("build_output.log", "w", encoding="utf-8") as logf:
    logf.write(f"=== Build basladi: hidden={len(HIDDEN)} exclude={len(EXCLUDE)} ===\n")
    logf.flush()
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in process.stdout:
        logf.write(line)
        logf.flush()
    process.wait()
    t1 = time.time()
    logf.write(f"\n\nEXIT CODE: {process.returncode}\n")
    logf.write(f"SURE: {t1-t0:.1f} saniye\n")

print(f"Build tamamlandi (exit={process.returncode}), {time.time()-t0:.1f}s")
