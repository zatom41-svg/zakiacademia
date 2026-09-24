"""
Monte Carlo : chances de faire x2, x10, x100 en 6 mois, ou de perdre la moitié,
selon le levier. On rejoue 20 000 trajectoires de 180 jours faites de blocs de
30 jours réels (2022 → aujourd'hui, moteur tools/lab.py).

Usage : python tools/montecarlo.py
"""

import json

import numpy as np

from lab import ROOT, hold_weights, load, run, trend_weights

N_PATHS, HORIZON, BLOCK = 20_000, 180, 30
rng = np.random.default_rng(42)


def summarise(name, lev, daily):
    starts = rng.integers(0, len(daily) - BLOCK, size=(N_PATHS, HORIZON // BLOCK))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(N_PATHS, -1)
    p = np.cumprod(1 + daily[idx], axis=1)
    final = p[:, -1]
    reached = lambda x: float((p.max(axis=1) >= x).mean() * 100)
    return {"strategy": name, "leverage": lev, "p_x2_pct": reached(2), "p_x10_pct": reached(10),
            "p_x100_pct": reached(100), "p_loss_half_pct": float((final <= 0.5).mean() * 100),
            "p_ruin_pct": float((final <= 0.05).mean() * 100), "median_final_x": float(np.median(final))}


def main():
    data = load()
    rows = []
    for name, w in [("TrendRegime", trend_weights(data)), ("Acheter et garder", hold_weights(data))]:
        for lev in [1, 2, 3, 5, 10, 20]:
            daily = run(data, w, lev, "2022-01-01").pnl.clip(lower=-1).to_numpy()
            rows.append(summarise(name, lev, daily))
            r = rows[-1]
            print(f"{name:18s} x{lev:<3} x2 {r['p_x2_pct']:5.1f}%  x10 {r['p_x10_pct']:5.1f}%  x100 {r['p_x100_pct']:5.2f}%  "
                  f"perdre 50% {r['p_loss_half_pct']:5.1f}%  ruine {r['p_ruin_pct']:5.1f}%  médian x{r['median_final_x']:.2f}")
    (ROOT / "results" / "montecarlo_6mois.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
