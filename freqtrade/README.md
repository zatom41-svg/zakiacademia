# Bots crypto Freqtrade (faux wallet)

3 stratégies actives (et 4 archivées), un panel multi-bots en **dry-run** (faux wallet de 1 000 USDT, aucun ordre réel) et les outils de test utilisés pour les choisir.

## Stratégies

**Actives** (dans `user_data/strategies/`) :

| Stratégie | Famille | Unité de temps | Verdict des tests |
|---|---|---|---|
| **TrendRegime** | Momentum 30 j + filtre de régime BTC + taille selon la volatilité, long uniquement | 1j | ✅ Gagnante sur les deux périodes, à tous les leviers |
| **DipReversion** | Achat de creux (RSI 3) dans une tendance haussière, long uniquement | 1j | ✅ Petits gains réguliers, très faibles baisses, peu de trades (44) |
| SupertrendTrend | Suivi de tendance Supertrend long/short | 4h | ⚠️ Perd en 2022-2024, gagne en 2025-2026 : instable |

**Archivées** (dans `user_data/strategies/archive/`, non chargées) : testées puis écartées.

| Stratégie | Pourquoi |
|---|---|
| MomentumTrend (cassure 4h long/short) | −40 à −64 % sur les deux périodes : faux signaux et frais |
| SqueezeBreakout (1h) | −90 à −100 % : des milliers de trades, les frais mangent tout |
| MeanReversionBB (1h) | Quasi neutre, 12 trades en 3 ans |
| DonchianRegime (cassure journalière) | +28 % puis +1 % : l'entrée à l'ouverture suivante perd l'avantage |

Toutes partagent `za_common.py` : levier réglable, taille de position calculée sur le risque, stop suiveur ATR, protections après une série de pertes, et refus d'un trade si le levier ferait liquider **avant** le stop.

## Résultats Freqtrade (OKX futures, 8 paires, 1 000 USDT de départ)

« Apprentissage » = 2022-2024. « Validation » = 2025 → sept. 2026, une période jamais utilisée pour choisir les réglages.

| TrendRegime | Apprentissage | Baisse max | Validation | Baisse max | Liquidations |
|---|---|---|---|---|---|
| x1 | +89 % | −11 % | +12 % | −11 % | 0 |
| x2 | +170 % | −24 % | +38 % | −18 % | 0 |
| x3 | +226 % | −36 % | +53 % | −26 % | 1 |
| x5 | +340 % | −33 % | +48 % | −42 % | 4 |
| x10 | +302 % | −58 % | +23 % | −71 % | 42 |
| x20 | +1 185 % | −71 % | +91 % | −77 % | 82 |

| DipReversion | Apprentissage | Baisse max | Validation | Baisse max | Liquidations |
|---|---|---|---|---|---|
| x1 | +6 % | −3 % | +4 % | −2 % | 0 |
| x2 | +13 % | −5 % | +9 % | −3 % | 0 |
| x3 | +20 % | −8 % | +13 % | −5 % | 0 |
| x5 | +14 % | −16 % | +23 % | −8 % | 3 |

Le tableau complet (toutes les stratégies × 6 leviers) est dans `results/summary.json` et dans le panel.

**Ce que ça montre sur le levier :**
- Jusqu'à x3, le levier augmente le gain sans trop détériorer le risque.
- Au-delà de x5, la pire baisse dépasse −40 % et les liquidations s'accumulent.
- À x20, chaque position ne risque que sa petite marge (marge isolée). Ça devient une loterie : très gros gains possibles, baisses de −70 % à −77 %.
- Aucun réglage testé ne fait x100 en 6 mois sur la période de validation.

## Chances de faire x100 en 6 mois (Monte Carlo)

`tools/montecarlo.py` rejoue 20 000 trajectoires de 6 mois à partir de blocs de 30 jours réels (2022-2026) :

| Stratégie | Levier | x2 | x10 | x100 | Perdre la moitié | Ruine (< 5 % restant) |
|---|---|---|---|---|---|---|
| TrendRegime | x2 | 20 % | < 0,1 % | 0 % | 0,1 % | 0 % |
| TrendRegime | x3 | 34 % | 0,7 % | 0 % | 3 % | 0 % |
| TrendRegime | x5 | 47 % | 6 % | 0,1 % | 17 % | 0,2 % |
| TrendRegime | x10 | 55 % | 15 % | **1,4 %** | 47 % | 9 % |
| TrendRegime | x20 | 43 % | 0,8 % | 0 % | 80 % | 58 % |
| Acheter et garder | x5 | 47 % | 11 % | 0,8 % | 78 % | 52 % |
| Acheter et garder | x10 | 37 % | 5 % | 0,2 % | 99,5 % | 98 % |

La meilleure chance de x100 trouvée est d'environ **1 sur 70**, et elle vient avec **près d'une chance sur deux de perdre la moitié**. Plus de levier ne l'augmente pas : au-delà de x10, les liquidations détruisent le wallet avant qu'il ait le temps de monter.

Limites : le coût du financement (funding) n'est compté que sur les 3 derniers mois (OKX ne donne pas plus d'historique), ce qui flatte un peu les positions longues. Un backtest n'est jamais une promesse.

## Leçon d'optimisation : ne pas croire le meilleur backtest

L'optimisation automatique (`freqtrade hyperopt`, 150 essais, 2022-2024, levier x2) a trouvé pour TrendRegime un réglage qui paraissait meilleur. Sur 2025-2026, jamais vue, il s'effondre :

| Réglage TrendRegime (x2) | 2022-2024 | Baisse max | Sharpe | **2025-2026** | Baisse max |
|---|---|---|---|---|---|
| Base : momentum 30 j, BTC > SMA 100, cible de volatilité 0,5 | +174 % | −24 % | 1,11 | **+38 %** | −18 % |
| « Optimisé » : 15 j, SMA 114, cible 0,21 | +55 % | −6 % | 1,56 | **−10 %** | −18 % |

Le réglage « optimisé » collait trop aux données passées (sur-optimisation). On garde le réglage de base : il vient de la littérature, et les variantes proches (14, 30, 60 jours) donnent toutes des résultats positifs dans `tools/explore.py`. Le bouton « Optimiser » du panel fait le même test : il choisit sur 2022-2024 puis affiche le résultat 2025-2026.

## Lancer le panel en faux wallet (sur votre PC)

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux).

```bash
cd freqtrade
docker compose up -d
```

4 bots démarrent en faux wallet :

| Bot | Stratégie | Levier | Adresse |
|---|---|---|---|
| za-trendregime-x2 | TrendRegime | x2 | http://localhost:8081 |
| za-trendregime-x5 | TrendRegime | x5 | http://localhost:8082 |
| za-dipreversion-x3 | DipReversion | x3 | http://localhost:8083 |
| za-supertrend-x3 | SupertrendTrend | x3 | http://localhost:8084 |

Ouvrez **http://localhost:8081** (FreqUI). Identifiant `zaki`, mot de passe `CHANGEZ-MOI`. Ensuite, dans FreqUI : **icône robot → Add new bot** avec les adresses 8082 à 8084 pour tout voir dans un seul panel.

Changez le mot de passe et `jwt_secret_key` dans `user_data/config.json` avant de lancer.

Pour changer le levier d'un bot : modifiez `za_leverage` dans `user_data/bots/<bot>.json` puis `docker compose restart <bot>`.

## Refaire les tests

```bash
pip install freqtrade
freqtrade download-data --userdir user_data -c user_data/config.json --timeframes 1h 4h 1d --timerange 20210101-
python tools/run_matrix.py                    # grille stratégies x leviers x périodes
python tools/explore.py                       # exploration rapide de dizaines de variantes
python tools/explore2.py                      # rotation et retour à la moyenne
python tools/montecarlo.py                    # chances x2 / x10 / x100 en 6 mois
python tools/build_panel.py                   # régénère ../panel/index.html
freqtrade hyperopt --userdir user_data -c user_data/config.json --strategy TrendRegime \
  --hyperopt-loss SharpeHyperOptLoss --timerange 20220101-20250101 -e 200
```

## Passer en réel (plus tard, et seulement si le faux wallet tient 3 mois)

1. Créez une clé API sur votre plateforme (agréée MiCA) **sans droit de retrait**, limitée à votre IP.
2. Mettez-la dans un fichier `user_data/config.private.json` (ignoré par git), jamais dans `config.json`.
3. Passez `"dry_run": false` et commencez petit, à x1 ou x2.
