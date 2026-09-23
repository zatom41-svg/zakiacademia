# zakiacademia

Laboratoire de trading automatisé : bots crypto en faux wallet, EA MetaTrader 5 pour les challenges FTMO et un panel pour tester l'effet du levier.

| Dossier | Contenu |
|---|---|
| [`panel/`](panel/) | **Labo Levier Crypto** : page web autonome. Choisissez une stratégie, un levier de x1 à x50 et une période, et voyez ce que devient un wallet de 1 000 €. Ouvrez `panel/index.html` dans un navigateur. |
| [`freqtrade/`](freqtrade/) | 5 stratégies Freqtrade, panel multi-bots en dry-run (Docker), outils de backtest et d'optimisation. |
| [`mt5/`](mt5/) | EA `FTMO_TrendBreakout.mq5` : suivi de tendance avec protections FTMO (perte journalière, perte max, arrêt à l'objectif). |
| [`docs/`](docs/) | Rapport de recherche : bots open source, IA et Claude, prop firms, rentabilité réelle. |

## En bref

- **Meilleure stratégie trouvée :** `TrendRegime` (momentum 30 jours + filtre de régime BTC). Elle gagne sur 2022-2024 **et** sur 2025-2026, une période jamais utilisée pour la régler.
- **Le levier :** x2-x3 améliore le résultat, x10 et plus multiplie les liquidations et les baisses de −70 %.
- **Aucune configuration testée n'a fait x100 en 6 mois.**
- Tout tourne en **faux wallet**. Aucun ordre réel n'est envoyé tant que vous ne mettez pas vous-même `dry_run: false` et une clé API.

*Ceci n'est pas un conseil en investissement. Les performances passées ne préjugent pas des performances futures.*
