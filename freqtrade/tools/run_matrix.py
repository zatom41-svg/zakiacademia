"""
Lance une grille de backtests Freqtrade : stratégies x leviers x périodes,
et écrit un résumé dans results/summary.json (lu par le panel).

Usage (depuis le dossier freqtrade/) :
    python tools/run_matrix.py
    python tools/run_matrix.py --strategies MomentumTrend --leverages 1 3 10
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats

ROOT = Path(__file__).resolve().parents[1]
USERDIR = ROOT / "user_data"
RESULTS = ROOT / "results"

DEFAULT_STRATEGIES = ["MomentumTrend", "SupertrendTrend", "MeanReversionBB", "SqueezeBreakout"]
DEFAULT_LEVERAGES = [1, 3, 5, 10, 20]
PERIODS = {
    # Période d'apprentissage (optimisation) et période de validation, jamais vue
    "in_sample_2022_2024": "20220101-20250101",
    "out_of_sample_2025_2026": "20250101-",
}


def run_one(strategy: str, leverage: float, period: str, timerange: str, extra_cfg: dict) -> dict:
    out_dir = RESULTS / "raw" / f"{strategy}_x{leverage:g}_{period}"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"za_leverage": leverage, **extra_cfg}, f)
        overlay = f.name

    cmd = [
        sys.executable, "-m", "freqtrade", "backtesting",
        "--userdir", str(USERDIR),
        "-c", str(USERDIR / "config.json"), "-c", overlay,
        "--strategy", strategy,
        "--timerange", timerange,
        "--enable-protections",
        "--cache", "none",
        "--export", "trades",
        "--backtest-directory", str(out_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        return {"strategy": strategy, "leverage": leverage, "period": period,
                "error": proc.stderr[-2000:]}

    stats = load_backtest_stats(out_dir)
    s = stats["strategy"][strategy]
    trades = load_backtest_data(out_dir, strategy)
    liquidations = int((trades["exit_reason"] == "liquidation").sum()) if len(trades) else 0

    return {
        "strategy": strategy,
        "leverage": leverage,
        "period": period,
        "timerange": timerange,
        "start_balance": s["starting_balance"],
        "final_balance": s["final_balance"],
        "profit_pct": s["profit_total"] * 100,
        "cagr_pct": (s.get("cagr") or 0) * 100,
        "max_drawdown_pct": s.get("max_drawdown_account", 0) * 100,
        "trades": s["total_trades"],
        "winrate_pct": (s["wins"] / s["total_trades"] * 100) if s["total_trades"] else 0,
        "profit_factor": s.get("profit_factor"),
        "sharpe": s.get("sharpe"),
        "liquidations": liquidations,
        "market_change_pct": s.get("market_change", 0) * 100,
        "equity_daily": [
            {"date": d["date"], "profit_abs": d["abs_profit"]}
            for d in s.get("daily_profit", [])
        ] if isinstance(s.get("daily_profit"), list) and s["daily_profit"] and isinstance(s["daily_profit"][0], dict)
        else [{"date": d[0], "profit_abs": d[1]} for d in s.get("daily_profit", [])],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="+", default=DEFAULT_STRATEGIES)
    ap.add_argument("--leverages", nargs="+", type=float, default=DEFAULT_LEVERAGES)
    ap.add_argument("--risk", type=float, default=0.02, help="risque par trade (0.02 = 2 %%)")
    ap.add_argument("--out", default="summary.json")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    rows = []
    for strategy in args.strategies:
        for lev in args.leverages:
            for period, tr in PERIODS.items():
                r = run_one(strategy, lev, period, tr, {"za_risk_per_trade": args.risk})
                rows.append(r)
                if "error" in r:
                    print(f"ERREUR {strategy} x{lev:g} {period}: {r['error'][-300:]}")
                else:
                    print(f"{strategy:16s} x{lev:<4g} {period:24s} profit {r['profit_pct']:8.1f}%  "
                          f"DD {r['max_drawdown_pct']:5.1f}%  trades {r['trades']:4d}  "
                          f"liq {r['liquidations']}")
    (RESULTS / args.out).write_text(json.dumps(rows, indent=1, default=str))
    print(f"Résumé écrit dans {RESULTS / args.out}")


if __name__ == "__main__":
    main()
