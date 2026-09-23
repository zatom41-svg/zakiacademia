# Bots crypto Freqtrade (faux wallet)

5 stratégies, un panel multi-bots en **dry-run** (faux wallet de 1 000 USDT, aucun ordre réel) et les outils de test utilisés pour les choisir.

## Stratégies

| Stratégie | Famille | Unité de temps | Verdict des tests |
|---|---|---|---|
| **TrendRegime** | Momentum 30 j + filtre de régime BTC + taille selon la volatilité, long uniquement | 1j | ✅ Gagnante sur les deux périodes, à tous les leviers |
| SupertrendTrend | Suivi de tendance Supertrend | 4h | ⚠️ Perd en 2022-2024, gagne en 2025-2026 : instable |
| MeanReversionBB | Retour à la moyenne (Bollinger + RSI) | 1h | ➖ Quasi neutre, trop peu de trades |
| MomentumTrend | Cassure Donchian 4h long/short | 4h | ❌ Perd : trop de faux signaux et de frais |
| SqueezeBreakout | Cassure après compression | 1h | ❌ Ruine le compte : des milliers de trades, les frais mangent tout |

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

Le tableau complet (5 stratégies × 6 leviers) est dans `results/summary.json` et dans le panel.

**Ce que ça montre sur le levier :**
- Jusqu'à x3, le levier augmente le gain sans trop détériorer le risque.
- Au-delà de x5, la pire baisse dépasse −40 % et les liquidations s'accumulent.
- À x20, chaque position ne risque que sa petite marge (marge isolée). Ça devient une loterie : très gros gains possibles, baisses de −70 % à −77 %.
- Aucun réglage testé ne fait x100 en 6 mois sur la période de validation.

Limites : le coût du financement (funding) n'est compté que sur les 3 derniers mois (OKX ne donne pas plus d'historique), ce qui flatte un peu les positions longues. Un backtest n'est jamais une promesse.

## Lancer le panel en faux wallet (sur votre PC)

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux).

```bash
cd freqtrade
docker compose up -d
```

5 bots démarrent en faux wallet :

| Bot | Stratégie | Levier | Adresse |
|---|---|---|---|
| za-trendregime-x2 | TrendRegime | x2 | http://localhost:8081 |
| za-trendregime-x5 | TrendRegime | x5 | http://localhost:8082 |
| za-supertrend-x3 | SupertrendTrend | x3 | http://localhost:8083 |
| za-momentum-x3 | MomentumTrend | x3 | http://localhost:8084 |
| za-meanrev-x3 | MeanReversionBB | x3 | http://localhost:8085 |

Ouvrez **http://localhost:8081** (FreqUI). Identifiant `zaki`, mot de passe `CHANGEZ-MOI`. Ensuite, dans FreqUI : **icône robot → Add new bot** avec les adresses 8082 à 8085 pour tout voir dans un seul panel.

Changez le mot de passe et `jwt_secret_key` dans `user_data/config.json` avant de lancer.

Pour changer le levier d'un bot : modifiez `za_leverage` dans `user_data/bots/<bot>.json` puis `docker compose restart <bot>`.

## Refaire les tests

```bash
pip install freqtrade
freqtrade download-data --userdir user_data -c user_data/config.json --timeframes 1h 4h 1d --timerange 20210101-
python tools/run_matrix.py                    # grille stratégies x leviers x périodes
python tools/explore.py                       # exploration rapide de dizaines de variantes
python tools/build_panel.py                   # régénère ../panel/index.html
freqtrade hyperopt --userdir user_data -c user_data/config.json --strategy TrendRegime \
  --hyperopt-loss SharpeHyperOptLoss --timerange 20220101-20250101 -e 200
```

## Passer en réel (plus tard, et seulement si le faux wallet tient 3 mois)

1. Créez une clé API sur votre plateforme (agréée MiCA) **sans droit de retrait**, limitée à votre IP.
2. Mettez-la dans un fichier `user_data/config.private.json` (ignoré par git), jamais dans `config.json`.
3. Passez `"dry_run": false` et commencez petit, à x1 ou x2.
