"""
Exporte l'historique H1 du MetaTrader 5 ouvert sur ce PC (Windows) en CSV,
au format lu par mt5/lab_ftmo.py (colonne time_server = heure du serveur).

Lecture seule : ce script n'envoie aucun ordre.

Usage :
    python .claude/skills/mt5-backtest/scripts/export_mt5.py --out mt5/data/ftmo --from 2023-01-01
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

SYMBOLS = [
    "XAUUSD", "XAGUSD", "US100.cash", "US30.cash", "US500.cash", "GER40.cash", "UK100.cash", "JP225.cash",
    "USOIL.cash", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "EURGBP", "BTCUSD", "ETHUSD",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="mt5/data/ftmo")
    ap.add_argument("--from", dest="start", default="2023-01-01")
    ap.add_argument("--symbols", nargs="*", default=SYMBOLS)
    ap.add_argument("--terminal", help="chemin de terminal64.exe si plusieurs MT5 sont installés")
    a = ap.parse_args()

    ok = mt5.initialize(a.terminal) if a.terminal else mt5.initialize()
    if not ok:
        raise SystemExit(f"Impossible de se connecter à MT5 ({mt5.last_error()}). Ouvrez MT5 et connectez-vous.")
    info = mt5.account_info()
    print(f"Connecté à {mt5.terminal_info().company}, serveur {info.server if info else '?'}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = datetime.now(timezone.utc)
    done = 0
    for sym in a.symbols:
        if not mt5.symbol_select(sym, True):
            print(f"{sym:12s} : absent chez ce courtier, ignoré")
            continue
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, start, end)
        if rates is None or len(rates) == 0:
            print(f"{sym:12s} : pas d'historique ({mt5.last_error()}). Ouvrez un graphique H1 de ce symbole puis relancez.")
            continue
        df = pd.DataFrame(rates)
        # Le paquet MetaTrader5 renvoie l'heure du serveur du courtier, encodée comme de l'UTC
        df = df.rename(columns={"time": "time_server", "spread": "spread_points"})
        df[["time_server", "open", "high", "low", "close", "spread_points"]].to_csv(out / f"{sym}_H1.csv", index=False)
        first = datetime.fromtimestamp(int(df.time_server.iloc[0]), timezone.utc)
        print(f"{sym:12s} : {len(df):6d} bougies depuis {first:%Y-%m-%d}")
        done += 1
    mt5.shutdown()
    print(f"\n{done} symboles exportés dans {out.resolve()}")


if __name__ == "__main__":
    main()
