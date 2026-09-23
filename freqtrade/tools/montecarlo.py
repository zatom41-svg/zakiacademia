"""
Monte Carlo : quelle est la probabilité de faire x2, x10, x100 en 6 mois,
et de perdre plus de la moitié, selon la stratégie et le levier ?

Méthode : on rejoue 20 000 fois des trajectoires de 180 jours en tirant au
hasard des blocs de 30 jours consécutifs de rendements journaliers réels
(2022 → 2026, moteur de explore.py). Les blocs gardent les séries de hausses
et de krachs telles qu'elles se sont produites.

Usage : python tools/montecarlo.py
"""

import json

import numpy as np
import pandas as pd

from explore import PAIRS, ROOT, load, sig_tsmom, simulate

N_PATHS = 20_000
HORIZON = 180
BLOCK = 30
rng = np.random.default_rng(42)


def paths(daily: np.ndarray) -> np.ndarray:
    n_blocks = HORIZON // BLOCK
    starts = rng.integers(0, len(daily) - BLOCK, size=(N_PATHS, n_blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(N_PATHS, -1)
    r = daily[idx]
    return np.cumprod(1 + r, axis=1)


def summarise(name, lev, eq: pd.Series) -> dict:
    daily = eq.pct_change().dropna().to_numpy()
    daily = daily[daily > -1]  # ruine totale : gérée par le cumprod
    p = paths(daily)
    final = p[:, -1]
    peak_dd = (p / np.maximum.accumulate(p, axis=1) - 1).min(axis=1)
    reached = lambda x: float((p.max(axis=1) >= x).mean() * 100)
    return {
        "strategy": name, "leverage": lev,
        "p_x2_pct": reached(2), "p_x10_pct": reached(10), "p_x100_pct": reached(100),
        "p_loss_half_pct": float((final <= 0.5).mean() * 100),
        "p_ruin_pct": float((final <= 0.05).mean() * 100),
        "median_final_x": float(np.median(final)),
        "median_worst_dd_pct": float(np.median(peak_dd) * 100),
    }


def main():
    data = load("1d")
    btc = data["BTC"]
    btc_up = btc.close > btc.close.rolling(100).mean()
    tsmom = {p: sig_tsmom(data[p], 30, False) for p in PAIRS}
    hold = {p: pd.Series(1.0, index=data[p].index) for p in PAIRS}

    rows = []
    for lev in [1, 2, 3, 5, 10, 20, 50]:
        eq = simulate(data, tsmom, lev, btc_up, 0.5)
        rows.append(summarise("TrendRegime", lev, eq[eq.index >= "2022-01-01"]))
        eq = simulate(data, hold, lev)
        rows.append(summarise("Acheter et garder (panier)", lev, eq[eq.index >= "2022-01-01"]))

    df = pd.DataFrame(rows)
    (ROOT / "results" / "montecarlo_6mois.json").write_text(json.dumps(rows, indent=1))
    pd.set_option("display.width", 200)
    print(df.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
