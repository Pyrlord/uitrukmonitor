@echo off
rem ============================================================
rem  Uitrukmonitor Zeist-De Bilt - verzamelaar voor Windows
rem  1. Haalt de nieuwste versie op van GitHub
rem  2. Draait scripts\collect.py (feeds ophalen, meldingen bijwerken)
rem  3. Zet nieuwe meldingen terug op GitHub
rem ============================================================
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set GITHUB_REPOSITORY=Pyrlord/uitrukmonitor

rem Ga naar de hoofdmap van de repository (de map boven deze map)
cd /d "%~dp0.."

rem Logbestand buiten de repository
set "LOGDIR=%LOCALAPPDATA%\Uitrukmonitor"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\log.txt"

echo.>> "%LOG%"
echo ===== %date% %time% ===== >> "%LOG%"

rem Naam voor de commits (geldt alleen voor deze repository)
git config user.name "uitrukmonitor-laptop" >nul
git config user.email "uitrukmonitor@users.noreply.github.com" >nul

rem 1. Laatste versie ophalen
git pull --rebase --autostash >> "%LOG%" 2>&1

rem 2. Feeds ophalen en meldingen bijwerken (py-launcher, anders python)
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\collect.py >> "%LOG%" 2>&1
) else (
  python scripts\collect.py >> "%LOG%" 2>&1
)

rem 3. Alleen opslaan als er echt iets veranderd is
rem    (data, plus website-bestanden die Claude heeft bijgewerkt)
git add data index.html windows\verzamelen.bat
git diff --cached --quiet
if %errorlevel%==0 (
  echo Geen nieuwe meldingen om op te slaan. >> "%LOG%"
) else (
  git commit -m "Bijgewerkt vanaf laptop" >> "%LOG%" 2>&1
  git push >> "%LOG%" 2>&1
)

rem Bij handmatig starten (dubbelklik): laat de laatste regels van de log zien
if /i not "%~1"=="stil" (
  echo.
  echo Laatste regels uit %LOG%:
  echo ------------------------------------------------------------
  powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 25"
  echo ------------------------------------------------------------
  pause
)
endlocal
