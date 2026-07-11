#!/usr/bin/env python3
"""Fetch daily prices for a watchlist via yfinance; emit JSON to stdout.

Usage:
    python3 scripts/fetch_data.py            # full watchlist
    python3 scripts/fetch_data.py VOLV-B.ST  # single ticker (smoke test)

Exit codes:
    0 -- at least one ticker succeeded
    1 -- yfinance/network failure, or all tickers failed
    2 -- configuration error (bad CLI, missing/invalid watchlist)
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

STOCKHOLM = ZoneInfo("Europe/Stockholm")
SCRIPT_DIR = Path(__file__).resolve().parent
WATCHLIST_PATH = SCRIPT_DIR / "watchlist.json"


def log(msg: str) -> None:
    print(f"[fetch_data] {msg}", file=sys.stderr)


def parse_args(argv: list[str]) -> str | None:
    if len(argv) == 1:
        return None
    if len(argv) == 2:
        return argv[1]
    log("usage: fetch_data.py [TICKER]")
    sys.exit(2)


def load_watchlist(path: Path) -> list[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log(f"watchlist error: {path} not found")
        sys.exit(2)
    except json.JSONDecodeError as e:
        log(f"watchlist error: invalid JSON: {e}")
        sys.exit(2)
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        log("watchlist error: expected a JSON array of ticker strings")
        sys.exit(2)
    return raw


def download(tickers: list[str]) -> pd.DataFrame:
    return yf.download(
        tickers,
        period="1y",
        interval="1d",
        group_by="ticker",
        progress=False,
        threads=True,
        auto_adjust=True,
    )


def extract_one(frame: pd.DataFrame, ticker: str) -> dict:
    try:
        # Single-ticker downloads return a flat column index; multi-ticker
        # returns a MultiIndex keyed by ticker at level 0. Normalize.
        if isinstance(frame.columns, pd.MultiIndex):
            sub = frame[ticker] if ticker in frame.columns.levels[0] else pd.DataFrame()
        else:
            sub = frame

        if sub.empty:
            return {"ticker": ticker, "error": "no data returned"}

        sub = sub.dropna(subset=["Close"])
        if len(sub) < 2:
            return {"ticker": ticker, "error": "insufficient history"}

        last = float(sub["Close"].iloc[-1])
        prev = float(sub["Close"].iloc[-2])
        change_pct = (last / prev - 1) * 100
        volume = int(sub["Volume"].iloc[-1])
        w52_high = float(sub["Close"].max())
        w52_low = float(sub["Close"].min())
        as_of = sub.index[-1].date().isoformat()

        return {
            "ticker": ticker,
            "as_of": as_of,
            "last": round(last, 2),
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "w52_high": round(w52_high, 2),
            "w52_low": round(w52_low, 2),
        }
    except Exception as e:
        return {"ticker": ticker, "error": f"{type(e).__name__}: {e}"}


def build_envelope(results: list[dict]) -> dict:
    return {
        "fetched_at": datetime.now(STOCKHOLM).isoformat(timespec="seconds"),
        "count": len(results),
        "results": results,
    }


def main(argv: list[str]) -> int:
    ticker = parse_args(argv)
    tickers = [ticker] if ticker else load_watchlist(WATCHLIST_PATH)

    try:
        frame = download(tickers)
    except Exception as e:
        log(f"fetch failed: {type(e).__name__}: {e}")
        return 1

    if frame.empty:
        log("fetch failed: no data returned by yfinance")
        return 1

    results = [extract_one(frame, t) for t in tickers]
    print(json.dumps(build_envelope(results), indent=2))

    if all("error" in r for r in results):
        log("all tickers failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
