# hermes-aktier

Semi-automated paper trading on Nasdaq Stockholm, driven by the
[Hermes agent](https://github.com/NousResearch/hermes-agent).

**The experiment:** how well can an AI judge buy/sell decisions based on
market data and news? Hermes analyzes, proposes trades with reasoning via
Telegram, and the human approves or rejects. All trades fill a simulated
portfolio first — real money only if paper results beat the index.

## How it works

```
cron (08:45 + 17:30 CET, weekdays)
  └─> Hermes wakes up and runs the "aktier" skill:
      1. scripts/fetch_data.py   → prices for the watchlist (JSON)
      2. scripts/fetch_news.py   → filtered news from MFN/Placera RSS   [TODO]
      3. Hermes analyzes and proposes trades (strict JSON + reasoning)
      4. scripts/portfolio.py    → validates risk rules, records proposals [TODO]
      5. Proposals sent to Telegram → user approves/rejects
      6. Approved proposals fill the paper portfolio (simulated fees)
```

Risk rules live in `portfolio.py` (code), not in the LLM prompt.
The AI analyzes — the code enforces limits.

## Status

- [ ] Step 1: `fetch_data.py` — batched price fetch via yfinance
- [ ] Step 2: `fetch_news.py` — MFN + Placera RSS, filtered by watchlist
- [ ] Step 3: SQLite schema (portfolio, trades, decisions, snapshots)
- [ ] Step 4: `portfolio.py` — propose/approve/reject CLI with risk rules
- [ ] Step 5: Hermes skill (`skills/aktier/SKILL.md`) — full analysis prompt
- [ ] Step 6: Benchmark portfolio (buy-and-hold OMXS30 index)
- [ ] Step 7: Hermes cron jobs + Telegram delivery

## Install (Debian LXC where Hermes runs)

```bash
git clone <this-repo> ~/hermes-aktier
cd ~/hermes-aktier
pip3 install -r requirements.txt --break-system-packages

# quick test
python3 scripts/fetch_data.py VOLV-B.ST

# register the skill with Hermes
ln -s ~/hermes-aktier/skills/aktier ~/.hermes/skills/aktier
```

## Risk rules (hard-coded, never up to the LLM)

| Rule | Value |
|---|---|
| Max position size | 10% of portfolio |
| Max holdings | 8 |
| Universe | Large/Mid Cap Nasdaq Stockholm (watchlist.json) |
| Stop loss | -8% from entry → auto-sell proposal |
| Circuit breaker | -15% total → halt trading, alert via Telegram |
| Simulated courtage | 0.25% per trade |
| Simulated slippage | 0.2% per trade |

## Evaluation

Paper portfolio vs a benchmark portfolio that buys an OMXS30 index fund on
day 1 and holds. Hermes must beat the benchmark after simulated fees over
3 months, with max drawdown under 15%, before any real money is involved.

See `PLAN.md` (Swedish) for the full project plan.

## Disclaimer

This is a hobby experiment, not financial advice. Real-money phase risks
only capital the owner can afford to lose.
