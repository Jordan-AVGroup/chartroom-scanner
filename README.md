# chartroom-scanner

Signal-only scanner for market-wide crash cascades and rebound setups on Hyperliquid perpetuals.

- Runs every 5 minutes on GitHub Actions (scheduled runs can lag 5-15 minutes).
- Reads public 5-minute candles from the Hyperliquid info API.
- Opens one GitHub issue per new event or setup (labels `event`, `setup`).
- No account access, no keys, no order code. It cannot trade.

Not financial advice.

## Paper mode

`paper.py` simulates fills at the live Hyperliquid mid price for every fresh signal and closes them after the strategy's hold (24h cascade, 48h thrust). Ledger: `paper.json`.

- `micro`: $20 start, one cascade coin per event (what a $20 account can do).
- `full`: $1,000 reference book, every cascade coin at equity/12 x 0.5 (the diversified version).
- `thrust`: probation strategy, tracked per trade only.

Costs: 7.5bp per side (taker plus slippage). Funding ignored.
