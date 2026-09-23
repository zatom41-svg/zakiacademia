"""
Exploration n°2 : nouvelles familles pour remplacer les stratégies perdantes.

  A. Rotation (momentum en coupe transversale) : chaque semaine, on détient
     les K cryptos qui ont le plus monté sur N jours (si BTC en régime haussier)
  B. Retour à la moyenne court terme (type Connors RSI-2) : on achète une
     baisse brutale seulement dans une tendance haussière, sortie au rebond
  C. Cassure Donchian journalière long-only avec filtre de régime

Même moteur simplifié que explore.py.  Usage : python tools/explore2.py
"""

import itertools

import numpy as np
import pandas as pd

from explore import PAIRS, ROOT, load, simulate, split


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def rotation(data, lookback, k, rebalance_days):
    closes = pd.DataFrame({p: data[p].close for p in PAIRS})
    mom = closes.pct_change(lookback)
    pos = pd.DataFrame(0.0, index=closes.index, columns=PAIRS)
    current = pd.Series(0.0, index=PAIRS)
    for i, d in enumerate(closes.index):
        if i % rebalance_days == 0:
            row = mom.loc[d].dropna()
            current = pd.Series(0.0, index=PAIRS)
            if len(row) >= k:
                winners = row[row > 0].nlargest(k).index
                # K positions concentrées : chaque gagnante vaut 8/K parts
                current[winners] = len(PAIRS) / k
        pos.loc[d] = current
    return {p: pos[p] for p in PAIRS}


def reversion(df, rsi_n, entry, exit_, trend):
    r = rsi(df.close, rsi_n)
    sma = df.close.rolling(trend).mean()
    pos = np.zeros(len(df))
    for i in range(1, len(df)):
        p = pos[i - 1]
        if p == 1 and (r.iat[i] > exit_ or df.close.iat[i] < sma.iat[i] * 0.9):
            p = 0
        elif p == 0 and r.iat[i] < entry and df.close.iat[i] > sma.iat[i]:
            p = 1
        pos[i] = p
    return pd.Series(pos, index=df.index)


def main():
    data = load("1d")
    btc = data["BTC"]
    btc_up = btc.close > btc.close.rolling(100).mean()
    rows = []

    def add(name, pos, vts=(None, 0.5)):
        for vt in vts:
            for lev in [1, 2, 3]:
                eq = simulate(data, pos, lev, btc_up, vt)
                ins, oos = split(eq)
                rows.append({"variant": name, "vol_target": vt, "lev": lev,
                             **{f"is_{k}": v for k, v in ins.items()},
                             **{f"oos_{k}": v for k, v in oos.items()}})

    for lb, k, rb in itertools.product([14, 30, 60], [1, 2, 3, 4], [7, 14]):
        add(f"rotation_{lb}d_top{k}_every{rb}", rotation(data, lb, k, rb), vts=(None,))
    for n, e, x, t in itertools.product([2, 3], [10, 20, 30], [60, 70], [100, 200]):
        add(f"reversion_rsi{n}_{e}_{x}_sma{t}", {p: reversion(data[p], n, e, x, t) for p in PAIRS})

    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "results" / "explore2_daily.csv", index=False)
    df["score"] = df[["is_sharpe", "oos_sharpe"]].min(axis=1)
    pd.set_option("display.width", 220)
    for fam in ["rotation", "reversion"]:
        top = df[(df.lev == 1) & df.variant.str.startswith(fam)].sort_values("score", ascending=False).head(8)
        print(f"\n=== {fam} (x1) ===")
        print(top[["variant", "vol_target", "is_total_pct", "is_maxdd_pct", "is_sharpe",
                   "oos_total_pct", "oos_maxdd_pct", "oos_sharpe"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
