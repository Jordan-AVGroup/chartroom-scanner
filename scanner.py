"""Chartroom scanner (public, signal-only). Detects market-wide crash cascades and rebound setups on Hyperliquid perps
using public candle data. It has no account access, no keys, and no order code: it only writes alert.json.

  python scanner.py --json alert.json
"""
import os, sys, json, time, math, argparse, datetime as dt
import numpy as np, pandas as pd, requests
HERE = os.path.dirname(os.path.abspath(__file__)); 
INFO = "https://api.hyperliquid.xyz/info"
UNIVERSE = [v for v in json.load(open(os.path.join(HERE, "hlmap.json"))).values() if v]
LIQ = ['BTC','ETH','SOL','XRP','BNB','DOGE','HYPE','SUI','ADA','AAVE','UNI','LINK','ENA','TRUMP','FARTCOIN','AVAX','LTC','DOT','NEAR','WLD','TAO','ONDO','ARB','INJ','CRV','kPEPE']
MAJ = ['BTC', 'ETH', 'SOL', 'XRP', 'BNB', 'DOGE']
P = dict(win=864, minp=432, z_ev=6.0, vr_ev=3.0, k_down=10, k_up=15, gap=288, reb_win=72, z_reb=5.0, vr_reb=2.0,
         reb_hold_h=24, reb_slots=12, reb_fresh_min=20, thr_wait_min=30, thr_valid_h=8, thr_hold_h=48, thr_slots=6,
         thrust_enabled=False)

def info(body, tries=6):
    for k in range(tries):
        try:
            r = requests.post(INFO, json=body, timeout=30)
            if r.status_code == 200:
                j = r.json()
                if j is not None: return j
        except Exception: pass
        time.sleep(1.5 + 2 * k)
    raise RuntimeError(f"Hyperliquid info failed: {body.get('type')}")

def candles(coin, bars=int(os.environ.get('IA_BARS', 2100))):
    now = int(time.time() * 1000); d = info({'type': 'candleSnapshot', 'req': {'coin': coin, 'interval': '5m', 'startTime': now - bars * 300000, 'endTime': now}})
    df = pd.DataFrame([(x['t'] // 1000, float(x['o']), float(x['c']), float(x['v']) * float(x['c'])) for x in d], columns=['t', 'o', 'c', 'qv']).set_index('t')
    return df[df.index <= (now // 1000) - 300]          # closed bars only

def features(D):
    """D: {coin: DataFrame(t -> o,c,qv)} on a common 5m grid. Returns z, vr, C, O DataFrames."""
    t1 = max(df.index.max() for df in D.values()); t0 = min(df.index.min() for df in D.values())
    idx = np.arange(t0, t1 + 1, 300)
    C = pd.DataFrame({k: v.c.reindex(idx) for k, v in D.items()}); O = pd.DataFrame({k: v.o.reindex(idx) for k, v in D.items()})
    V = pd.DataFrame({k: v.qv.reindex(idx) for k, v in D.items()})
    r = np.log(C).diff(); sig = np.sqrt((r ** 2).rolling(P['win'], min_periods=P['minp']).mean().shift(1))
    vr = V / V.rolling(P['win'], min_periods=P['minp']).median().shift(1)
    return r / sig, vr, C, O

def detect(z, vr):
    """Event starts (index labels) for both sides, plus the live 1h breadth series."""
    out = {}
    for side, K in (('down', P['k_down']), ('up', P['k_up'])):
        hit = ((z <= -P['z_ev']) if side == 'down' else (z >= P['z_ev'])) & (vr >= P['vr_ev'])
        h1 = hit.sum(axis=1).rolling(12, min_periods=1).sum(); casc = (h1 >= K).values
        st = np.flatnonzero(casc & ~np.r_[False, casc[:-1]]); ev = []; last = -10 ** 9
        for s in st:
            if s - last >= P['gap']: ev.append(int(z.index[s])); last = s
        out[side] = dict(events=ev, h1=h1, hits=hit)
    return out

def signals(z, vr, C, det, now=None):
    """Actionable setups at the latest closed bar."""
    now = now or int(z.index[-1]); res = []
    for e in det['down']['events']:
        if now - e > P['reb_win'] * 300 + P['reb_fresh_min'] * 60: continue
        w = (z.index > e) & (z.index <= e + P['reb_win'] * 300)
        for coin in [c for c in LIQ if c in z.columns]:
            m = w & (z[coin] >= P['z_reb']).values & (vr[coin] >= P['vr_reb']).values
            if not m.any(): continue
            tb = int(z.index[np.flatnonzero(m)[0]]); age = (now - tb) / 60 + 5
            res.append(dict(strategy='cascade', coin=coin, side='long', event_t=e, signal_t=tb, age_min=round(age), fresh=age <= P['reb_fresh_min'],
                            z=round(float(z.at[tb, coin]), 1), vr=round(float(vr.at[tb, coin]), 1), px=float(C.at[tb, coin]), hold_h=P['reb_hold_h'], slots=P['reb_slots']))
    for e in det['up']['events']:
        due = e + P['thr_wait_min'] * 60; age = (now - due) / 60
        if age < -P['thr_wait_min'] or age > P['thr_valid_h'] * 60: continue
        for coin in MAJ:
            res.append(dict(strategy='thrust', coin=coin, side='long', event_t=e, signal_t=due, age_min=round(age), fresh=0 <= age <= P['thr_valid_h'] * 60,
                            pending=age < 0, px=float(C[coin].iloc[-1]), hold_h=P['thr_hold_h'], slots=P['thr_slots']))
    return res

def load_all(coins=None):
    coins = coins or UNIVERSE; D = {}
    for c in coins:
        try: D[c] = candles(c)
        except Exception as e: print('skip', c, e, file=sys.stderr)
        time.sleep(0.25)
    return D


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json', dest='json_out', default='alert.json'); a = ap.parse_args()
    D = load_all(); z, vr, C, O = features(D); det = detect(z, vr); sig = signals(z, vr, C, det); now = int(z.index[-1])
    out = dict(now=now, coins=len(D), down_h1=int(det['down']['h1'].iloc[-1]), up_h1=int(det['up']['h1'].iloc[-1]), k_down=P['k_down'], k_up=P['k_up'],
               events=[dict(t=int(e), side=sd) for sd in ('down', 'up') for e in det[sd]['events'] if now - e <= 6 * 3600],
               fresh=[dict(strategy=x['strategy'], coin=x['coin'], event_t=int(x['event_t']), age_min=x['age_min'], z=x.get('z'), vr=x.get('vr')) for x in sig if x['fresh']])
    json.dump(out, open(a.json_out, 'w'), indent=1)
    print(json.dumps({k: out[k] for k in ('now', 'coins', 'down_h1', 'up_h1')}), len(out['events']), 'events,', len(out['fresh']), 'fresh')

if __name__ == '__main__':
    main()
