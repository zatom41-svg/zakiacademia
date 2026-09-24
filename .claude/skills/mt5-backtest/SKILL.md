---
name: mt5-backtest
description: Backteste les stratégies de l'EA FTMO_TrendBreakout sur les vraies cotations du MetaTrader 5 installé sur ce PC Windows. À utiliser quand l'utilisateur demande de backtester, tester un actif, trouver des réglages pour FTMO, exporter l'historique MT5, lire un rapport du testeur MT5 ou simuler un challenge FTMO. Lecture de données et tests uniquement, jamais d'ordres réels.
---

# Backtests MT5 pour le challenge FTMO

Ce skill tourne **sur le PC Windows de l'utilisateur**, où MetaTrader 5 est installé. Il utilise le paquet Python officiel `MetaTrader5` pour lire l'historique du terminal, puis le laboratoire `mt5/lab_ftmo.py` du dépôt pour tester toutes les stratégies.

## Règle absolue

**Ne jamais passer, modifier ou fermer un ordre.** N'appelle jamais `order_send`, `order_check` ni aucune fonction de trading du paquet `MetaTrader5`. Ce skill ne fait que lire l'historique, lancer des backtests et lire des rapports. Si l'utilisateur demande de trader, refuse et explique qu'il doit le faire lui-même.

Réponds toujours en **français**, simplement : l'utilisateur débute.

## Étape 0 : préparer Python (une seule fois)

```powershell
python --version
python -m pip install MetaTrader5 pandas numpy
```

Si `python` n'existe pas, demande à l'utilisateur d'installer Python 3.11 ou plus récent depuis https://www.python.org/downloads/, en cochant **« Add python.exe to PATH »**.

MetaTrader 5 doit être **ouvert et connecté** au compte FTMO (démo ou challenge) pendant l'export.

## Étape 1 : exporter l'historique H1 de MT5

```powershell
python .claude/skills/mt5-backtest/scripts/export_mt5.py --out mt5/data/ftmo --from 2023-01-01
```

- Le script essaie 21 symboles FTMO (or, indices `.cash`, forex, pétrole, BTC, ETH). Ceux qui n'existent pas chez le courtier sont ignorés.
- Il écrit un CSV par symbole (`<symbole>_H1.csv`, colonne `time_server` = heure du serveur FTMO).
- Si `initialize()` échoue : MT5 est fermé, ou plusieurs MT5 sont installés. Passe alors `--terminal "C:\Program Files\MetaTrader 5\terminal64.exe"`.

## Étape 2 : lancer le laboratoire

```powershell
python mt5/lab_ftmo.py --data mt5/data/ftmo --out mt5/results_ftmo
```

Il faut quelques minutes. Il affiche :
1. les couples stratégie × actif **choisis sur 2023-2024** (facteur de profit > 1,15, au moins 40 trades) et leur résultat sur 2025-2026 ;
2. le portefeuille (trades par jour, facteur de profit, espérance en R) ;
3. le challenge FTMO simulé avec un départ chaque jour de 2025-2026 : réussite et échec à 14 jours, 30 jours, à terme, et la phase 2, selon le risque par trade.

Les fichiers `mt5/results_ftmo/strategies_par_actif.csv` et `challenge.json` gardent le détail.

**Honnêteté des résultats :** ne change jamais le critère de sélection en regardant 2025-2026. Si on trie selon la période de validation, les chiffres deviennent trop beaux et faux. Signale-le à l'utilisateur si il le demande.

## Étape 3 (facultative) : vérifier dans le testeur MT5

Pour confirmer un réglage dans le vrai testeur :

1. Vérifie que l'EA compilé existe : `%APPDATA%\MetaQuotes\Terminal\<id>\MQL5\Experts\FTMO_TrendBreakout.ex5`. Sinon, demande à l'utilisateur de compiler `mt5/FTMO_TrendBreakout.mq5` dans MetaEditor (F7).
2. **MT5 doit être fermé**, puis lance `mt5\tests_auto\lancer_les_tests.bat`. Ou lance un seul test :
   ```powershell
   Start-Process -Wait "C:\Program Files\MetaTrader 5\terminal64.exe" -ArgumentList '/config:"C:\chemin\vers\mt5\tests_auto\za_01_xauusd_cassure.ini"'
   ```
   Le premier lancement télécharge l'historique et peut être long sans rien afficher.
3. Lis les rapports produits dans `<dossier des données>\za_reports\*.htm` :
   ```powershell
   python .claude/skills/mt5-backtest/scripts/parse_report.py "<dossier des données>\za_reports"
   ```

Pour un nouveau réglage, copie un fichier `mt5/tests_auto/za_*.set` + `.ini`, change les valeurs, et garde `Model=2` (rapide) ou `Model=1` (plus précis).

## Étape 4 : répondre à l'utilisateur

Résume en quelques lignes, en français simple :
- les actifs et stratégies retenus, avec leur résultat 2025-2026 ;
- le nombre de trades par jour ;
- les chances de réussir le challenge en 14 jours, 30 jours et à terme, au risque recommandé (en général 1 %) ;
- les réglages à mettre dans l'EA pour chaque graphique (voir le tableau de `mt5/README.md`).

Ne promets jamais de résultat : ce sont des tests sur le passé.
