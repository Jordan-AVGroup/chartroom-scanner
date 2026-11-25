"""Paper trading ledger. No orders, no keys: fills are simulated at the live Hyperliquid mid price.

Two books, both fed by the same live signals:
  micro: $20 start, one cascade coin per event at min(max(11.5, 0.55*eq), eq), skipped if a position is open (what a $20 account can do)
  full:  $1,000 reference book, every cascade coin at equity/12 x 0.5 (the diversified version the backtest validated)
Breadth thrust (probation) is tracked as its own per-trade record only, not in either book.
Cost per side: 4.5bp taker + 3bp slippage. Funding is ignored (small over 24h, noted in README).
"""
import json, os, time, requests, datetime as dt
COST = 0.00075; P = 'paper.json'
L = json.load(open(P)) if os.path.exists(P) else dict(started=int(time.time()), books=dict(micro=dict(eq=20.0, start=20.0), full=dict(eq=1000.0, start=1000.0)), open=[], closed=[], seen=[])
A = json.load(open('alert.json')); now = int(time.time())
mids = {k: float(v) for k, v in requests.post('https://api.hyperliquid.xyz/info', json={'type': 'allMids'}, timeout=30).json().items()}
f = lambda t: dt.datetime.fromtimestamp(t, dt.UTC).strftime('%b %d %H:%M UTC')
log = []
# 1) close anything past its hold
for p in [p for p in L['open'] if now >= p['exit_ts'] and p['coin'] in mids]:
    px = mids[p['coin']]; r = px / p['entry'] - 1 - 2 * COST; pnl = p['usd'] * r
    if p['book'] in L['books']: L['books'][p['book']]['eq'] += pnl
    p.update(exit=px, exit_t=now, ret=round(r, 5), pnl=round(pnl, 4)); L['open'].remove(p); L['closed'].append(p)
    log.append(f"CLOSE {p['book']} {p['coin']} {p['entry']:.6g} -> {px:.6g}  {r*100:+.2f}%  ${pnl:+.2f}")
# 2) open new fresh signals (deduped per event+coin+book)
for s in A['fresh']:
    c = s['coin']
    if c not in mids: continue
    hold = 24 if s['strategy'] == 'cascade' else 48
    books = ['micro', 'full'] if s['strategy'] == 'cascade' else ['thrust']
    for b in books:
        key = f"{b}-{s['event_t']}-{c}"
        if key in L['seen']: continue
        if b == 'micro':
            eq = L['books']['micro']['eq']
            if any(p['book'] == 'micro' for p in L['open']) or any(k.startswith(f"micro-{s['event_t']}-") for k in L['seen']): continue
            usd = min(max(11.5, 0.55 * eq), eq)
            if usd < 11: continue
        elif b == 'full': usd = L['books']['full']['eq'] * 0.5 / 12
        else: usd = 100.0
        L['seen'].append(key)
        L['open'].append(dict(book=b, strategy=s['strategy'], coin=c, event_t=s['event_t'], entry=mids[c], entry_t=now, lag_min=s['age_min'], usd=round(usd, 2), exit_ts=now + hold * 3600))
        log.append(f"OPEN  {b} {c} long ${usd:.2f} @ {mids[c]:.6g} (signal age {s['age_min']}m), exit ~{f(now + hold*3600)}")
json.dump(L, open(P, 'w'), indent=1)
for b, v in L['books'].items():
    cl = [p for p in L['closed'] if p['book'] == b]; w = sum(p['ret'] > 0 for p in cl)
    print(f"{b}: equity ${v['eq']:.2f} ({(v['eq']/v['start']-1)*100:+.2f}%), {len(cl)} closed, {w} wins, {sum(p['book']==b for p in L['open'])} open")
for x in log: print(x)
open('paper_log.txt', 'w').write('\n'.join(log))
