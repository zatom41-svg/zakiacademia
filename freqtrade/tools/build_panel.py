"""
Construit panel/index.html (page autonome) à partir de panel/template.html :
  - injecte les bougies journalières OKX des 8 paires (pour le simulateur)
  - injecte les résultats Freqtrade de results/summary.json (tableau validé)

Usage (depuis freqtrade/) : python tools/build_panel.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DATA = ROOT / "user_data" / "data" / "okx" / "futures"
PAIRS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]


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

    summary_path = ROOT / "results" / "summary.json"
    summary = []
    if summary_path.exists():
        for r in json.loads(summary_path.read_text()):
            r.pop("equity_daily", None)
            summary.append(r)

    mc_path = ROOT / "results" / "montecarlo_6mois.json"
    mc = json.loads(mc_path.read_text()) if mc_path.exists() else []

    tpl = (REPO / "panel" / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__CANDLES__*/null", json.dumps(candles, separators=(",", ":"))).replace(
        "/*__SUMMARY__*/null", json.dumps(summary, separators=(",", ":"), default=str)
    ).replace("/*__MC__*/null", json.dumps(mc, separators=(",", ":")))
    out = REPO / "panel" / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"{out} ({len(html) / 1024:.0f} Ko, {len(idx)} jours, {len(summary)} backtests)")


if __name__ == "__main__":
    main()
