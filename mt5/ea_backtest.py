"""
Backtest RAPIDE de la logique de l'EA FTMO_TrendBreakout, en Python, sans MT5.

Données : bougies H1 de PAXG/USDT (jeton adossé à l'or, suit XAUUSD) depuis
les archives publiques de Binance (data.binance.vision). Les week-ends sont
retirés pour imiter le marché de l'or, et l'heure est convertie en heure
serveur FTMO (UTC+2 l'hiver, UTC+3 l'été).

Reproduit l'EA : cassure Donchian N bougies + filtre EMA 200, stop = ATR x 2,
break-even à +1R, stop suiveur ATR x 3 après +1R, risque 1 % par trade,
3 trades max par jour, entrées de 8 h à 20 h, fermeture le vendredi 20 h,
coupure journalière à -4 %.

Limites : le prix intra-bougie est approché avec le plus haut / plus bas H1
(un stop touché dans la bougie compte toujours en premier), coûts estimés à
0,02 % aller-retour + 0,01 % de glissement.

Usage :
    python mt5/ea_backtest.py --data dossier_des_zip_PAXGUSDT
"""

import argparse
import glob
import io
import zipfile

import numpy as np
import pandas as pd

COST = 0.0003  # frais + glissement aller-retour, en fraction du prix


def load(folder: str) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(f"{folder}/PAXGUSDT-1h-*.zip")):
        with zipfile.ZipFile(f) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw), header=None, usecols=[0, 1, 2, 3, 4])
        df = df[pd.to_numeric(df[0], errors="coerce").notna()]
        frames.append(df)
    df = pd.concat(frames).astype(float)
    df.columns = ["t", "open", "high", "low", "close"]
    ms = np.where(df.t > 1e14, df.t // 1000, df.t).astype("int64")  # 2025+ : microsecondes
    df["time"] = pd.to_datetime(ms, unit="ms", utc=True)
    df = df.drop_duplicates("time").set_index("time").sort_index().drop(columns="t")
    df.index = df.index.tz_convert("Europe/Athens")  # heure des serveurs FTMO
    return df[df.index.dayofweek < 5]  # pas de week-end sur l'or


def backtest(df, n=20, sl_mult=2.0, trail_mult=3.0, risk=1.0, start="2022-01-01", end=None,
             ftmo=None, balance0=100_000.0):
    """ftmo = dict(target=10, max_loss=10, daily=4) pour simuler un challenge."""
    d = df[df.index >= pd.Timestamp(start, tz="Europe/Athens") - pd.Timedelta(days=40)]
    if end:
        d = d[d.index < pd.Timestamp(end, tz="Europe/Athens")]
    o, h, l, c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    tr = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()          # iATR de MT5 = moyenne simple
    ema = pd.Series(c).ewm(span=200, adjust=False).mean().to_numpy()
    hh = pd.Series(h).rolling(n).max().shift(1).to_numpy()      # N bougies AVANT la bougie signal
    ll = pd.Series(l).rolling(n).min().shift(1).to_numpy()
    idx = d.index
    t0 = pd.Timestamp(start, tz="Europe/Athens")

    bal = balance0
    pos = None
    trades, day_key, day_start, day_halt, n_today, traded_days = [], None, bal, False, 0, set()
    result = {"status": "en cours", "days": None}
    for i in range(len(d) - 1):
        now = idx[i + 1]  # ouverture de la bougie suivante = moment où l'EA agit
        if now < t0:
            continue
        key = now.date()
        if key != day_key:
            day_key, day_start, day_halt, n_today = key, bal, False, 0

        # 1) gestion de la position ouverte pendant la bougie i+1
        if pos:
            j = i + 1
            side = pos["side"]
            worst = l[j] if side > 0 else h[j]
            stop_hit = (worst <= pos["sl"]) if side > 0 else (worst >= pos["sl"])
            friday = now.dayofweek == 4 and now.hour >= 20
            exit_px = None
            if friday:
                exit_px = o[j]
            elif stop_hit:
                exit_px = pos["sl"] if (o[j] - pos["sl"]) * side > 0 else o[j]  # gap : sortie à l'ouverture
            if exit_px is None and ftmo:
                eq_worst = bal + (worst - pos["entry"]) * side * pos["units"]
                if eq_worst <= day_start - balance0 * ftmo["daily"] / 100:
                    exit_px = pos["entry"] + (day_start - balance0 * ftmo["daily"] / 100 - bal) / (side * pos["units"])
                    day_halt = True
            if exit_px is not None:
                pnl = (exit_px - pos["entry"]) * side * pos["units"] - COST * pos["entry"] * pos["units"]
                bal += pnl
                trades.append({"open": pos["time"], "close": now, "R": pnl / pos["risk_money"], "pnl": pnl})
                pos = None
            else:
                best = h[j] if side > 0 else l[j]
                move = (best - pos["entry"]) * side
                if move >= pos["r"]:
                    be = pos["entry"]
                    trail = best - trail_mult * atr[i] * side
                    new = max(pos["sl"], be, trail) if side > 0 else min(pos["sl"], be, trail)
                    pos["sl"] = new

        if ftmo:
            if bal <= balance0 * (1 - ftmo["max_loss"] / 100) or (day_halt and bal <= day_start - balance0 * 0.05):
                result = {"status": "échoué", "days": (now - t0).days}
                break
            if bal >= balance0 * (1 + ftmo["target"] / 100) and len(traded_days) >= 4:
                result = {"status": "réussi", "days": (now - t0).days}
                break

        # 2) nouvelle entrée à l'ouverture de la bougie i+1, sur signal de la bougie i
        if pos or day_halt or n_today >= 3 or np.isnan(atr[i]) or np.isnan(hh[i]):
            continue
        if not (8 <= now.hour < 20) or (now.dayofweek == 4 and now.hour >= 20):
            continue
        side = 1 if (c[i] > hh[i] and c[i] > ema[i]) else -1 if (c[i] < ll[i] and c[i] < ema[i]) else 0
        if not side:
            continue
        dist = atr[i] * sl_mult
        entry = o[i + 1]
        risk_money = bal * risk / 100
        pos = {"side": side, "entry": entry, "sl": entry - side * dist, "r": dist, "units": risk_money / dist,
               "risk_money": risk_money, "time": now}
        n_today += 1
        traded_days.add(key)
    trades = pd.DataFrame(trades)
    return bal, trades, result


def stats(bal0, bal, trades):
    if trades.empty:
        return {"trades": 0}
    eq = bal0 + trades.pnl.cumsum()
    dd = (eq / np.maximum.accumulate(np.concatenate([[bal0], eq.to_numpy()]))[1:] - 1).min()
    wins = trades[trades.pnl > 0].pnl.sum()
    losses = -trades[trades.pnl < 0].pnl.sum()
    return {"profit_pct": (bal / bal0 - 1) * 100, "maxdd_pct": dd * 100, "trades": len(trades),
            "winrate_pct": (trades.pnl > 0).mean() * 100, "profit_factor": wins / losses if losses else np.inf,
            "avg_R": trades.R.mean()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--export-r", help="écrit les résultats en R (pour ftmo_sim.py)")
    a = ap.parse_args()
    df = load(a.data)
    print(f"Données : {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}, {len(df)} bougies H1\n")

    print("=== 1. Réglages par défaut (Donchian 20, stop 2 ATR, suiveur 3 ATR), risque", a.risk, "% ===")
    for y in [2022, 2023, 2024, 2025, 2026]:
        bal, tr, _ = backtest(df, risk=a.risk, start=f"{y}-01-01", end=f"{y + 1}-01-01")
        s = stats(100_000, bal, tr)
        print(f"{y}: " + ("aucun trade" if not s["trades"] else
              f"{s['profit_pct']:+6.1f} %  DD {s['maxdd_pct']:6.1f} %  {s['trades']:3d} trades  "
              f"{s['winrate_pct']:4.0f} % gagnants  PF {s['profit_factor']:.2f}  moy {s['avg_R']:+.2f} R"))
    bal, tr, _ = backtest(df, risk=a.risk)
    s = stats(100_000, bal, tr)
    print(f"TOUT 2022→: {s['profit_pct']:+.1f} %  DD {s['maxdd_pct']:.1f} %  {s['trades']} trades  PF {s['profit_factor']:.2f}  moy {s['avg_R']:+.2f} R")
    if a.export_r:
        np.savetxt(a.export_r, tr.R.to_numpy(), fmt="%.3f")

    print("\n=== 2. Robustesse : facteur de profit 2022-2024 → 2025-2026 ===")
    for n in [10, 20, 30, 55]:
        row = []
        for sl in [1.5, 2.0, 3.0]:
            b1, t1, _ = backtest(df, n=n, sl_mult=sl, risk=a.risk, start="2022-01-01", end="2025-01-01")
            b2, t2, _ = backtest(df, n=n, sl_mult=sl, risk=a.risk, start="2025-01-01")
            p1, p2 = stats(1e5, b1, t1).get("profit_factor", 0), stats(1e5, b2, t2).get("profit_factor", 0)
            row.append(f"stop {sl}: {p1:4.2f} → {p2:4.2f}")
        print(f"Donchian {n:2d} | " + " | ".join(row))

    print("\n=== 3. Challenge FTMO simulé : un départ au 1er de chaque mois (2022 → 2026) ===")
    months = pd.date_range("2022-01-01", "2026-08-01", freq="MS")
    for risk in [0.5, 1.0, 1.5, 2.0]:
        res = [backtest(df, risk=risk, start=m.strftime("%Y-%m-%d"), ftmo={"target": 10, "max_loss": 10, "daily": 4})[2]
               for m in months]
        ok30 = sum(r["status"] == "réussi" and r["days"] <= 30 for r in res)
        ok = sum(r["status"] == "réussi" for r in res)
        ko = sum(r["status"] == "échoué" for r in res)
        med = np.median([r["days"] for r in res if r["status"] == "réussi"]) if ok else float("nan")
        print(f"risque {risk:3.1f} % : réussi en < 30 j {ok30:2d}/{len(res)}  |  réussi un jour {ok:2d}  "
              f"échoué {ko:2d}  jamais conclu {len(res) - ok - ko:2d}  |  durée médiane {med:.0f} j")


if __name__ == "__main__":
    main()
