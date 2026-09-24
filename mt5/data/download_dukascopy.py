"""
Télécharge les bougies HORAIRES (prix BID) de Dukascopy pour les actifs
disponibles chez FTMO, et les enregistre en CSV (heure UTC).

Usage : python mt5/data/download_dukascopy.py --out dossier --start 2022-01
Le serveur limite le débit : le script attend et réessaie tout seul.
"""

import argparse
import lzma
import struct
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# symbole Dukascopy -> (nom FTMO, diviseur de prix)
SYMBOLS = {
    "EURUSD": ("EURUSD", 1e5), "GBPUSD": ("GBPUSD", 1e5), "USDJPY": ("USDJPY", 1e3),
    "AUDUSD": ("AUDUSD", 1e5), "USDCAD": ("USDCAD", 1e5), "USDCHF": ("USDCHF", 1e5),
    "NZDUSD": ("NZDUSD", 1e5), "EURJPY": ("EURJPY", 1e3), "GBPJPY": ("GBPJPY", 1e3),
    "EURGBP": ("EURGBP", 1e5), "XAUUSD": ("XAUUSD", 1e3), "XAGUSD": ("XAGUSD", 1e3),
    "USATECHIDXUSD": ("US100.cash", 1e3), "USA30IDXUSD": ("US30.cash", 1e3),
    "USA500IDXUSD": ("US500.cash", 1e3), "DEUIDXEUR": ("GER40.cash", 1e3),
    "GBRIDXGBP": ("UK100.cash", 1e3), "JPNIDXJPY": ("JP225.cash", 1e3),
    "LIGHTCMDUSD": ("USOIL.cash", 1e3),
}
URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/BID_candles_hour_1.bi5"


def fetch(url: str, cache: Path) -> bytes | None:
    if cache.exists():
        return cache.read_bytes() or None
    time.sleep(30)  # rythme régulier : le serveur bloque au-delà d'environ 1 requête / 20 s
    for attempt in range(200):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read()
                cache.write_bytes(data)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cache.write_bytes(b"")
                return None
            time.sleep(min(60 * (attempt + 1), 300))  # 429 : bloqué, on patiente de plus en plus
        except Exception:
            time.sleep(10)
    raise RuntimeError(f"échec : {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", default="2022-01")
    priority = ["XAUUSD", "USATECHIDXUSD", "USA30IDXUSD", "USA500IDXUSD", "DEUIDXEUR", "EURUSD", "GBPUSD", "USDJPY"]
    ap.add_argument("--symbols", nargs="*", default=priority + [s for s in SYMBOLS if s not in priority])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    y0, m0 = map(int, a.start.split("-"))
    now = datetime.now(timezone.utc)
    for sym in a.symbols:
        name, div = SYMBOLS[sym]
        target = out / f"{name}_H1.csv"
        if target.exists():
            continue
        rows = []
        y, m = y0, m0
        while (y, m) <= (now.year, now.month):
            cache = out / "cache" / f"{sym}_{y}_{m:02d}.bi5"
            cache.parent.mkdir(exist_ok=True)
            data = fetch(URL.format(sym=sym, y=y, m=m - 1), cache)  # mois numérotés à partir de 0
            if data:
                raw = lzma.decompress(data)
                base = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
                for i in range(len(raw) // 24):
                    t, o, c, lo, hi, v = struct.unpack(">IIIIIf", raw[i * 24:(i + 1) * 24])
                    if v > 0:  # heures de marché fermé : volume nul
                        rows.append(f"{int(base + t)},{o / div},{hi / div},{lo / div},{c / div}")
            print(f"  {name} {y}-{m:02d}", flush=True)
            m += 1
            if m > 12:
                y, m = y + 1, 1
        target.write_text("time,open,high,low,close\n" + "\n".join(rows))
        print(f"{name}: {len(rows)} bougies", flush=True)


if __name__ == "__main__":
    main()
