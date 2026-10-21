@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Ez a kulon ag sajat mappajaban telepit. Masik Jarvis-mappat nem keres es nem modosit.
if not exist "venv\Scripts\python.exe" (
  call setup.bat
  if errorlevel 1 exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo Nem keszult el a Python kornyezet. Ellenorizd a setup.bat hibajat.
  pause
  exit /b 1
)
"venv\Scripts\python.exe" -m pip install -r requirements-ng.txt
if errorlevel 1 goto :error
where npm >nul 2>&1
if errorlevel 1 (
  echo A felulet forditasahoz Node.js es npm szukseges.
  goto :error
)
pushd web
call npm ci
if errorlevel 1 (
  popd
  goto :error
)
call npm run build
if errorlevel 1 (
  popd
  goto :error
)
popd
"venv\Scripts\python.exe" -m jarvis.main --check
if errorlevel 1 goto :error
echo.
pushd electron
call npm ci
if errorlevel 1 (
  popd
  goto :error
)
popd
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\desktop-shortcut.ps1"
if errorlevel 1 goto :error
echo Kesz. Inditas: JARVIS.vbs vagy az asztali Jarvis parancsikon.
echo A run-app.bat hibakereseshez tovabbra is hasznalhato.
pause
exit /b 0
:error
echo A telepites nem fejezodott be. A fenti hiba javitasa utan ujraindithato.
pause
exit /b 1
