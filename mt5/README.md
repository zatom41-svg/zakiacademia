# EA MT5 « FTMO_TrendBreakout »

Un robot MetaTrader 5 de **suivi de tendance / cassure**, avec les règles FTMO codées en dur pour ne jamais les dépasser.

## Ce que fait le robot

| Élément | Réglage par défaut (v1.10) |
|---|---|
| Unité de temps | **H4** |
| Entrée | Cassure du plus haut (ou plus bas) des **55** dernières bougies, dans le sens de l'EMA 200 |
| Stop initial | **3** × ATR(14) |
| Gestion | Break-even à +1R, puis stop suiveur à **5** × ATR |
| Risque | 1 % du solde par trade (la taille en lots est calculée automatiquement) |
| Trades max | 3 par jour et par symbole |
| Horaires | Entrées de 8 h à 20 h (heure serveur), fermeture le vendredi à 20 h |

## Résultats du backtest Python (`ea_backtest.py`, or H1/H4 2022 → sept. 2026)

Testé sans MT5 sur l'historique horaire de PAXG (jeton adossé à l'or, qui suit XAUUSD), en heure serveur FTMO, sans les week-ends.

**Ancien réglage (H1, Donchian 20, stop 2 ATR) : perdant.** −9 % au total, pire baisse −41 %, facteur de profit 0,96. Il ne gagnait qu'en 2025. **Ne pas l'utiliser.**

**Nouveau réglage (H4, Donchian 55, stop 3 ATR, suiveur 5 ATR), risque 1 % :**

| Année | Résultat | Pire baisse | Trades | Facteur de profit |
|---|---|---|---|---|
| 2022 | −2 % | −3 % | 23 | 0,73 |
| 2023 | +1 % | −2 % | 18 | 1,23 |
| 2024 | +5 % | −1 % | 17 | 4,01 |
| 2025 | +6 % | −3 % | 27 | 2,10 |
| 2026 (sept.) | +4 % | −2 % | 16 | 1,88 |

C'est le seul réglage qui reste positif avant **et** après 2025 parmi les 72 testés (unités H1 et H4, cassure 10 à 55, stop 1,5 à 3 ATR, suiveur 3 à 5 ATR). Il perd très peu, mais **il gagne lentement**.

**Challenge FTMO simulé** (un départ le 1er de chaque mois, 56 départs de 2022 à 2026) :

| Risque par trade | Réussi en < 30 jours | Réussi un jour | Échoué | Durée médiane pour réussir |
|---|---|---|---|---|
| 1 % | 0 | 46 | 0 | environ 2 ans |
| 2 % | 0 | 49 | 0 | environ 1 an |
| 3 % | 0 | 50 | 2 | environ 8 mois |

Conclusion : sur l'or seul, cet EA ne fait presque jamais échouer le challenge, mais **il ne le passe pas en moins d'un mois**. Pour aller plus vite sans prendre de gros risques, il faut plus d'occasions de trade : lancez-le **sur plusieurs actifs en même temps** (XAUUSD, US100.cash, US30.cash, EURUSD, GBPUSD), un graphique par actif, avec 0,5 à 1 % de risque chacun. À vérifier dans le testeur MT5 sur chaque actif.

**Protections FTMO (Challenge 2-Step) :**
- **Perte journalière :** coupure à **−4 %** du capital initial depuis le solde de début de journée (limite FTMO : −5 %). Le robot ferme tout et attend le lendemain.
- **Perte maximale :** coupure définitive à **−9 %** (limite FTMO : −10 %).
- **Objectif :** une fois **+10 %** atteint, le robot ferme tout et s'arrête. Pour la phase 2, mettez `InpProfitTargetPct = 5`.

Le tableau de bord (en haut à gauche du graphique) affiche l'equity, le résultat du jour et l'objectif.

## Installation

1. Dans MT5 : **Fichier → Ouvrir le dossier des données → MQL5 → Experts**, puis copiez-y `FTMO_TrendBreakout.mq5`.
2. Ouvrez-le dans **MetaEditor** (F4) et compilez (F7). Il ne doit y avoir aucune erreur.
3. Glissez l'EA sur un graphique (XAUUSD, US30, NAS100, EURUSD…), cochez **Autoriser le trading algorithmique**.
4. Mettez `InpInitialBalance` = la taille de votre compte FTMO (ex. 100000).

> Je n'ai pas pu compiler ce fichier ici (MetaEditor n'existe que sous Windows). S'il y a une erreur de compilation, copiez-la-moi et je la corrige.

## Tester AVANT le challenge (obligatoire)

1. **Testeur de stratégie** (Ctrl+R) : modèle **« OHLC sur M1 »** (rapide et suffisant pour un EA en H4), dates 2022.01.01 → aujourd'hui, `InpStopAtTarget = false` et `InpProfitTargetPct = 0` pour tester sur plusieurs années. Évitez « Chaque tick basé sur des ticks réels » : sur FTMO, les ticks réels ne commencent qu'en février 2024 et le test devient très long.
2. **Optimisation :** faites varier `InpBreakoutBars` (20-100), `InpSlAtrMult` (2-4), `InpTrailAtrMult` (3-6), en optimisation génétique. Gardez 6 mois d'historique à part pour vérifier (onglet « Forward »). Un réglage qui ne tient pas sur la période forward est à jeter.
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
