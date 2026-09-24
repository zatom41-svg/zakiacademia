"""
Construit panel/index.html (page autonome) à partir de panel/template.html en y
injectant :
  - les bougies journalières OKX des 8 paires (le simulateur tourne dans la page)
  - les résultats Freqtrade année par année (results/yearly.json)
  - le Monte Carlo 6 mois (results/montecarlo_6mois.json)

Usage (depuis freqtrade/) : python tools/build_panel.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DATA = ROOT / "user_data" / "data" / "okx" / "futures"
PAIRS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]


def read_json(name: str) -> list:
    path = ROOT / "results" / name
    return json.loads(path.read_text()) if path.exists() else []


def main() -> None:
    frames = {p: pd.read_feather(DATA / f"{p}_USDT_USDT-1d-futures.feather").set_index("date") for p in PAIRS}
    idx = frames["BTC"].index
    candles = {"dates": [d.strftime("%Y-%m-%d") for d in idx], "pairs": {}}
    for p, df in frames.items():
        df = df.reindex(idx)
        candles["pairs"][p] = {
            k: [None if pd.isna(v) else float(f"{v:.6g}") for v in df[k]]
            for k in ("open", "high", "low", "close")
        }

    yearly = [{k: r[k] for k in ("strategy", "leverage", "period", "profit_pct", "max_drawdown_pct", "trades", "liquidations")}
              for r in read_json("yearly.json") if "error" not in r]
    mc = read_json("montecarlo_6mois.json")

    tpl = (REPO / "panel" / "template.html").read_text(encoding="utf-8")
    html = (tpl.replace("/*__CANDLES__*/null", json.dumps(candles, separators=(",", ":")))
               .replace("/*__YEARLY__*/null", json.dumps(yearly, separators=(",", ":")))
               .replace("/*__MC__*/null", json.dumps(mc, separators=(",", ":"))))
    out = REPO / "panel" / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out} ({len(html) / 1024:.0f} Ko, {len(idx)} jours, {len(yearly)} backtests Freqtrade)")


if __name__ == "__main__":
    main()
