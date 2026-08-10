@echo off
setlocal
title Gundem Defteri - Haber Ekle
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
echo Kullanilacak haber JSON dosyasini bu pencereye surukleyip birakabilirsiniz.
echo Ornek: examples\article-template.json
echo.
set /p INPUT=JSON dosyasi yolu: 
if "%INPUT%"=="" (
  echo Dosya belirtilmedi.
  pause
  exit /b 1
)

%PY_CMD% BUILD_ARTICLE.py "%INPUT%"
echo.
pause
