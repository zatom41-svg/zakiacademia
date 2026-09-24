"""
Optimisation ROBUSTE : on ne garde pas le meilleur backtest, mais le réglage
qui tient le mieux ANNÉE PAR ANNÉE (2022 → 2026), puis on vérifie avec un
walk-forward : chaque année est jouée avec les réglages choisis uniquement
sur les années précédentes.

Usage : python tools/optimize_robust.py
Écrit : results/robust_<strategie>.csv et results/walkforward.json
"""

import itertools
import json

import numpy as np
import pandas as pd

from lab import ROOT, YEARS, combine, dip_weights, load, metrics, run, trend_weights, yearly

GRIDS = {
    "trend": (trend_weights, {"lookback": [10, 14, 20, 30, 45, 60, 90],
                              "btc_sma": [0, 50, 100, 150, 200],
                              "vol_target": [0.3, 0.5, 0.8]}),
    "dip": (dip_weights, {"entry": [5, 10, 15, 20, 25], "exit_": [50, 60, 70, 80],
                          "sma": [50, 100, 200]}),
}


def score(years: dict) -> float:
    """Robustesse : moyenne des Sharpe annuels moins leur dispersion, pénalité si une année perd."""
    s = np.array([years[y].get("sharpe", 0) for y in YEARS])
    worst = min(years[y].get("total_pct", 0) for y in YEARS)
    return s.mean() - 0.5 * s.std() + (0 if worst >= 0 else worst / 20)


def grid_rows(data, name):
    fn, grid = GRIDS[name]
    rows = []
    keys = list(grid)
    for combo in itertools.product(*grid.values()):
        params = dict(zip(keys, combo))
        w = fn(data, **params)
        ys = yearly(data, w)
        row = {**params, "score": score(ys)}
        for y in YEARS:
            row[f"{y}_pct"] = ys[y].get("total_pct")
            row[f"{y}_dd"] = ys[y].get("maxdd_pct")
            row[f"{y}_sharpe"] = ys[y].get("sharpe")
        rows.append((row, w))
    return rows


def walk_forward(data, name, rows):
    """Pour chaque année Y, choisit le réglage le plus robuste sur les années < Y."""
    fn, grid = GRIDS[name]
    keys = list(grid)
    chosen = {}
    pieces = []
    for y in YEARS[1:]:
        past = [yy for yy in YEARS if yy < y]
        best = max(rows, key=lambda rw: np.mean([rw[0][f"{yy}_sharpe"] for yy in past])
                   - 0.5 * np.std([rw[0][f"{yy}_sharpe"] for yy in past]))
        params = {k: best[0][k] for k in keys}
        chosen[y] = params
        pieces.append(run(data, best[1], 1.0, f"{y}-01-01", f"{y + 1}-01-01").pnl)
    pnl = pd.concat(pieces)
    eq = (1 + pnl).cumprod()
    return chosen, metrics(pd.DataFrame({"pnl": pnl, "equity": eq * 1000, "liq": 0, "expo": 0}))


def main():
    data = load()
    out = {}
    best_w = {}
    pd.set_option("display.width", 250)
    for name in GRIDS:
        rows = grid_rows(data, name)
        df = pd.DataFrame([r for r, _ in rows]).sort_values("score", ascending=False)
        df.to_csv(ROOT / "results" / f"robust_{name}.csv", index=False)
        cols = list(GRIDS[name][1]) + ["score"] + [f"{y}_pct" for y in YEARS]
        print(f"\n=== {name} : 10 réglages les plus robustes (x1, % par année) ===")
        print(df[cols].head(10).round(1).to_string(index=False))
        chosen, wf = walk_forward(data, name, rows)
        print(f"Walk-forward 2023-2026 : {wf['total_pct']:.1f} %  (baisse max {wf['maxdd_pct']:.1f} %, Sharpe {wf['sharpe']:.2f})")
        print("Réglages choisis chaque année :", chosen)
        top = df.iloc[0]
        best_params = {k: (int(top[k]) if float(top[k]).is_integer() else float(top[k])) for k in GRIDS[name][1]}
        best_w[name] = GRIDS[name][0](data, **best_params)
        out[name] = {"robust_params": best_params, "walk_forward": wf, "walk_forward_choices": {str(k): v for k, v in chosen.items()}}

    combo = combine(best_w["trend"], best_w["dip"], split=[0.7, 0.3])
    print("\n=== Combinaison 70 % trend + 30 % dip, par année (x1) ===")
    ys = yearly(data, combo)
    print({y: round(ys[y]["total_pct"], 1) for y in YEARS})
    out["combo_yearly"] = {str(y): ys[y] for y in YEARS}
    (ROOT / "results" / "walkforward.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
