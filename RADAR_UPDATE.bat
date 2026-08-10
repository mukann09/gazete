@echo off
setlocal
title Gundem Defteri V17.2 - Guncelle
cd /d "%~dp0"

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

echo Python bulunamadi.
pause
exit /b 1

:FOUND
echo.
echo Gerekli ucretsiz kutuphane kontrol ediliyor...
%PY_CMD% -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Kutuphane kurulamadı.
  pause
  exit /b 1
)

echo.
echo GUNDEM RADARI + GERCEK YAYINCI BAGLANTISI
echo Ucretli API kullanilmaz.
echo.
%PY_CMD% RADAR_UPDATE.py
echo.
pause
