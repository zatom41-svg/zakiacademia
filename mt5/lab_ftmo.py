"""
Laboratoire multi-actifs pour le challenge FTMO (bougies H1 Dukascopy).

1. Génère les trades de 4 familles de stratégies sur chaque actif, en unités
   de risque « R » (1 R = la perte si le stop est touché), coûts FTMO inclus.
2. Garde les couples stratégie x actif rentables sur 2022-2024 ET 2025-2026.
3. Rejoue le challenge FTMO (+10 %, perte max -10 %, perte journalière -5 %,
   4 jours min.) en démarrant un challenge CHAQUE jour de bourse.

Usage : python mt5/lab_ftmo.py --data dossier_csv
"""

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Coût aller-retour (spread + commission FTMO + glissement), en unités de prix
COSTS = {
    "EURUSD": 0.00008, "GBPUSD": 0.00011, "USDJPY": 0.011, "AUDUSD": 0.0001, "USDCAD": 0.00013,
    "USDCHF": 0.00013, "NZDUSD": 0.00013, "EURJPY": 0.016, "GBPJPY": 0.026, "EURGBP": 0.00011,
    "XAUUSD": 0.35, "XAGUSD": 0.03, "US100.cash": 2.0, "US30.cash": 3.5, "US500.cash": 0.7,
    "GER40.cash": 2.5, "UK100.cash": 1.8, "JP225.cash": 12.0, "USOIL.cash": 0.05,
}
# Cryptos FTMO : coût en fraction du prix (spread large + commission)
COST_PCT = {"NAS100QQQ": 0.00015, "BTCUSD": 0.0008, "ETHUSD": 0.0010, "SOLUSD": 0.0015, "XRPUSD": 0.0015}


def cost_of(sym: str, price: float) -> float:
    return COSTS[sym] if sym in COSTS else COST_PCT[sym] * price


# Heure (serveur FTMO, UTC+2/+3) d'ouverture de la session de référence
SESSION_OPEN = {s: 10 for s in list(COSTS) + list(COST_PCT)}  # Londres 08:00 = 10:00 serveur
SESSION_OPEN.update({"NAS100QQQ": 16, "BTCUSD": 16, "ETHUSD": 16, "SOLUSD": 16, "XRPUSD": 16, "US100.cash": 16, "US30.cash": 16, "US500.cash": 16, "USOIL.cash": 16,
                     "JP225.cash": 3})
SESSION_END = 22  # heure serveur de sortie forcée des trades intraday
IS_END = pd.Timestamp("2025-01-01", tz="Europe/Athens")


def load(folder: str) -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(Path(folder).glob("*_H1.csv")):
        sym = f.name.replace("_H1.csv", "")
        df = pd.read_csv(f)
        if df.empty:
            continue
        if "time_server" in df.columns:  # export ZA_ExportHistory.mq5 : heure du serveur FTMO
            idx = pd.DatetimeIndex(pd.to_datetime(df.time_server, unit="s"))
            df.index = idx.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward")
            df = df[df.index.notna()].drop(columns=[c for c in ("time_server", "spread_points") if c in df.columns])
        else:
            df.index = pd.DatetimeIndex(pd.to_datetime(df.time, unit="s", utc=True)).tz_convert("Europe/Athens")
            df = df.drop(columns="time")
        df = df.sort_index()
        df = df[~df.index.duplicated()]
        out[sym] = df
    return out


def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


# ---------------------------------------------------------------- exécution d'un trade
def walk(df, i, side, entry, stop, target, cost, max_bars=None, exit_hour=None, trail=None):
    """Suit un trade ouvert à l'ouverture de la bougie i. Retourne (index sortie, R, MAE en R)."""
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    hours = df.index.hour
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    mae = 0.0
    j = i
    n = len(df)
    while j < n:
        # stop d'abord (hypothèse prudente si stop et objectif sont dans la même bougie)
        adverse = (entry - l[j]) if side > 0 else (h[j] - entry)
        mae = max(mae, adverse / risk)
        if (side > 0 and l[j] <= stop) or (side < 0 and h[j] >= stop):
            px = stop if (side > 0 and o[j] > stop) or (side < 0 and o[j] < stop) else o[j]
            return j, ((px - entry) * side - cost) / risk, min(mae, 1.5)
        if target is not None and ((side > 0 and h[j] >= target) or (side < 0 and l[j] <= target)):
            return j, (abs(target - entry) - cost) / risk, mae
        if trail is not None:
            ext = h[j] if side > 0 else l[j]
            if (ext - entry) * side >= risk:
                new = ext - side * trail[j]
                stop = max(stop, entry, new) if side > 0 else min(stop, entry, new)
        end = (max_bars is not None and j - i + 1 >= max_bars) or \
              (exit_hour is not None and (hours[j] >= exit_hour - 1 or (j + 1 < n and df.index[j + 1].date() != df.index[j].date())))
        if end:
            return j, ((c[j] - entry) * side - cost) / risk, mae
        j += 1
    return None


# ---------------------------------------------------------------- stratégies
def s_breakout(df, sym, n=20, sl=2.0, tr=3.0):
    """Cassure Donchian H1 + EMA 200 (logique de l'EA v1.00)."""
    a = atr(df).values
    ema = df.close.ewm(span=200, adjust=False).mean().values
    hh = df.high.rolling(n).max().shift(1).values
    ll = df.low.rolling(n).min().shift(1).values
    c = df.close.values
    hrs = df.index.hour
    trades, i, last = [], 201, -1
    while i < len(df) - 1:
        side = 1 if c[i] > hh[i] and c[i] > ema[i] else -1 if c[i] < ll[i] and c[i] < ema[i] else 0
        if side and 8 <= hrs[i + 1] < 20:
            e = df.open.values[i + 1]
            r = walk(df, i + 1, side, e, e - side * sl * a[i], None, cost_of(sym, e), trail=tr * a)
            if r:
                trades.append((df.index[i + 1], df.index[r[0]], side, r[1], r[2]))
                i = r[0] + 1
                continue
        i += 1
    return trades


def s_orb(df, sym, rr=2.0, width_min=0.0):
    """Range de la 1re heure de session ; cassure dans les 4 h suivantes ; stop à l'autre bout ; sortie le soir."""
    trades = []
    so = SESSION_OPEN[sym]
    exit_h = 11 if sym == "JP225.cash" else SESSION_END
    a = atr(df, 24).values
    for day, g in df.groupby(df.index.date):
        first = g[g.index.hour == so]
        if first.empty:
            continue
        hi, lo = first.high.iloc[0], first.low.iloc[0]
        k0 = df.index.get_loc(first.index[0])
        if hi - lo < width_min * a[k0]:
            continue
        for k in range(k0 + 1, min(k0 + 5, len(df) - 1)):
            if df.index[k].date() != day:
                break
            cl = df.close.values[k]
            side = 1 if cl > hi else -1 if cl < lo else 0
            if side:
                e = df.open.values[k + 1]
                stop = lo if side > 0 else hi
                if (e - stop) * side <= 0:
                    break
                tgt = e + side * rr * abs(e - stop)
                r = walk(df, k + 1, side, e, stop, tgt, cost_of(sym, e), exit_hour=exit_h)
                if r:
                    trades.append((df.index[k + 1], df.index[r[0]], side, r[1], r[2]))
                break
    return trades


def s_pdhl(df, sym, rr=1.5):
    """Cassure du plus haut / plus bas de la veille pendant la session ; stop = milieu du range de la veille."""
    trades = []
    daily = df.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    prev = daily.shift(1)
    so = SESSION_OPEN[sym]
    exit_h = 11 if sym == "JP225.cash" else SESSION_END
    for day, g in df.groupby(df.index.date):
        ts = pd.Timestamp(day, tz="Europe/Athens")
        if ts not in prev.index or pd.isna(prev.loc[ts, "high"]):
            continue
        ph, pl = prev.loc[ts, "high"], prev.loc[ts, "low"]
        mid = (ph + pl) / 2
        sess = g[(g.index.hour >= so) & (g.index.hour < so + 6)]
        for t in sess.index:
            k = df.index.get_loc(t)
            if k + 1 >= len(df) or df.index[k + 1].date() != day:
                break
            cl = df.close.values[k]
            side = 1 if cl > ph else -1 if cl < pl else 0
            if side:
                e = df.open.values[k + 1]
                stop = mid
                if (e - stop) * side <= 0:
                    break
                r = walk(df, k + 1, side, e, stop, e + side * rr * abs(e - stop), cost_of(sym, e), exit_hour=exit_h)
                if r:
                    trades.append((df.index[k + 1], df.index[r[0]], side, r[1], r[2]))
                break
    return trades


def s_rsi2(df, sym, lo=10, sl=2.0, hold=6):
    """Retour à la moyenne : RSI(2) extrême dans le sens de l'EMA 200 ; sortie au rebond ou après N heures."""
    d = df.close.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn)).values
    ema = df.close.ewm(span=200, adjust=False).mean().values
    ema5 = df.close.ewm(span=5, adjust=False).mean().values
    a = atr(df).values
    c = df.close.values
    hrs = df.index.hour
    trades, i = [], 201
    while i < len(df) - 1:
        side = 1 if rsi[i] < lo and c[i] > ema[i] else -1 if rsi[i] > 100 - lo and c[i] < ema[i] else 0
        if side and 8 <= hrs[i + 1] < 21:
            e = df.open.values[i + 1]
            stop = e - side * sl * a[i]
            # sortie : retour au-dessus de l'EMA 5 (approché par un objectif à 1 ATR) ou après `hold` heures
            r = walk(df, i + 1, side, e, stop, e + side * 1.0 * a[i], cost_of(sym, e), max_bars=hold)
            if r:
                trades.append((df.index[i + 1], df.index[r[0]], side, r[1], r[2]))
                i = r[0] + 1
                continue
        i += 1
    return trades


STRATS = {
    "breakout": (s_breakout, [dict(n=n, sl=s) for n in (20, 55) for s in (2.0, 3.0)]),
    "orb": (s_orb, [dict(rr=r, width_min=w) for r in (1.0, 2.0, 3.0) for w in (0.0, 0.5)]),
    "pdhl": (s_pdhl, [dict(rr=r) for r in (1.0, 1.5, 2.5)]),
    "rsi2": (s_rsi2, [dict(lo=l, sl=s) for l in (5, 10) for s in (1.5, 3.0)]),
}


def pf(r):
    w, l = r[r > 0].sum(), -r[r < 0].sum()
    return w / l if l > 0 else (np.inf if w > 0 else 0)


def evaluate(data):
    rows, streams = [], {}
    for sym, df in data.items():
        for name, (fn, grid) in STRATS.items():
            for params in grid:
                t = pd.DataFrame(fn(df, sym, **params), columns=["open", "close", "side", "R", "mae"])
                if t.empty:
                    continue
                key = f"{name}|{sym}|{json.dumps(params)}"
                streams[key] = t
                a, b = t[t.open < IS_END].R, t[t.open >= IS_END].R
                days = (df.index[-1] - df.index[0]).days * 5 / 7
                rows.append({"key": key, "strategy": name, "symbol": sym, "params": json.dumps(params),
                             "trades_per_day": len(t) / days, "is_n": len(a), "is_pf": pf(a), "is_exp": a.mean(),
                             "oos_n": len(b), "oos_pf": pf(b), "oos_exp": b.mean()})
    return pd.DataFrame(rows), streams


# ---------------------------------------------------------------- challenge FTMO
def challenge(trades, start, risk, days_limit=None, target=10.0, max_loss=10.0, daily=5.0, daily_cut=4.0):
    """trades : DataFrame trié (open, close, R, mae) de tout le portefeuille."""
    t = trades[trades.open >= start]
    bal, b0 = 100.0, 100.0
    day, day_start, halted = None, bal, False
    traded_days = set()
    for row in t.itertuples():
        d = row.open.date()
        if days_limit and (row.open - start).days > days_limit:
            return "en cours", None
        if d != day:
            day, day_start, halted = d, bal, False
        if halted:
            continue
        stake = risk  # % du capital initial risqué par trade (comme un EA en lots fixes)
        # pire moment du trade (MAE) : la limite journalière FTMO compte le flottant
        if bal - stake * row.mae <= day_start - daily or bal - stake * row.mae <= b0 - max_loss:
            return "échoué", (row.close - start).days
        bal += stake * row.R
        traded_days.add(d)
        if bal <= b0 - max_loss or bal <= day_start - daily:
            return "échoué", (row.close - start).days
        if bal <= day_start - daily_cut:
            halted = True  # l'EA coupe la journée
        if bal >= b0 + target and len(traded_days) >= 4:
            return "réussi", (row.close - start).days
    return "en cours", None


def run_challenges(port, risk, starts, limit):
    res = [challenge(port, s, risk, days_limit=limit) for s in starts]
    ok = sum(r[0] == "réussi" for r in res)
    ko = sum(r[0] == "échoué" for r in res)
    return ok / len(res) * 100, ko / len(res) * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="mt5/results")
    a = ap.parse_args()
    data = load(a.data)
    print("Actifs :", ", ".join(f"{s} ({len(d)} h)" for s, d in data.items()))
    table, streams = evaluate(data)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    table.to_csv(Path(a.out) / "strategies_par_actif.csv", index=False)

    # Sélection sur la période d'APPRENTISSAGE seulement (avant 2025). La validation
    # 2025-2026 n'est jamais utilisée pour choisir : c'est ce qui la rend honnête.
    good = table[(table.is_pf > 1.15) & (table.is_n >= 40)]
    good = good.sort_values("is_pf", ascending=False).drop_duplicates(["strategy", "symbol"])
    pd.set_option("display.width", 220)
    print(f"\n{len(good)} couples stratégie x actif choisis sur 2023-2024 (facteur de profit > 1,15), puis vérifiés sur 2025-2026 :")
    print(good[["strategy", "symbol", "params", "trades_per_day", "is_n", "is_pf", "is_exp", "oos_n", "oos_pf", "oos_exp"]]
          .round(3).to_string(index=False))

    port = pd.concat([streams[k] for k in good.key]).sort_values("open").reset_index(drop=True)
    if port.empty:
        print("Aucun portefeuille robuste.")
        return
    oos = port[port.open >= IS_END]
    n_days = len(set(oos.open.dt.date))
    print(f"\nPortefeuille : {len(oos)} trades en validation (2025-2026), {len(oos) / max(n_days, 1):.1f} trades par jour de trading,"
          f" facteur de profit {pf(oos.R):.2f}, espérance {oos.R.mean():+.3f} R/trade")

    starts = [pd.Timestamp(d, tz="Europe/Athens") + pd.Timedelta(hours=1)
              for d in sorted(set(oos.open.dt.date)) if pd.Timestamp(d) <= pd.Timestamp("2026-08-15")]
    print(f"\nChallenge FTMO phase 1 : {len(starts)} départs (un par jour de 2025-2026)")
    print(f"{'Risque/trade':>12} | {'réussi <=14 j':>13} {'échoué <=14 j':>13} | {'réussi <=30 j':>13} {'échoué <=30 j':>13} |"
          f" {'réussi à terme':>14} {'échoué à terme':>14} | {'phase 2 réussie':>15}")
    starts_long = [s for s in starts if s <= pd.Timestamp("2026-03-01", tz="Europe/Athens")]
    summary = []
    for risk in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        ok14, ko14 = run_challenges(port, risk, starts, 14)
        ok30, ko30 = run_challenges(port, risk, starts, 30)
        okL, koL = run_challenges(port, risk, starts_long, 180)
        p2 = [challenge(port, s, risk, days_limit=180, target=5.0) for s in starts_long]
        ok2 = sum(r[0] == "réussi" for r in p2) / len(p2) * 100
        summary.append({"risk": risk, "ok14": ok14, "ko14": ko14, "ok30": ok30, "ko30": ko30,
                        "ok_180j": okL, "ko_180j": koL, "phase2_ok_180j": ok2})
        print(f"{risk:11.2f}% | {ok14:12.0f}% {ko14:12.0f}% | {ok30:12.0f}% {ko30:12.0f}% | {okL:13.0f}% {koL:13.0f}% | {ok2:14.0f}%")
    (Path(a.out) / "challenge.json").write_text(json.dumps({"portfolio": list(good.key), "summary": summary}, indent=1))


if __name__ == "__main__":
    main()
