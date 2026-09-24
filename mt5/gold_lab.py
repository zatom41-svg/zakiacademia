"""
Laboratoire OR (XAUUSD) : cherche une stratégie rentable ANNÉE PAR ANNÉE.

Données : bougies H1 de PAXG (suit XAUUSD), heure serveur FTMO, sans week-ends
(chargées par ea_backtest.load). Coût : 0,012 % du prix par aller-retour.

Chaque trade est mesuré en R (1 R = la perte si le stop est touché).
Sélection sur 2021-2023 uniquement ; 2024, 2025, 2026 servent de vérification.

Usage : python mt5/gold_lab.py --data dossier_zip_PAXG
"""

import argparse
import itertools

import numpy as np
import pandas as pd

import ea_backtest as eb

COST = 0.00012


def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def walk(df, i, side, stop, target=None, exit_i=None):
    """Trade ouvert à l'ouverture de la bougie i. Sortie : stop, objectif, ou clôture de la bougie exit_i."""
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    e = o[i]
    risk = abs(e - stop)
    if risk <= 0:
        return None
    last = min(exit_i if exit_i is not None else len(df) - 1, len(df) - 1)
    for j in range(i, last + 1):
        if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
            px = stop if (o[j] - stop) * side > 0 else o[j]
            return j, ((px - e) * side - COST * e) / risk
        if target is not None and ((side > 0 and h[j] >= target) or (side < 0 and l[j] <= target)):
            return j, (abs(target - e) - COST * e) / risk
    return last, ((c[last] - e) * side - COST * e) / risk


# ------------------------------------------------------------------ stratégies
def s_hours(df, start_h, end_h, sl=1.5, side=1):
    """Position chaque jour de start_h à end_h (heure serveur), stop ATR."""
    a = atr(df, 24).values
    out = []
    for day, g in df.groupby(df.index.date):
        s = g[g.index.hour == start_h]
        e = g[g.index.hour == end_h - 1]
        if s.empty or e.empty:
            continue
        i = df.index.get_loc(s.index[0])
        k = df.index.get_loc(e.index[0])
        if np.isnan(a[i - 1]):
            continue
        r = walk(df, i, side, df.open.values[i] - side * sl * a[i - 1], exit_i=k)
        if r:
            out.append((df.index[i], r[1]))
    return out


def s_asian_breakout(df, rr=1.5, end_h=20):
    """Range 01h-09h (serveur) ; cassure entre 10h et 14h ; stop = autre bout ; sortie à end_h."""
    out = []
    for day, g in df.groupby(df.index.date):
        asia = g[(g.index.hour >= 1) & (g.index.hour < 10)]
        sess = g[(g.index.hour >= 10) & (g.index.hour < 14)]
        if len(asia) < 6 or sess.empty:
            continue
        hi, lo = asia.high.max(), asia.low.min()
        for t in sess.index:
            k = df.index.get_loc(t)
            c = df.close.values[k]
            side = 1 if c > hi else -1 if c < lo else 0
            if side and k + 1 < len(df) and df.index[k + 1].date() == day:
                e = df.open.values[k + 1]
                stop = lo if side > 0 else hi
                if (e - stop) * side <= 0:
                    break
                ex = g[g.index.hour == end_h - 1]
                exit_i = df.index.get_loc(ex.index[0]) if not ex.empty else None
                r = walk(df, k + 1, side, stop, e + side * rr * abs(e - stop), exit_i)
                if r:
                    out.append((df.index[k + 1], r[1]))
                break
    return out


def daily(df):
    d = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return d


def s_daily_trend(df, n=50, sl=3.0, long_only=True):
    """Tendance journalière : long tant que la clôture > SMA n ; stop ATR journalier x sl."""
    d = daily(df)
    sma = d.close.rolling(n).mean()
    a = atr(d, 14)
    out, i = [], n + 15
    while i < len(d) - 1:
        up = d.close.iloc[i] > sma.iloc[i]
        side = 1 if up else (0 if long_only else -1)
        if side:
            e = d.open.iloc[i + 1]
            stop = e - side * sl * a.iloc[i]
            j = i + 1
            res = None
            while j < len(d):
                if (side > 0 and d.low.iloc[j] <= stop) or (side < 0 and d.high.iloc[j] >= stop):
                    px = stop if (d.open.iloc[j] - stop) * side > 0 else d.open.iloc[j]
                    res = (j, ((px - e) * side - COST * e) / abs(e - (e - side * sl * a.iloc[i])))
                    break
                if (d.close.iloc[j] > sma.iloc[j]) != up:  # signal inverse : sortie à l'ouverture suivante
                    x = d.open.iloc[j + 1] if j + 1 < len(d) else d.close.iloc[j]
                    res = (j + 1, ((x - e) * side - COST * e) / (sl * a.iloc[i]))
                    break
                j += 1
            if res:
                out.append((d.index[i + 1], res[1]))
                i = res[0]
                continue
        i += 1
    return out


def s_rsi_dip(df, tf="4h", lvl=10, sl=2.0, hold=6, sma_n=50):
    """Achat de creux : RSI(2) < lvl au-dessus de la SMA ; sortie au rebond (clôture > SMA 5) ou après hold bougies."""
    d = df.resample(tf).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna() if tf != "1h" else df
    dd = d.close.diff()
    up = dd.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-dd.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    sma = d.close.rolling(sma_n).mean()
    sma5 = d.close.rolling(5).mean()
    a = atr(d, 14)
    out, i = [], sma_n + 15
    while i < len(d) - 1:
        if rsi.iloc[i] < lvl and d.close.iloc[i] > sma.iloc[i]:
            e = d.open.iloc[i + 1]
            stop = e - sl * a.iloc[i]
            res = None
            for j in range(i + 1, min(i + 1 + hold, len(d))):
                if d.low.iloc[j] <= stop:
                    px = stop if d.open.iloc[j] > stop else d.open.iloc[j]
                    res = (j, (px - e - COST * e) / (e - stop))
                    break
                if d.close.iloc[j] > sma5.iloc[j] or j == min(i + hold, len(d) - 1):
                    res = (j, (d.close.iloc[j] - e - COST * e) / (e - stop))
                    break
            if res:
                out.append((d.index[i + 1], res[1]))
                i = res[0] + 1
                continue
        i += 1
    return out


def s_prev_high(df, rr=2.0):
    """Cassure du plus haut de la veille (achat seulement) entre 10h et 18h ; stop = plus bas du jour en cours."""
    d = daily(df)
    ph = d.high.shift(1)
    out = []
    for day, g in df.groupby(df.index.date):
        ts = pd.Timestamp(day, tz=df.index.tz)
        if ts not in ph.index or np.isnan(ph.loc[ts]):
            continue
        for t in g[(g.index.hour >= 10) & (g.index.hour < 18)].index:
            k = df.index.get_loc(t)
            if df.close.values[k] > ph.loc[ts] and k + 1 < len(df) and df.index[k + 1].date() == day:
                e = df.open.values[k + 1]
                stop = g.loc[:t].low.min()
                if e <= stop:
                    break
                ex = g[g.index.hour == 21]
                r = walk(df, k + 1, 1, stop, e + rr * (e - stop), df.index.get_loc(ex.index[0]) if not ex.empty else None)
                if r:
                    out.append((df.index[k + 1], r[1]))
                break
    return out


def s_weekday(df, wd, sl=2.0):
    """Long du lundi (0) ... vendredi (4) : ouverture 02h → clôture 22h ce jour-là."""
    a = atr(df, 24).values
    out = []
    for day, g in df.groupby(df.index.date):
        if pd.Timestamp(day).dayofweek != wd:
            continue
        s, e = g[g.index.hour == 2], g[g.index.hour == 21]
        if s.empty or e.empty:
            continue
        i, k = df.index.get_loc(s.index[0]), df.index.get_loc(e.index[0])
        r = walk(df, i, 1, df.open.values[i] - sl * a[i - 1], exit_i=k)
        if r:
            out.append((df.index[i], r[1]))
    return out


def variants():
    for sh, eh in [(1, 9), (1, 5), (9, 16), (16, 22), (3, 10), (10, 17)]:
        for side in (1, -1):
            yield f"heures {sh:02d}h-{eh:02d}h {'achat' if side > 0 else 'vente'}", lambda df, sh=sh, eh=eh, side=side: s_hours(df, sh, eh, side=side)
    for rr in (1.0, 1.5, 2.5):
        yield f"range asiatique RR {rr}", lambda df, rr=rr: s_asian_breakout(df, rr)
    for n, sl in itertools.product((20, 50, 100), (2.0, 3.0)):
        yield f"tendance jour SMA{n} stop {sl} ATR", lambda df, n=n, sl=sl: s_daily_trend(df, n, sl)
    for tf, lvl, sma_n in itertools.product(("1h", "4h", "1D"), (5, 10, 20), (50, 200)):
        yield f"achat de creux RSI2<{lvl} {tf} SMA{sma_n}", lambda df, tf=tf, lvl=lvl, sma_n=sma_n: s_rsi_dip(df, tf, lvl, sma_n=sma_n)
    for rr in (1.0, 2.0, 3.0):
        yield f"cassure plus haut veille RR {rr}", lambda df, rr=rr: s_prev_high(df, rr)
    for wd, name in enumerate(("lundi", "mardi", "mercredi", "jeudi", "vendredi")):
        yield f"achat le {name}", lambda df, wd=wd: s_weekday(df, wd)


def pf(r):
    w, l = r[r > 0].sum(), -r[r < 0].sum()
    return w / l if l > 0 else np.inf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    df = eb.load(a.data)
    df = df[df.index >= pd.Timestamp("2021-01-01", tz=df.index.tz)]
    rows = []
    for name, fn in variants():
        t = pd.DataFrame(fn(df), columns=["time", "R"])
        if t.empty:
            continue
        t["year"] = t.time.dt.year
        is_ = t[t.year <= 2023].R
        row = {"stratégie": name, "trades/an": len(t) / 5.7, "PF 2021-23": pf(is_), "R/trade 21-23": is_.mean()}
        for y in (2024, 2025, 2026):
            ry = t[t.year == y].R
            row[f"R {y}"] = ry.sum()
        row["PF 2024-26"] = pf(t[t.year >= 2024].R)
        rows.append(row)
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    chosen = res[(res["PF 2021-23"] > 1.2) & (res["trades/an"] >= 20)].sort_values("PF 2021-23", ascending=False)
    print("=== Choisies sur 2021-2023 (facteur de profit > 1,2), puis vérifiées sur 2024, 2025, 2026 (total en R) ===")
    print(chosen.round(2).to_string(index=False))
    print("\n=== Toutes les variantes (tri : facteur de profit 2024-2026) ===")
    print(res.sort_values("PF 2024-26", ascending=False).round(2).head(15).to_string(index=False))
    res.to_csv("mt5/results/gold_lab.csv", index=False)


if __name__ == "__main__":
    main()
