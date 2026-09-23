"""
Exploration rapide (vectorisée) de familles de stratégies sur données journalières.

But : trier des dizaines de variantes en quelques secondes AVANT de les
coder proprement dans Freqtrade (qui reste la référence pour valider).

Hypothèses simplifiées :
  - décision à la clôture du jour t, appliquée au rendement du jour t+1
  - capital réparti à parts égales entre les paires, levier L sur chaque part
  - frais + glissement : 0,08 % par changement de position (x levier)
  - liquidation : si le mouvement défavorable intrajournalier dépasse ~1/L,
    la part de la paire est perdue (isolated margin)
  - financement (funding) ignoré -> résultats un peu optimistes en long

Usage : python tools/explore.py
"""

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data" / "okx" / "futures"
PAIRS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]
COST = 0.0008
IS_END = "2025-01-01"


def load(tf: str = "1d") -> dict[str, pd.DataFrame]:
    out = {}
    for p in PAIRS:
        f = DATA / f"{p}_USDT_USDT-{tf}-futures.feather"
        df = pd.read_feather(f).set_index("date")
        out[p] = df
    return out


# ---------------------------------------------------------------- signaux
def sig_donchian(df, n, m, allow_short):
    hh = df.high.rolling(n).max().shift(1)
    ll = df.low.rolling(n).min().shift(1)
    xl = df.low.rolling(m).min().shift(1)
    xh = df.high.rolling(m).max().shift(1)
    pos = np.zeros(len(df))
    c = df.close.to_numpy()
    for i in range(1, len(df)):
        p = pos[i - 1]
        if p == 1 and c[i] < xl.iat[i]:
            p = 0
        elif p == -1 and c[i] > xh.iat[i]:
            p = 0
        if p == 0:
            if c[i] > hh.iat[i]:
                p = 1
            elif allow_short and c[i] < ll.iat[i]:
                p = -1
        pos[i] = p
    return pd.Series(pos, index=df.index)


def sig_sma(df, n, allow_short):
    sma = df.close.rolling(n).mean()
    pos = np.where(df.close > sma, 1, -1 if allow_short else 0)
    pos = pd.Series(pos, index=df.index, dtype=float)
    pos[sma.isna()] = 0
    return pos


def sig_ema_cross(df, f, s, allow_short):
    ef = df.close.ewm(span=f, adjust=False).mean()
    es = df.close.ewm(span=s, adjust=False).mean()
    pos = np.where(ef > es, 1, -1 if allow_short else 0)
    pos = pd.Series(pos, index=df.index, dtype=float)
    pos.iloc[:s] = 0
    return pos


def sig_tsmom(df, lb, allow_short):
    r = df.close.pct_change(lb)
    pos = np.where(r > 0, 1, -1 if allow_short else 0)
    pos = pd.Series(pos, index=df.index, dtype=float)
    pos[r.isna()] = 0
    return pos


# ---------------------------------------------------------------- moteur
def simulate(data, positions, lev, btc_filter=None, vol_target=None):
    """Retourne la courbe d'équité (1 = capital initial)."""
    idx = data["BTC"].index
    n = len(PAIRS)
    rets = []
    for p in PAIRS:
        df = data[p].reindex(idx)
        pos = positions[p].reindex(idx).fillna(0)
        if btc_filter is not None:
            pos = pos.where(~((pos > 0) & (~btc_filter)), 0)
        w = pos.copy()
        if vol_target:
            vol = df.close.pct_change().rolling(30).std() * np.sqrt(365)
            w = pos * (vol_target / vol).clip(upper=2.0).fillna(0)
        held = w.shift(1).fillna(0)  # position décidée hier, tenue aujourd'hui
        r = df.close.pct_change().fillna(0)
        # pire mouvement intrajournalier contre la position
        adverse_long = (df.low / df.close.shift(1) - 1).fillna(0)
        adverse_short = (df.high / df.close.shift(1) - 1).fillna(0)
        adverse = np.where(held > 0, -adverse_long * held, np.where(held < 0, adverse_short * -held, 0))
        pnl = held * r * lev
        liq = adverse * lev >= 0.9
        pnl = np.where(liq, -1.0, pnl)  # la part de la paire est perdue
        turnover = (w - w.shift(1).fillna(0)).abs() * COST * lev
        rets.append(pd.Series(pnl, index=idx) - turnover)
    port = pd.concat(rets, axis=1).mean(axis=1)
    equity = (1 + port.clip(lower=-1)).cumprod()
    return equity


def metrics(eq: pd.Series) -> dict:
    if len(eq) < 2:
        return {}
    eq = eq / eq.iloc[0]
    days = (eq.index[-1] - eq.index[0]).days or 1
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (365 / days) - 1 if eq.iloc[-1] > 0 else -1
    dd = (eq / eq.cummax() - 1).min()
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else 0
    return {"total_pct": total * 100, "cagr_pct": cagr * 100, "maxdd_pct": dd * 100, "sharpe": sharpe}


def split(eq):
    a = eq[(eq.index >= "2022-01-01") & (eq.index < IS_END)]
    b = eq[eq.index >= IS_END]
    return metrics(a), metrics(b)


def main():
    data = load("1d")
    btc = data["BTC"]
    btc_up = btc.close > btc.close.rolling(100).mean()

    variants = []
    for n, m, sh in itertools.product([20, 30, 55], [10, 20], [False, True]):
        variants.append((f"donchian_{n}_{m}{'_ls' if sh else ''}",
                         {p: sig_donchian(data[p], n, m, sh) for p in PAIRS}))
    for n, sh in itertools.product([30, 50, 100, 200], [False, True]):
        variants.append((f"sma_{n}{'_ls' if sh else ''}", {p: sig_sma(data[p], n, sh) for p in PAIRS}))
    for (f, s), sh in itertools.product([(10, 30), (20, 50), (50, 200)], [False, True]):
        variants.append((f"ema_{f}_{s}{'_ls' if sh else ''}",
                         {p: sig_ema_cross(data[p], f, s, sh) for p in PAIRS}))
    for lb, sh in itertools.product([14, 30, 60, 90], [False, True]):
        variants.append((f"tsmom_{lb}{'_ls' if sh else ''}", {p: sig_tsmom(data[p], lb, sh) for p in PAIRS}))
    variants.append(("buy_and_hold", {p: pd.Series(1.0, index=data[p].index) for p in PAIRS}))

    rows = []
    for name, pos in variants:
        for filt in [None, "btc100"]:
            for vt in [None, 0.5]:
                for lev in [1, 2, 3, 5]:
                    eq = simulate(data, pos, lev, btc_up if filt else None, vt)
                    ins, oos = split(eq)
                    rows.append({"variant": name, "btc_filter": bool(filt), "vol_target": vt, "lev": lev,
                                 **{f"is_{k}": v for k, v in ins.items()},
                                 **{f"oos_{k}": v for k, v in oos.items()}})
    df = pd.DataFrame(rows)
    out = ROOT / "results" / "explore_daily.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    # Classement : il faut être bon SUR LES DEUX périodes (robustesse)
    df["score"] = df[["is_sharpe", "oos_sharpe"]].min(axis=1)
    top = df[df.lev == 1].sort_values("score", ascending=False).head(20)
    pd.set_option("display.width", 200)
    print(top[["variant", "btc_filter", "vol_target", "is_total_pct", "is_maxdd_pct", "is_sharpe",
               "oos_total_pct", "oos_maxdd_pct", "oos_sharpe"]].round(2).to_string(index=False))
    print("\nBuy & hold x1 :")
    print(df[(df.variant == "buy_and_hold") & (df.lev == 1) & (~df.btc_filter) & (df.vol_target.isna())]
          [["is_total_pct", "is_maxdd_pct", "oos_total_pct", "oos_maxdd_pct"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
