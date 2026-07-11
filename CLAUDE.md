# CLAUDE.md — hermes-aktier

Context for AI assistants working in this repo.

## What this is

Semi-automated paper trading experiment on Nasdaq Stockholm. The Hermes
agent (NousResearch/hermes-agent) analyzes market data + news twice a day
via cron, proposes trades with reasoning over Telegram, and Jesper
approves/rejects. Approved trades fill a simulated portfolio (SQLite).
Real money only if paper results beat OMXS30 over 3 months.

The point of the experiment: measure how good an LLM is at buy/sell
decisions. Logging the reasoning behind every decision matters more than
the returns themselves.

## Owner context

- Jesper: advanced hardware skills, beginner–intermediate software. Learning
  by building. Explain WHY, not just what.
- Respond in Swedish. Code and code comments in English.
- Work iteratively — one step at a time, small testable pieces. Don't
  build ahead of the current step in README's status checklist.
- Prefer simple solutions over clever ones.

## Architecture principles (do not violate)

1. **Risk rules live in code, never in prompts.** portfolio.py enforces
   max position 10%, max 8 holdings, stop loss -8%, circuit breaker -15%,
   watchlist-only tickers. The LLM analyzes and proposes — it must not be
   able to bypass these.
2. **The human decides.** Nothing executes without explicit approval via
   Telegram. No auto-trading, no broker APIs (Swedish brokers don't offer
   usable ones anyway).
3. **Everything is logged.** Every proposal stores: timestamp, price at
   decision, full reasoning, news context. This is the experiment's data.
4. **Simulate real costs.** Paper trades apply 0.25% courtage + 0.2%
   slippage. Results without costs are lies.
5. **Benchmark or it didn't happen.** Performance is always measured
   against a buy-and-hold OMXS30 portfolio started on day 1.

## Layout

```
scripts/fetch_data.py     # price fetch, yfinance, batch, JSON to stdout
scripts/watchlist.json    # ~25 Large Cap .ST tickers — the only allowed universe
scripts/fetch_news.py     # TODO step 2: MFN + Placera RSS, watchlist-filtered
scripts/portfolio.py      # TODO step 4: SQLite CLI — status/propose/approve/reject
skills/aktier/SKILL.md    # Hermes skill (agentskills.io format), symlinked to ~/.hermes/skills/
data/                     # SQLite + logs, gitignored — never commit state
PLAN.md                   # full project plan (Swedish)
```

## Conventions

- Python 3.11+, stdlib + yfinance/feedparser only. No frameworks.
- Scripts are standalone CLIs: JSON to stdout, errors per-item (one bad
  ticker must never kill a run).
- Deployment target: Debian LXC on Proxmox, same container as Hermes.
  Install: `pip3 install -r requirements.txt --break-system-packages`.
- Test commands:
  - `python3 scripts/fetch_data.py VOLV-B.ST` (single ticker smoke test)
  - `python3 scripts/fetch_data.py` (full watchlist, ~10 s)

## Current status

See the checklist in README.md. Update it when a step is completed.
