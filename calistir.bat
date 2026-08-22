@echo off
REM Icerik Tarayici baslatici.
REM EXE kendi klasoru icinde _internal/ dosyalarini arar,
REM bu yuzden cd /d ile oraya gecmek sart.

setlocal
cd /d "%~dp0dist\IcerikTarayici"

if not exist "IcerikTarayici.exe" (
    echo HATA: IcerikTarayici.exe bulunamadi.
    echo "%~dp0dist\IcerikTarayici" icinde olmali.
    pause
    exit /b 1
)

start "" "IcerikTarayici.exe" %*