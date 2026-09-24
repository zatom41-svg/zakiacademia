# zakiacademia

Laboratoire de trading automatisé.

| Dossier | Contenu |
|---|---|
| [`panel/`](panel/) | **Labo Levier Crypto** : ouvrez `panel/index.html` dans un navigateur. Choisissez des dates précises (ou 7 jours, 30 jours, 2026…) et un levier, et voyez le faux wallet évoluer jour par jour. |
| [`freqtrade/`](freqtrade/) | Le bot crypto **TrendRegime** et 3 faux wallets prêts à lancer avec Docker (x1, x2, x3). |
| [`mt5/`](mt5/) | EA MetaTrader 5 `FTMO_TrendBreakout.mq5` avec les protections FTMO, et un simulateur de challenge. |
| [`docs/`](docs/) | Rapport de recherche : bots open source, IA et Claude, prop firms, rentabilité réelle. |

## Backtests MT5 faits par Claude Code sur votre PC

Le dépôt contient un skill Claude Code, `.claude/skills/mt5-backtest`. Lancez Claude Code dans ce dossier, sur le PC Windows où MT5 est installé, puis demandez par exemple « backteste tous les actifs FTMO ». Claude exporte l'historique de votre MT5, lance le laboratoire `mt5/lab_ftmo.py` et vous résume les résultats. Il ne passe jamais d'ordres.

## En bref

- **Une stratégie :** acheter les cryptos qui montent depuis 30 jours, seulement quand le BTC est au-dessus de sa moyenne 200 jours.
- **Résultats (Freqtrade, levier x2, 1 000 € de départ) :** 0 % en 2022 (hors marché pendant le krach), +164 % en 2023, +66 % en 2024, +6 % en 2025, +35 % en 2026 (au 23 septembre). **Aucune année perdante.**
- **Levier conseillé : x2.** À partir de x5, des années deviennent perdantes. À x10 et plus, le wallet peut être détruit.
- **x100 en 6 mois :** environ 1 chance sur 100, avec plus d'une chance sur deux de perdre la moitié.
- Tout tourne en **faux wallet**. Aucun ordre réel n'est envoyé tant que vous ne mettez pas vous-même une clé API.

*Ceci n'est pas un conseil en investissement. Les performances passées ne préjugent pas des performances futures.*
