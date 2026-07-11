# Design: `scripts/fetch_data.py` (Step 1)

**Status:** Approved 2026-07-11
**Related:** README.md Step 1, CLAUDE.md ("Layout" section)

## Purpose

A standalone CLI that fetches daily price data for a fixed watchlist of ~25
Large Cap Nasdaq Stockholm tickers via `yfinance`, and emits a single JSON
document to stdout. Downstream consumers (Hermes agent, later
`portfolio.py`) parse this JSON to make decisions or value the portfolio.

The script is deliberately small, dependency-light (stdlib + `yfinance`
only), and follows the repo convention: standalone CLI, JSON to stdout,
per-item error handling that never lets one bad ticker kill the run.

## CLI

```
python3 scripts/fetch_data.py            # fetch the full watchlist
python3 scripts/fetch_data.py VOLV-B.ST  # fetch a single ticker (smoke test)
```

- The watchlist is read from `scripts/watchlist.json`, resolved relative
  to the script's own location (so `cron` can run it from any cwd).
- If a ticker is passed as the first CLI argument, the watchlist is
  skipped and only that ticker is fetched.
- JSON goes to stdout. Log/error messages go to stderr, prefixed
  `[fetch_data]`.
- Uses plain `sys.argv` — no `argparse`. Keeps the surface minimal.

## `scripts/watchlist.json`

A flat JSON array of ticker strings. This is the only "universe" the
agent is allowed to trade — enforced later by `portfolio.py`.

```json
[
  "VOLV-B.ST", "ATCO-A.ST", "SAND.ST", "SKF-B.ST", "ALFA.ST",
  "ERIC-B.ST", "HM-B.ST", "ESSITY-B.ST", "SCA-B.ST", "SWMA.ST",
  "SEB-A.ST", "SHB-A.ST", "SWED-A.ST", "NDA-SE.ST", "INVE-B.ST",
  "AZN.ST", "ASSA-B.ST", "TEL2-B.ST", "TELIA.ST", "EVO.ST",
  "SAAB-B.ST", "BOL.ST", "GETI-B.ST", "HEXA-B.ST", "NIBE-B.ST"
]
```

Sector spread (informational, not encoded in the file):

- **Industrials:** VOLV-B, ATCO-A, SAND, SKF-B, ALFA, ASSA-B, HEXA-B,
  SAAB-B
- **Banks/finance:** SEB-A, SHB-A, SWED-A, NDA-SE, INVE-B
- **Consumer:** HM-B, ESSITY-B, SCA-B, SWMA
- **Telecom:** ERIC-B, TEL2-B, TELIA
- **Pharma/health:** AZN, GETI-B
- **Other:** EVO (gaming), BOL (base metals), NIBE-B (heating)

Why flat strings (not objects with `name`/`sector`): nothing in the
current step or the next few needs those fields. Adding metadata later
is trivial.

## yfinance flow

One batched call, then in-process extraction:

```python
data = yf.download(
    tickers,
    period="1y",
    interval="1d",
    group_by="ticker",
    progress=False,
    threads=True,
    auto_adjust=True,
)
```

For each ticker, from the resulting frame:

| Field         | Source                                       |
| ------------- | -------------------------------------------- |
| `last`        | `data[t]["Close"].iloc[-1]`                  |
| `change_pct`  | `(last / data[t]["Close"].iloc[-2] - 1)*100` |
| `volume`      | `data[t]["Volume"].iloc[-1]`                 |
| `w52_high`    | `data[t]["Close"].max()`                     |
| `w52_low`     | `data[t]["Close"].min()`                     |
| `as_of`       | index (date) of the last row                 |

Rounding in output:

- `last`, `w52_high`, `w52_low` → 2 decimals
- `change_pct` → 2 decimals
- `volume` → integer

`auto_adjust=True` corrects historical prices for splits and dividends
so `change_pct` reflects a real move, not a corporate action.

If a ticker has fewer than 2 rows in the returned frame (delisted, new
listing, holiday edge case) → mark as `error: "insufficient history"`,
do not crash.

## Output schema

Envelope with run-level metadata and a flat `results` list where
successful items and errors coexist.

```json
{
  "fetched_at": "2026-07-11T18:30:12+02:00",
  "count": 25,
  "results": [
    {
      "ticker": "VOLV-B.ST",
      "as_of": "2026-07-10",
      "last": 267.50,
      "change_pct": 1.23,
      "volume": 3241500,
      "w52_high": 289.10,
      "w52_low": 214.60
    },
    {
      "ticker": "RUBBISH.ST",
      "error": "no data returned"
    }
  ]
}
```

Rules:

- `fetched_at` is ISO-8601 with the local timezone (Europe/Stockholm).
- `count` equals `len(results)`. Trivial redundancy that lets consumers
  sanity-check the payload without iterating.
- Successful item = all Section-3 fields present, no `error` key.
- Failed item = only `ticker` and `error` (string). No empty fields —
  consumers can safely check `"error" in item`.
- `as_of` is **per item**, not per envelope: different tickers can
  legitimately have different last-trading dates (delistings, halts).

## Error handling & exit codes

**Per-ticker (soft — reported inside output, exit 0 if any succeed):**

- No data returned → `error: "no data returned"`
- Fewer than 2 trading days in the frame → `error: "insufficient history"`
- Unexpected exception during extraction → `error: "<ExceptionType>: <msg>"`

**Run-level (hard — non-zero exit):**

| Condition                                          | Exit | To stderr                          |
| -------------------------------------------------- | ---- | ---------------------------------- |
| `watchlist.json` missing or invalid JSON           | 2    | `[fetch_data] watchlist error: …` |
| CLI arg malformed (e.g. multiple positional args)  | 2    | `[fetch_data] usage: …`            |
| yfinance/network failure — no data for any ticker  | 1    | `[fetch_data] fetch failed: …`     |
| All tickers returned soft errors                   | 1    | `[fetch_data] all tickers failed`  |

Why split 1 from 2: cron/monitoring should treat them differently.
Exit 2 = "fix the config, human." Exit 1 = "retry later, transient."

**Logging:** stderr only in the failure paths. No info-level logs in the
happy path — keeps cron output small. stdout is *always* strictly valid
JSON (even when exiting 1 after per-ticker failures).

## Testing

Manual smoke tests only for Step 1 (script is ~80–120 lines of I/O
against an external API — mocking would cost more than the script).

Unit tests will arrive with `portfolio.py` (Step 4) where there is pure
logic worth isolating.

| Test | Command | Expected |
| ---- | ------- | -------- |
| Single ticker | `python3 scripts/fetch_data.py VOLV-B.ST` | `count: 1`, plausible price, exit 0 |
| Full watchlist | `python3 scripts/fetch_data.py` | `count: 25`, mostly successes, exit 0, runs in ≲10 s |
| Broken ticker | `python3 scripts/fetch_data.py RUBBISH.ST` | `count: 1`, error item, exit 1 |
| Missing watchlist | rename watchlist and rerun | stderr msg, exit 2 |
| JSON validity | `python3 scripts/fetch_data.py \| python3 -m json.tool > /dev/null && echo OK` | prints `OK` |

## Non-goals for this step

Explicitly out of scope — these belong to later steps or are simply not
needed:

- Moving averages, RSI, or other technical indicators (LLM can reason
  without them; revisit if prompt quality shows a gap).
- Intraday prices (daily close is enough for a 2×/day cron cadence).
- Caching or a local price database (`portfolio.py` handles persistence;
  this script is stateless by design).
- Retry logic with backoff (transient failures → cron retries next run).
- Real-time streaming.
- Any HTTP server / API wrapper.
