# Bot crypto TrendRegime (Freqtrade, faux wallet)

Un seul bot, une seule stratégie, choisie parce qu'elle ne perd aucune année de 2022 à 2026.

## La stratégie en 3 règles

Chaque jour, à la clôture (minuit UTC), pour chacune des 8 cryptos (BTC, ETH, SOL, BNB, XRP, DOGE, AVAX, LINK) :

1. **Filtre de marché :** le BTC doit être au-dessus de sa moyenne des 200 derniers jours. Sinon, le bot vend tout et reste en dollars.
2. **Tendance de la crypto :** elle doit avoir monté sur les 30 derniers jours. Sinon, le bot la vend.
3. **Taille :** chaque crypto reçoit au plus 1/8 du capital, moins si elle est très agitée (cible de volatilité 0,5).

L'achat ou la vente se fait à l'ouverture du lendemain. Fichier : `user_data/strategies/TrendRegime.py`.

## Résultats Freqtrade, année par année

Moteur réel de Freqtrade, futures OKX, 1 000 USDT de départ, frais et financement inclus. Chaque ligne repart de 1 000 USDT.

| Année | x1 | x2 | x3 |
|---|---|---|---|
| 2022 | 0 % (bot hors marché : bear market) | 0 % | 0 % |
| 2023 | +84 % | +164 % | +242 % |
| 2024 | +35 % | +66 % | +88 % |
| 2025 | +6 % | +6 % | +4 % |
| 2026 (1er janv. → 23 sept.) | +17 % | +35 % | +52 % |
| **Tout (2022 → 23/09/2026)** | **+206 %** | **+555 %** | **+1 039 %** |
| Pire baisse sur la période | −13 % | −26 % | −38 % |
| Liquidations | 0 | 0 | 0 |

**Levier recommandé : x2.** Au-delà de x3, les baisses dépassent −40 % et des années deviennent perdantes. Le détail jour par jour est dans le panel (`../panel/index.html`).

## Comment les réglages ont été choisis

`tools/optimize_robust.py` a testé 105 combinaisons (momentum de 10 à 90 jours, moyenne BTC de 0 à 200 jours, trois tailles). Le critère de choix n'était pas le meilleur gain total, mais la **régularité année par année**. Les 10 meilleurs réglages utilisent tous la moyenne BTC de 200 jours.

**Test walk-forward :** chaque année de 2023 à 2026 est jouée avec des réglages choisis **uniquement sur les années précédentes**. Résultat : **+141 %** de 2023 à 2026 à x1, avec une pire baisse de −22 %. C'est l'estimation la plus honnête de ce qu'on peut attendre.

**Ce qui a été testé et écarté** (fichiers dans `user_data/strategies/archive/`) :
- Momentum 4h, Squeeze 1h, Bollinger 1h : perdants, les frais mangent tout.
- Supertrend, Donchian journalier, DipReversion : instables ou trop faibles.
- Hyperopt « au meilleur Sharpe » : excellent sur 2022-2024, mais −10 % sur 2025-2026 (sur-optimisation).
- Pauses automatiques après des pertes : elles bloquaient le bot des semaines entières (2024 : −2 % au lieu de +35 %).

## Chances en 6 mois (Monte Carlo, `tools/montecarlo.py`)

| Levier | Doubler | x10 | x100 | Perdre la moitié | Ruine |
|---|---|---|---|---|---|
| x1 | 1 % | 0 % | 0 % | 0 % | 0 % |
| x2 | 14 % | 0 % | 0 % | 0,2 % | 0 % |
| x3 | 28 % | 0,2 % | 0 % | 3 % | 0 % |
| x5 | 41 % | 3 % | < 0,1 % | 14 % | 0 % |
| x10 | 48 % | 10 % | 0,6 % | 49 % | 6 % |
| x20 | 48 % | 13 % | 1,2 % | 84 % | 57 % |

## Lancer les 3 bots en faux wallet

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/).

1. Dans `user_data/config.json`, changez `password` et `jwt_secret_key`.
2. Lancez :

   ```bash
   cd freqtrade
   docker compose up -d
   ```

| Bot | Levier | Adresse |
|---|---|---|
| za-trendregime-x1 | x1 | http://localhost:8081 |
| za-trendregime-x2 | x2 | http://localhost:8082 |
| za-trendregime-x3 | x3 | http://localhost:8083 |

3. Ouvrez http://localhost:8081 (identifiant `zaki`), puis dans FreqUI : **icône robot → Add new bot** avec 8082 et 8083. Vous verrez les 3 faux wallets côte à côte.

## Refaire les tests

```bash
pip install freqtrade
freqtrade download-data --userdir user_data -c user_data/config.json --timeframes 1h 1d --timerange 20210101-
python tools/run_matrix.py          # Freqtrade année par année, x1 / x2 / x3 / x5
python tools/optimize_robust.py     # optimisation robuste + walk-forward
python tools/montecarlo.py          # chances en 6 mois
python tools/build_panel.py         # régénère ../panel/index.html
```

## Passer en réel (seulement après 3 mois de faux wallet concluants)

1. Créez une clé API OKX (plateforme agréée MiCA) **sans droit de retrait**, limitée à votre IP.
2. Mettez-la dans `user_data/config.private.json` (ignoré par git).
3. Passez `"dry_run": false` et commencez petit, à x1.
