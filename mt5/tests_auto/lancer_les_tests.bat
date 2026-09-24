@echo off
chcp 65001 >nul
setlocal
REM =====================================================================
REM  Lance les 5 backtests de l'EA FTMO_TrendBreakout l'un apres l'autre.
REM  Rien a modifier : double-cliquez simplement sur ce fichier.
REM  Avant : compilez l'EA sous le nom FTMO_TrendBreakout et FERMEZ MT5.
REM =====================================================================

REM --- 1. Trouver le dossier des donnees MT5 qui contient l'EA compile
set "DATA="
for /d %%D in ("%APPDATA%\MetaQuotes\Terminal\*") do if exist "%%~fD\MQL5\Experts\FTMO_TrendBreakout.ex5" set "DATA=%%~fD"
if defined DATA goto found_data
echo Je ne trouve pas l'EA compile FTMO_TrendBreakout.ex5.
echo Dans MT5 : Fichier ^> Ouvrir le dossier des donnees, copiez l'adresse du dossier,
set /p "DATA=collez-la ici puis appuyez sur Entree : "
set "DATA=%DATA:"=%"
:found_data
if not exist "%DATA%\MQL5\Experts\FTMO_TrendBreakout.ex5" goto no_ea
echo Dossier des donnees : %DATA%

REM --- 2. Trouver terminal64.exe (le chemin est note dans origin.txt)
set "MT5="
if exist "%DATA%\origin.txt" for /f "usebackq delims=" %%L in (`type "%DATA%\origin.txt"`) do set "MT5=%%L\terminal64.exe"
if exist "%MT5%" goto found_mt5
if exist "%DATA%\terminal64.exe" set "MT5=%DATA%\terminal64.exe"
if exist "%MT5%" goto found_mt5
echo Je ne trouve pas terminal64.exe.
echo Clic droit sur le raccourci MetaTrader 5 ^> Proprietes ^> Cible : copiez ce chemin,
set /p "MT5=collez-le ici puis appuyez sur Entree : "
set "MT5=%MT5:"=%"
if not exist "%MT5%" goto no_mt5
:found_mt5
echo MetaTrader 5 : %MT5%

REM --- 3. Copier les reglages et lancer les tests
if not exist "%DATA%\MQL5\Profiles\Tester" mkdir "%DATA%\MQL5\Profiles\Tester"
copy /Y "%~dp0za_*.set" "%DATA%\MQL5\Profiles\Tester\" >nul
if not exist "%DATA%\za_reports" mkdir "%DATA%\za_reports"

for %%F in ("%~dp0za_*.ini") do (
  echo.
  echo === Test %%~nF en cours : MT5 va s'ouvrir puis se fermer tout seul...
  start "" /wait "%MT5%" /config:"%%~fF"
)

echo.
echo Termine. Les rapports sont dans : %DATA%\za_reports
start "" "%DATA%\za_reports"
pause
exit /b 0

:no_ea
echo.
echo L'EA compile est introuvable dans "%DATA%\MQL5\Experts".
echo Ouvrez FTMO_TrendBreakout.mq5 dans MetaEditor et compilez-le (F7), puis relancez.
pause
exit /b 1

:no_mt5
echo.
echo terminal64.exe introuvable : "%MT5%"
pause
exit /b 1
