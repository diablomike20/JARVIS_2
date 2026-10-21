@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Jarvis telefonos eleressel indul a helyi halozaton.
echo A gepen: http://127.0.0.1:7341 - Beallitasok - Munkaterulet - Telefon
echo A telefonon: http://A_SZAMITOGEP_HELYI_IP_CIME:7341/phone
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -m jarvis.main --host 0.0.0.0
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m jarvis.main --host 0.0.0.0
) else (
  echo Elobb futtasd a setup.bat fajlt.
)
pause
