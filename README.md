# chartroom-scanner

Signal-only scanner for market-wide crash cascades and rebound setups on Hyperliquid perpetuals.

- Runs every 5 minutes on GitHub Actions (scheduled runs can lag 5-15 minutes).
- Reads public 5-minute candles from the Hyperliquid info API.
- Opens one GitHub issue per new event or setup (labels `event`, `setup`).
- No account access, no keys, no order code. It cannot trade.

Not financial advice.
