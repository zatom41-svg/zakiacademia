"""
Laboratoire du bot ZA_Gold_Creux (achat de creux RSI(2) en H1 sur l'or).

Rejoue la logique de l'EA (v1.40) bougie par bougie, avec intérêts composés :
  - entrée à l'ouverture si, sur la bougie close : RSI(2) < niveau et clôture > EMA 200 H1
  - filtre tendance : clôture journalière de la veille > SMA 50 jours
  - filtre volatilité : ATR14 / ATR480 < limite
  - sortie : stop ATR, rebond (clôture > SMA 5) ou après N bougies
Option : ventes en miroir quand l'or est sous sa SMA 50 jours.

Usage : python mt5/gold_creux_lab.py --data dossier_zip_PAXG
"""

import argparse

import numpy as np
import pandas as pd

import ea_backtest as eb

COST = 0.00012


def indicators(df):
    c = df.close
    pc = c.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    day = c.resample("1D").last().dropna()
    dsma = day.rolling(50).mean()
    prev_up = (day > dsma).shift(1)  # veille au-dessus de la SMA 50 jours
    return pd.DataFrame({
        "rsi": 100 - 100 / (1 + up / dn), "ema": c.ewm(span=200, adjust=False).mean(),
        "sma5": c.rolling(5).mean(), "atr": tr.rolling(14).mean(), "atrl": tr.rolling(480).mean(),
        "trend": prev_up.reindex(df.index.normalize()).to_numpy(),
    }, index=df.index)


def run(df, ind, lvl=10, sl=4.0, hold=12, risk=1.5, vol=1.5, shorts=False, start="2024-01-01", end=None):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rsi, ema, sma5, atr, atrl, trend = (ind[k].to_numpy() for k in ("rsi", "ema", "sma5", "atr", "atrl", "trend"))
    t0 = df.index.searchsorted(pd.Timestamp(start, tz=df.index.tz))
    t1 = df.index.searchsorted(pd.Timestamp(end, tz=df.index.tz)) if end else len(df)
    bal, eq, trades = 1.0, [], []
    i = t0
    while i < t1 - 1:
        k = i  # bougie close
        side = 0
        if not np.isnan(atrl[k]) and trend[k] is not None and not pd.isna(trend[k]) and (not vol or atr[k] / atrl[k] < vol):
            if trend[k] and rsi[k] < lvl and c[k] > ema[k]:
                side = 1
            elif shorts and not trend[k] and rsi[k] > 100 - lvl and c[k] < ema[k]:
                side = -1
        if not side:
            eq.append((df.index[i], bal))
            i += 1
            continue
        e = o[k + 1]
        stop = e - side * sl * atr[k]
        px, j = None, k + 1
        while j < t1:
            if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
                px = stop if (o[j] - stop) * side > 0 else o[j]
                break
            if (side > 0 and c[j] > sma5[j]) or (side < 0 and c[j] < sma5[j]) or j - k >= hold:
                px = c[j]
                break
            j += 1
        if px is None:
            break
        r = ((px - e) * side - COST * e) / abs(e - stop)
        bal *= 1 + risk / 100 * r
        trades.append((df.index[k + 1], r, side))
        eq.append((df.index[j], bal))
        i = j + 1
    s = pd.Series(dict(eq))
    return s, pd.DataFrame(trades, columns=["time", "R", "side"])


def stats(s):
    dd = (s / s.cummax() - 1).min() * 100
    return (s.iloc[-1] - 1) * 100, dd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    df = eb.load(a.data)
    ind = indicators(df)
    variants = {
        "Vos réglages (stop 2, 6 h, 2 %)": dict(sl=2.0, hold=6, risk=2.0),
        "v1.40 par défaut (stop 4, 12 h, 1,5 %)": dict(),
        "v1.40 à 2 %": dict(risk=2.0),
        "v1.40 à 3 %": dict(risk=3.0),
        "v1.40 + ventes en baisse, 2 %": dict(risk=2.0, shorts=True),
        "v1.40 RSI<20, 2 %": dict(lvl=20, risk=2.0),
        "v1.40 RSI<5, 2 %": dict(lvl=5, risk=2.0),
        "v1.40 sortie 24 h, 2 %": dict(hold=24, risk=2.0),
        "v1.40 sans filtre volatilité, 2 %": dict(vol=0, risk=2.0),
    }
    rows = []
    for name, kw in variants.items():
        row = {"variante": name}
        for y in (2022, 2023, 2024, 2025, 2026):
            s, t = run(df, ind, start=f"{y}-01-01", end=f"{y + 1}-01-01", **kw)
            row[str(y)] = round(stats(s)[0], 1)
        s, t = run(df, ind, start="2024-01-01", **kw)
        row["2024→26"], row["pire baisse"] = (round(v, 1) for v in stats(s))
        row["trades/an"] = round(len(t) / 2.73)
        rows.append(row)
    p = df.close
    bh = lambda y0, y1: round((p[p.index.year <= y1].iloc[-1] / p[p.index.year >= y0].iloc[0] - 1) * 100, 1)
    rows.append({"variante": "Or acheté et gardé (x1)", **{str(y): bh(y, y) for y in (2022, 2023, 2024, 2025, 2026)},
                 "2024→26": bh(2024, 2026)})
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))
    res.to_csv("mt5/results/gold_creux_lab.csv", index=False)


if __name__ == "__main__":
    main()
