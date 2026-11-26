"""Open one GitHub issue per new event or setup found in alert.json. Deduped by a key in the issue title.
Uses only the workflow's built-in GITHUB_TOKEN via the gh CLI. No other credentials."""
import json, os, subprocess, datetime as dt
A = json.load(open('alert.json')); APP = os.environ.get('APP_URL', '')
OWNER = os.environ.get('GITHUB_REPOSITORY_OWNER', '')
f = lambda t: dt.datetime.fromtimestamp(t, dt.UTC).strftime('%b %d %H:%M UTC')
def gh(*a): return subprocess.run(['gh', *a], capture_output=True, text=True)
seen = gh('issue', 'list', '--state', 'all', '--limit', '300', '--json', 'title', '-q', '.[].title').stdout
def post(key, title, body, label):
    if f'[{key}]' in seen: return
    r = gh('issue', 'create', '--title', f'[{key}] {title}', '--body', body + (f'\n\nOpen Chartroom: {APP}' if APP else ''),
           '--label', label, '--assignee', OWNER)
    print('posted' if r.returncode == 0 else 'FAILED', key, r.stderr.strip())
for e in A['events']:
    if e['side'] == 'down':
        post(f"down-{e['t']}", f"Crash cascade {f(e['t'])}", f"Market-wide downside cascade detected (1h breadth {A['down_h1']}/{A['k_down']}). "
             "Watch for rebound setups over the next 6h. Nothing has been traded.", 'event')
    else:
        post(f"up-{e['t']}", f"Breadth thrust {f(e['t'])} (probation, alert only)", f"Upside breadth thrust (1h breadth {A['up_h1']}/{A['k_up']}). "
             "Strategy is on probation; informational only.", 'event')
by = {}
for s in A['fresh']:
    if s['strategy'] == 'cascade': by.setdefault(s['event_t'], []).append(s)
for et, ss in by.items():
    first = ss[0]
    post(f"setup-{et}", f"Rebound setup: {first['coin']} (age {first['age_min']}m)",
         "Fresh cascade rebound setups: " + ', '.join(f"{s['coin']} z {s['z']} vr {s['vr']} age {s['age_min']}m" for s in ss) +
         ".\nEntry edge decays fast (15m late is still OK, 30m+ late is weak). Trades need explicit approval.\n\n" +
         '\n'.join('DATA ' + json.dumps(dict(coin=s['coin'], strategy=s['strategy'], event_t=s['event_t'], signal_t=s.get('signal_t'), px=s.get('px'), z=s['z'], vr=s['vr'])) for s in ss), 'setup')
print('scan', f(A['now']), 'down', A['down_h1'], 'up', A['up_h1'], 'events', len(A['events']), 'fresh', len(A['fresh']))
