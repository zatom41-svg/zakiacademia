"""
Simulateur de challenge FTMO (2-Step, phase 1) : quelle chance de valider
en moins de 30 jours, et quelle chance d'échouer, selon le risque par trade ?

Règles simulées (comme l'EA FTMO_TrendBreakout) :
  - objectif +10 %, perte max -10 % (statique), perte journalière -5 %
  - l'EA coupe la journée à -4 % et s'arrête dès l'objectif atteint
  - au moins 4 jours de trading
  - 22 jours de bourse dans 30 jours calendaires

Deux façons de l'utiliser :
  1. Sans données : on suppose un « avantage » (taux de réussite, gain moyen en R)
       python mt5/ftmo_sim.py
  2. Avec VOS résultats de backtest MT5 : un fichier texte avec un résultat
     par ligne, en multiples de R (ex. 2.4, -1, -1, 0, 3.1 ...)
       python mt5/ftmo_sim.py --trades mes_trades_R.txt
"""

import argparse

import numpy as np

rng = np.random.default_rng(7)
N = 20_000


def simulate(draw_r, risk_pct, trades_per_day=1.0, days=22, target=10.0, max_loss=10.0,
             daily_cut=4.0, daily_limit=5.0, max_trades_day=3, min_days=4):
    passed = failed = 0
    days_to_pass = []
    for _ in range(N):
        bal = 100.0
        traded_days = 0
        done = False
        for d in range(days):
            day_start = bal
            n = min(rng.poisson(trades_per_day), max_trades_day)
            if n:
                traded_days += 1
            for _ in range(n):
                bal += bal * risk_pct / 100 * draw_r()
                if bal <= 100 - max_loss or bal <= day_start - daily_limit:
                    failed += 1
                    done = True
                    break
                if bal >= 100 + target and traded_days >= min_days:
                    passed += 1
                    days_to_pass.append(d + 1)
                    done = True
                    break
                if bal <= day_start - daily_cut:  # l'EA coupe la journée
                    break
            if done:
                break
    med = float(np.median(days_to_pass)) if days_to_pass else float("nan")
    return passed / N * 100, failed / N * 100, med


def edge_sampler(winrate, avg_win_r, be_rate=0.10):
    """Tirage d'un trade : gain de avg_win_r R, perte de 1 R, ou break-even."""
    def draw():
        u = rng.random()
        if u < winrate:
            return rng.exponential(avg_win_r)  # gains variables, moyenne avg_win_r
        if u < winrate + be_rate:
            return 0.0
        return -1.0
    return draw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", help="fichier de résultats en R (un par ligne)")
    ap.add_argument("--per-day", type=float, default=1.0, help="trades par jour en moyenne")
    args = ap.parse_args()

    scenarios = []
    if args.trades:
        rs = np.loadtxt(args.trades)
        scenarios.append((f"Vos trades ({len(rs)}, moyenne {rs.mean():+.2f} R)", lambda: rng.choice(rs)))
    else:
        scenarios += [
            ("Aucun avantage (espérance 0)", edge_sampler(0.30, 2.0)),
            ("Petit avantage (+0,15 R/trade)", edge_sampler(0.33, 2.18)),
            ("Bon avantage (+0,35 R/trade)", edge_sampler(0.38, 2.29)),
        ]

    print(f"{'Scénario':40s} {'Risque':>7s} {'Réussi <30 j':>13s} {'Échoué':>8s} {'En cours':>9s} {'Jours médian':>13s}")
    for name, draw in scenarios:
        for risk in [0.5, 1.0, 1.5, 2.0, 3.0]:
            ok, ko, med = simulate(draw, risk, args.per_day)
            print(f"{name:40s} {risk:6.1f}% {ok:12.1f}% {ko:7.1f}% {100 - ok - ko:8.1f}% {med:13.0f}")
        print()


if __name__ == "__main__":
    main()
