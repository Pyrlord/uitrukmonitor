@echo off
rem ============================================================
rem  WhatsApp-meldingen instellen voor de Uitrukmonitor
rem  Slaat je nummer en CallMeBot-sleutel op in windows\whatsapp.txt
rem  (dat bestand gaat NOOIT naar GitHub) en stuurt een testbericht.
rem ============================================================
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."

echo.
echo  WhatsApp-meldingen instellen
echo  ----------------------------
echo  Heb je al een WhatsApp-bericht naar CallMeBot gestuurd en een API-key teruggekregen?
echo  Zo niet: sluit dit venster en doe dat eerst.
echo.
set /p TEL=Je mobiele nummer met landcode, zonder spaties (bijv. +31612345678): 
set /p KEY=De API-key uit het antwoord van CallMeBot: 

> "windows\whatsapp.txt" echo telefoon=%TEL%
>> "windows\whatsapp.txt" echo apikey=%KEY%

echo.
echo Testbericht versturen...
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\collect.py --test-whatsapp
) else (
  python scripts\collect.py --test-whatsapp
)
echo.
echo Vanaf nu krijg je bij elke nieuwe brandweermelding een WhatsApp-bericht.
echo Uitzetten: verwijder het bestand windows\whatsapp.txt
pause
endlocal
