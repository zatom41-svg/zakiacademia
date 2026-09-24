# EA MT5 « FTMO_TrendBreakout » (v1.30)

Un robot MetaTrader 5 avec **deux stratégies au choix** et les règles FTMO codées en dur pour ne jamais les dépasser. On le pose sur **6 graphiques** (un par réglage) pour faire environ **2 trades par jour** au total.

## Bot OR (v1.30) : 2 graphiques XAUUSD

Trouvé par `gold_lab.py` : 6 familles de stratégies testées sur l'or (PAXG H1, 2021 → sept. 2026). Choix sur 2021-2023, vérification sur 2024-2026. La cassure H1 (ancien réglage) **perd** : −7,9 % en 2024 dans votre testeur MT5.

| Graphique | Réglages |
|---|---|
| **XAUUSD H1 : achat de creux** | `InpMode = 1` (RSI2), `InpRsiLevel = 10`, `InpSlAtrMult = 2.0`, `InpRsiTpAtr = 0`, `InpRsiExitSma = 5`, `InpRsiMaxBars = 6`, `InpAllowShort = false`, `InpStartHour = 0`, `InpEndHour = 24`, `InpMaxTradesPerDay = 10`, `InpCloseBeforeWeekend = false`, `InpMagic = 11` |
| **XAUUSD D1 : tendance** | `InpMode = 2` (Tendance), `InpTimeframe = D1`, `InpTrendSma = 50`, `InpSlAtrMult = 3.0`, `InpAllowShort = false`, `InpCloseBeforeWeekend = false`, `InpMagic = 12` |

Les deux avec `InpRiskPercent = 1.0`. Résultats du backtest Python (les deux ensemble) :

| Année | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (sept.) |
|---|---|---|---|---|---|---|
| Résultat | +12 % | **−7 %** | +18 % | +26 % | +24 % | 0 % |
| Pire baisse | −2 % | −12 % | −3 % | −3 % | −11 % | −8 % |

- **Rentable 5 années sur 6**, mais **lent** : environ 0,7 trade par jour. Simulation FTMO : 4 % de réussite en moins de 30 jours à 1 % de risque.
- **Plutôt un bot d'investissement** sur l'or qu'un outil pour passer un challenge vite.
- Le mode Tendance ne fait que 7 trades par an. Il profite surtout des années de forte hausse de l'or (2024, 2025).

Vérifiez dans le testeur MT5 (« OHLC sur M1 ») année par année, surtout 2022.

## Le portefeuille recommandé : 6 graphiques

Chaque ligne = un graphique MT5 en **H1** avec l'EA, un **numéro magique différent**, et `InpRiskPercent = 1.0`.

| Graphique | `InpMode` | Réglages à changer | Autres |
|---|---|---|---|
| XAUUSD | Cassure | `InpBreakoutBars = 20`, `InpSlAtrMult = 3.0` | `InpMagic = 1` |
| XAUUSD | RSI(2) | `InpRsiLevel = 5`, `InpSlAtrMult = 3.0`, `InpEndHour = 21` | `InpMagic = 2` |
| US100.cash | Cassure | `InpBreakoutBars = 55`, `InpSlAtrMult = 3.0` | `InpMagic = 3` |
| US100.cash | RSI(2) | `InpRsiLevel = 5`, `InpSlAtrMult = 3.0`, `InpEndHour = 21` | `InpMagic = 4` |
| BTCUSD | Cassure | `InpBreakoutBars = 55`, `InpSlAtrMult = 2.0` | `InpMagic = 5`, `InpCloseBeforeWeekend = false` |
| ETHUSD | Cassure | `InpBreakoutBars = 55`, `InpSlAtrMult = 3.0` | `InpMagic = 6`, `InpCloseBeforeWeekend = false` |

Pour tous : `InpInitialBalance` = la taille du compte (ex. 100000), `InpTrailAtrMult = 3.0`, `InpProfitTargetPct = 10` (phase 1) puis `5` (phase 2).

## Comment ces réglages ont été choisis (`lab_ftmo.py`)

- **Actifs testés** en bougies horaires, de janvier 2023 à septembre 2026 : or (PAXG, qui suit XAUUSD), Nasdaq 100 (QQQ, pour US100), EURUSD, BTC, ETH, SOL et XRP.
- **4 familles de stratégies testées sur chaque actif, avec 3 à 6 réglages chacune** :
  - cassure de tendance ;
  - cassure du range d'ouverture de session ;
  - cassure du plus haut / plus bas de la veille ;
  - retour à la moyenne RSI(2).
- **Coûts FTMO inclus** : spread, commission et glissement.
- **Choix uniquement sur 2023-2024** (facteur de profit > 1,15, au moins 40 trades), puis **vérification sur 2025-2026**, une période jamais utilisée pour choisir. 6 couples ont été retenus.
- **Écartés :** aucune stratégie ne marche sur EURUSD, SOL et XRP, ni la cassure d'ouverture de session et du plus haut de la veille. Le RSI(2) sur US100 a été retenu sur 2023-2024 mais **perd en 2025-2026** : vous pouvez ne pas l'activer.

**Portefeuille en validation (2025-2026) :** 751 trades, **1,9 trade par jour de bourse**, facteur de profit 1,33, espérance +0,13 R par trade.

**Challenge FTMO simulé** : un challenge démarré **chaque jour** de 2025-2026 (377 départs). Limite journalière comptée avec les pertes en cours.

| Risque par trade | Réussi en ≤ 14 j | Échoué en ≤ 14 j | Réussi en ≤ 30 j | Échoué en ≤ 30 j | **Réussi à terme** | Échoué à terme | Phase 2 réussie |
|---|---|---|---|---|---|---|---|
| 0,5 % | 3 % | 0 % | 12 % | 0 % | 65 % | 5 % | 86 % |
| 0,75 % | 10 % | 0 % | 24 % | 1 % | 69 % | 17 % | 84 % |
| **1 %** | **18 %** | **1 %** | **36 %** | **11 %** | **76 %** | **23 %** | **78 %** |
| 1,5 % | 28 % | 15 % | 47 % | 29 % | 67 % | 33 % | 70 % |
| 2 % | 30 % | 40 % | 44 % | 51 % | 49 % | 51 % | 57 % |

**Ce qu'il faut en retenir :**
- **Réussir en 2 semaines** n'arrive que dans **1 cas sur 5 à 1 cas sur 3**, quel que soit le risque.
- **Monter le risque ne donne presque rien de plus sur les 14 premiers jours** (18 % → 30 %), mais fait exploser les échecs (1 % → 40 %).
- **Le meilleur réglage est 1 % par trade :** 3 challenges sur 4 réussis si on laisse le temps (FTMO n'a pas de limite), dont 1 sur 5 en moins de 2 semaines.

Limites : l'or, le Nasdaq et les cryptos sont testés sur des marchés proches de ceux de FTMO (PAXG, QQQ, futures OKX), pas sur les cotations FTMO elles-mêmes. Vérifiez chaque graphique dans le testeur MT5 avant de payer un challenge.

**Protections FTMO (Challenge 2-Step) :**
- **Perte journalière :** coupure à **−4 %** du capital initial depuis le solde de début de journée (limite FTMO : −5 %). Le robot ferme tout et attend le lendemain.
- **Perte maximale :** coupure définitive à **−9 %** (limite FTMO : −10 %).
- **Objectif :** une fois **+10 %** atteint, le robot ferme tout et s'arrête. Pour la phase 2, mettez `InpProfitTargetPct = 5`.

Le tableau de bord (en haut à gauche du graphique) affiche l'equity, le résultat du jour et l'objectif.

## Tout tester automatiquement (kit `tests_auto/`)

1. **Compilez l'EA** sous le nom exact `FTMO_TrendBreakout` (dans MQL5\Experts).
2. Extrayez le kit (clic droit sur le zip → **Extraire tout**). Laissez `lancer_les_tests.bat` dans le dossier `tests_auto`, avec les fichiers `.ini` et `.set`. Il n'y a rien à modifier : le fichier trouve tout seul MT5 et l'EA, et vous demande le chemin seulement s'il ne le trouve pas.
3. **Fermez MT5**, puis double-cliquez sur `lancer_les_tests.bat`. Les 5 backtests (or cassure, or RSI(2), US100, BTC, ETH) s'enchaînent en mode rapide « Prix d'ouverture uniquement » (quelques secondes par test) du 01/01/2023 au 20/09/2026, et les rapports arrivent dans `DATA\za_reports`.
4. Envoyez-moi les rapports (fichiers .htm) : je compare avec mes résultats et j'ajuste.

## Exporter l'historique FTMO pour mes tests

Copiez `ZA_ExportHistory.mq5` dans MQL5\Scripts, compilez-le, puis glissez-le sur n'importe quel graphique. Il exporte l'historique H1 de 21 actifs FTMO dans `MQL5\Files\za_export`. Envoyez-moi ces CSV : `lab_ftmo.py` les lit directement et je pourrai tester tous les actifs sur les vraies cotations FTMO.

## Installation

1. Dans MT5 : **Fichier → Ouvrir le dossier des données → MQL5 → Experts**, puis copiez-y `FTMO_TrendBreakout.mq5`.
2. Ouvrez-le dans **MetaEditor** (F4) et compilez (F7). Il ne doit y avoir aucune erreur.
3. Glissez l'EA sur un graphique (XAUUSD, US30, NAS100, EURUSD…), cochez **Autoriser le trading algorithmique**.
4. Mettez `InpInitialBalance` = la taille de votre compte FTMO (ex. 100000).

> Je n'ai pas pu compiler ce fichier ici (MetaEditor n'existe que sous Windows). S'il y a une erreur de compilation, copiez-la-moi et je la corrige.

## Tester AVANT le challenge (obligatoire)

1. **Testeur de stratégie** (Ctrl+R) : modèle **« OHLC sur M1 »** (rapide et suffisant pour un EA en H1), dates 2022.01.01 → aujourd'hui, `InpStopAtTarget = false` et `InpProfitTargetPct = 0` pour tester sur plusieurs années. Évitez « Chaque tick basé sur des ticks réels » : sur FTMO, les ticks réels ne commencent qu'en février 2024 et le test devient très long.
2. **Optimisation :** faites varier `InpBreakoutBars` (10-55), `InpSlAtrMult` (2-3), `InpTrailAtrMult` (2-4), en optimisation génétique. Gardez 6 mois d'historique à part pour vérifier (onglet « Forward »). Un réglage qui ne tient pas sur la période forward est à jeter.
3. **Compte démo FTMO** (Free Trial) pendant 2 à 4 semaines.

## « Valider en moins d'un mois »

FTMO n'a plus de limite de temps, mais il faut au moins 4 jours de trading. Avec 1 % de risque par trade, +10 % représente environ 10 trades gagnants nets de plus que les perdants. En un mois sur H1, c'est possible **si** la tendance est au rendez-vous. Ce n'est jamais garanti.

Monter le risque à 2 % double la vitesse, mais aussi le risque de toucher −5 % dans la journée. Ne dépassez pas 1 à 1,5 %. Gagner vite est justement ce qui fait échouer la majorité des challenges (seulement ~14 % de réussite dans l'industrie).

## Simulateur de challenge

`ftmo_sim.py` estime vos chances de valider la phase 1 (+10 %) en moins de 30 jours, selon le risque par trade (20 000 challenges simulés, 1 trade par jour en moyenne, coupure de l'EA à −4 % par jour) :

| Stratégie | Risque / trade | Réussi en < 30 j | Échoué | Encore en cours |
|---|---|---|---|---|
| Sans avantage (espérance 0) | 1 % | 18 % | 12 % | 71 % |
| Sans avantage | 2 % | 34 % | 48 % | 19 % |
| Petit avantage (+0,15 R/trade) | 1 % | 29 % | 6 % | 64 % |
| Petit avantage | 1,5 % | 42 % | 21 % | 36 % |
| Bon avantage (+0,35 R/trade) | 1 % | 45 % | 3 % | 53 % |
| **Bon avantage** | **1,5 %** | **59 %** | **12 %** | 30 % |
| Bon avantage | 2 % | 62 % | 23 % | 15 % |
| Bon avantage | 3 % | 43 % | 56 % | 1 % |

- **Moins d'un mois** est réaliste avec une stratégie qui a un vrai avantage et **1 à 1,5 %** de risque par trade.
- **Au-delà de 2 %**, on échoue plus souvent qu'on ne réussit.
- **Sans avantage**, on peut réussir par chance, mais on paie beaucoup de challenges.

Avec vos propres résultats de backtest MT5 (un résultat par ligne, en R) :

```bash
pip install numpy
python mt5/ftmo_sim.py --trades mes_trades_R.txt --per-day 1.5
```

## Règles FTMO à respecter

- Votre propre EA est autorisé. Un EA acheté et utilisé par beaucoup de traders peut entraîner un refus.
- Interdit : HFT, arbitrage de latence, tick scalping, couverture entre comptes, plus de 2 000 requêtes serveur par jour. Cet EA en fait une poignée par jour.
- Évitez de garder des positions pendant les grosses annonces sur un compte financé.
