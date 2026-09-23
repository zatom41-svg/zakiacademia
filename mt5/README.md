# EA MT5 « FTMO_TrendBreakout »

Un robot MetaTrader 5 de **suivi de tendance / cassure**, avec les règles FTMO codées en dur pour ne jamais les dépasser.

## Ce que fait le robot

| Élément | Réglage par défaut |
|---|---|
| Unité de temps | H1 |
| Entrée | Cassure du plus haut (ou plus bas) des 20 dernières bougies, dans le sens de l'EMA 200 |
| Stop initial | 2 × ATR(14) |
| Gestion | Break-even à +1R, puis stop suiveur à 3 × ATR |
| Risque | 1 % du solde par trade (la taille en lots est calculée automatiquement) |
| Trades max | 3 par jour et par symbole |
| Horaires | Entrées de 8 h à 20 h (heure serveur), fermeture le vendredi à 20 h |

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

1. **Testeur de stratégie** (Ctrl+R) : modèle « Chaque tick basé sur des ticks réels », au moins 2 ans d'historique, sur chaque symbole visé.
2. **Optimisation :** faites varier `InpBreakoutBars` (10-55), `InpSlAtrMult` (1,5-3), `InpTrailAtrMult` (2-4), en optimisation génétique. Gardez 6 mois d'historique à part pour vérifier (onglet « Forward »). Un réglage qui ne tient pas sur la période forward est à jeter.
3. **Compte démo FTMO** (Free Trial) pendant 2 à 4 semaines.

## « Valider en moins d'un mois »

FTMO n'a plus de limite de temps, mais il faut au moins 4 jours de trading. Avec 1 % de risque par trade, +10 % représente environ 10 trades gagnants nets de plus que les perdants. En un mois sur H1, c'est possible **si** la tendance est au rendez-vous. Ce n'est jamais garanti.

Monter le risque à 2 % double la vitesse, mais aussi le risque de toucher −5 % dans la journée. Ne dépassez pas 1 à 1,5 %. Gagner vite est justement ce qui fait échouer la majorité des challenges (seulement ~14 % de réussite dans l'industrie).

## Règles FTMO à respecter

- Votre propre EA est autorisé. Un EA acheté et utilisé par beaucoup de traders peut entraîner un refus.
- Interdit : HFT, arbitrage de latence, tick scalping, couverture entre comptes, plus de 2 000 requêtes serveur par jour. Cet EA en fait une poignée par jour.
- Évitez de garder des positions pendant les grosses annonces sur un compte financé.
