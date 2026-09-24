"""
Lit les rapports HTML du testeur de stratégie MT5 (.htm, souvent en UTF-16)
et affiche les chiffres clés de chacun.

Usage :
    python .claude/skills/mt5-backtest/scripts/parse_report.py "<dossier des rapports>"
"""

import html
import re
import sys
from pathlib import Path

# Libellés français et anglais des rapports MT5
KEYS = {
    "Bénéfice net total": "Profit net", "Total Net Profit": "Profit net",
    "Facteur de profit": "Facteur de profit", "Profit Factor": "Facteur de profit",
    "Drawdown relatif de l'équité": "Drawdown relatif (equity)", "Equity Drawdown Relative": "Drawdown relatif (equity)",
    "Total des trades": "Trades", "Total Trades": "Trades",
    "Trades gagnants (% du total)": "Trades gagnants", "Profit Trades (% of total)": "Trades gagnants",
    "Paiement espéré": "Gain moyen par trade", "Expected Payoff": "Gain moyen par trade",
}


def read(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def summary(text: str) -> dict:
    cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", text, re.S)]
    out = {}
    for i, c in enumerate(cells[:-1]):
        label = c.rstrip(":").strip()
        if label in KEYS and KEYS[label] not in out:
            out[KEYS[label]] = cells[i + 1]
    return out


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    files = sorted(folder.glob("*.htm*"))
    if not files:
        raise SystemExit(f"Aucun rapport .htm dans {folder}")
    for f in files:
        s = summary(read(f))
        print(f"\n== {f.stem}")
        if not s:
            print("   (rapport vide : le test n'a peut-être fait aucun trade)")
        for k, v in s.items():
            print(f"   {k:28s} {v}")


if __name__ == "__main__":
    main()
