@echo off
setlocal
title Gundem Defteri Yerel Sunucu

REM Her durumda bu BAT dosyasinin bulundugu klasore gec
cd /d "%~dp0"

echo.
echo ============================================
echo   GUNDEM DEFTERI - YEREL SUNUCU
echo ============================================
echo.
echo Klasor:
echo %CD%
echo.
echo Python araniyor...

set "PY_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
    goto :FOUND
)

where python >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=python"
    goto :FOUND
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=python3"
    goto :FOUND
)

echo.
echo HATA: Python bulunamadi.
echo.
echo Cozum:
echo 1. Python kuruluysa Windows'ta "py" veya "python" komutunun PATH'e ekli oldugunu kontrol edin.
echo 2. Python yoksa https://www.python.org/downloads/ adresinden kurun.
echo 3. Kurulumda "Add Python to PATH" kutusunu isaretleyin.
echo.
pause
exit /b 1

:FOUND
echo Bulundu: %PY_CMD%
echo.
echo Sunucu baslatiliyor: http://localhost:8000
echo Bu pencere ACIK kalmalidir.
echo Kapatirsaniz site de kapanir.
echo.

REM Tarayiciyi 2 saniye sonra otomatik ac
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

%PY_CMD% -m http.server 8000

echo.
echo Sunucu kapandi veya baslatilamadi.
echo Yukaridaki hata mesajini kontrol edin.
echo.
pause
