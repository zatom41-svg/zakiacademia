@echo off
chcp 65001 >nul
REM =====================================================================
REM  Lance les 5 backtests de l'EA FTMO_TrendBreakout l'un apres l'autre.
REM  1) FERMEZ MetaTrader 5 avant de lancer ce fichier.
REM  2) Modifiez les 2 lignes ci-dessous si besoin :
REM     MT5  = le programme terminal64.exe de votre MT5 FTMO
REM     DATA = le dossier ouvert par "Fichier > Ouvrir le dossier des donnees"
REM =====================================================================
set "MT5=C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
set "DATA=COLLEZ_ICI_LE_DOSSIER_DES_DONNEES"

if not exist "%MT5%" (
  echo MT5 introuvable : "%MT5%"
  echo Clic droit sur le raccourci MetaTrader 5 ^> Proprietes ^> Cible, et copiez le chemin dans ce fichier.
  pause & exit /b 1
)
if not exist "%DATA%\MQL5\Experts\FTMO_TrendBreakout.ex5" (
  echo EA introuvable : "%DATA%\MQL5\Experts\FTMO_TrendBreakout.ex5"
  echo Verifiez DATA et compilez l'EA dans MetaEditor sous le nom FTMO_TrendBreakout.
  pause & exit /b 1
)

if not exist "%DATA%\MQL5\Profiles\Tester" mkdir "%DATA%\MQL5\Profiles\Tester"
copy /Y "%~dp0*.set" "%DATA%\MQL5\Profiles\Tester\" >nul
if not exist "%DATA%\za_reports" mkdir "%DATA%\za_reports"

for %%F in ("%~dp0za_*.ini") do (
  echo.
  echo === Test %%~nF en cours... ^(MT5 va s'ouvrir puis se fermer tout seul^)
  start "" /wait "%MT5%" /config:"%%~fF"
)

echo.
echo Termine. Les rapports sont dans : %DATA%\za_reports
start "" "%DATA%\za_reports"
pause
