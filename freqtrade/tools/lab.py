"""
Moteur de simulation journalier « réaliste » partagé par l'optimisation et le panel.

Par rapport à explore.py :
  - décision à la clôture du jour J, exécution à l'OUVERTURE du jour J+1
  - frais 0,05 % + glissement 0,03 % à chaque changement de position (x levier)
  - financement (funding) : 0,01 % toutes les 8 h payé sur les positions longues
    (moyenne typique en marché haussier), soit ~11 % par an du montant exposé
  - liquidation (marge isolée) si la mèche du jour dépasse 90 % de la marge

Les stratégies renvoient une « position voulue » par paire et par jour :
0 (dehors) ou un poids entre 0 et 1 (part du capital réservée à la paire).
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data" / "okx" / "futures"
PAIRS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]
FEE = 0.0008
FUNDING_DAY = 0.0003
YEARS = [2022, 2023, 2024, 2025, 2026]


def load() -> dict[str, pd.DataFrame]:
    frames = {p: pd.read_feather(DATA / f"{p}_USDT_USDT-1d-futures.feather").set_index("date") for p in PAIRS}
    idx = frames["BTC"].index
    return {p: df.reindex(idx) for p, df in frames.items()}


# ------------------------------------------------------------------ indicateurs
def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def vol30(close: pd.Series) -> pd.Series:
    return close.pct_change().rolling(30).std() * np.sqrt(365)


def btc_regime(data, sma: int | None) -> pd.Series:
    btc = data["BTC"].close
    if not sma:
        return pd.Series(True, index=btc.index)
    return btc > btc.rolling(sma).mean()


# ------------------------------------------------------------------ stratégies
def trend_weights(data, lookback=30, btc_sma=200, vol_target=0.5):
    """TrendRegime : long si la crypto a monté sur `lookback` jours et BTC en régime haussier."""
    regime = btc_regime(data, btc_sma)
    out = {}
    for p in PAIRS:
        c = data[p].close
        on = (c.pct_change(lookback) > 0) & regime
        w = (vol_target / vol30(c)).clip(upper=1.0) if vol_target else pd.Series(1.0, index=c.index)
        out[p] = (on.astype(float) * w).fillna(0)
    return out


def dip_weights(data, entry=10, exit_=60, sma=100, btc_sma=100, vol_target=0.5):
    """DipReversion : achète un RSI(3) très bas au-dessus de la SMA, revend au rebond."""
    regime = btc_regime(data, btc_sma)
    out = {}
    for p in PAIRS:
        c = data[p].close
        r = rsi(c, 3).to_numpy()
        m = c.rolling(sma).mean().to_numpy()
        reg = regime.to_numpy()
        cv = c.to_numpy()
        pos = np.zeros(len(c))
        st = 0
        for i in range(len(c)):
            if np.isnan(cv[i]) or np.isnan(m[i]) or np.isnan(r[i]):
                st = 0
            elif st == 1 and (r[i] > exit_ or cv[i] < m[i] * 0.9):
                st = 0
            elif st == 0 and r[i] < entry and cv[i] > m[i] and reg[i]:
                st = 1
            pos[i] = st
        w = (vol_target / vol30(c)).clip(upper=1.0) if vol_target else pd.Series(1.0, index=c.index)
        out[p] = (pd.Series(pos, index=c.index) * w).fillna(0)
    return out


def hold_weights(data):
    return {p: data[p].close.notna().astype(float) for p in PAIRS}


def combine(*sleeves, split=None):
    """Plusieurs stratégies se partagent le capital (50/50 par défaut)."""
    split = split or [1 / len(sleeves)] * len(sleeves)
    return {p: sum(s[p] * k for s, k in zip(sleeves, split)) for p in PAIRS}


# ------------------------------------------------------------------ moteur
def run(data, weights, lev=1.0, start=None, end=None, wallet=1000.0):
    """Retourne un DataFrame journalier : equity, pnl, exposition, liquidations."""
    idx = data["BTC"].index
    n = len(PAIRS)
    pnl_total = np.zeros(len(idx))
    expo = np.zeros(len(idx))
    liq_count = np.zeros(len(idx))
    for p in PAIRS:
        df = data[p]
        o, h, l = df.open.to_numpy(), df.high.to_numpy(), df.low.to_numpy()
        w_dec = weights[p].reindex(idx).fillna(0).to_numpy()
        held = np.concatenate([[0.0], w_dec[:-1]])  # décidé hier, exécuté à l'ouverture d'aujourd'hui
        prev = np.concatenate([[0.0], held[:-1]])
        o_next = np.concatenate([o[1:], [np.nan]])
        r = np.where(np.isnan(o_next) | np.isnan(o), 0.0, o_next / o - 1)
        adverse = np.where(held > 0, np.nan_to_num((o - l) / o), 0.0)
        liq = (held > 0) & (adverse * lev >= 0.9)
        pnl = held * r * lev - np.abs(held - prev) * FEE * lev - held * lev * FUNDING_DAY
        pnl = np.where(liq, -held, pnl)
        pnl_total += pnl / n
        expo += held / n
        liq_count += liq
    res = pd.DataFrame({"pnl": pnl_total, "expo": expo, "liq": liq_count}, index=idx)
    if start:
        res = res[res.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        res = res[res.index < pd.Timestamp(end, tz="UTC")]
    res["equity"] = wallet * (1 + res.pnl.clip(lower=-1)).cumprod()
    return res


def metrics(res: pd.DataFrame) -> dict:
    if res.empty:
        return {}
    eq = res.equity
    start_val = eq.iloc[0] / (1 + res.pnl.iloc[0])
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    total = eq.iloc[-1] / start_val - 1
    dd = (eq / np.maximum.accumulate(np.concatenate([[start_val], eq.to_numpy()]))[1:] - 1).min()
    sd = res.pnl.std()
    return {
        "total_pct": total * 100,
        "cagr_pct": ((1 + total) ** (365 / days) - 1) * 100 if total > -1 else -100,
        "maxdd_pct": dd * 100,
        "sharpe": res.pnl.mean() / sd * np.sqrt(365) if sd > 0 else 0.0,
        "liq": int(res.liq.sum()),
        "expo_pct": res.expo.mean() * 100,
    }


def yearly(data, weights, lev=1.0) -> dict[int, dict]:
    return {y: metrics(run(data, weights, lev, f"{y}-01-01", f"{y + 1}-01-01")) for y in YEARS}
