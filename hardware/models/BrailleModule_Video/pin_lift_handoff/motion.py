"""Target playback and pin motion, on a millisecond time base (independent of the output frame rate).

A target is a 10 x 9 grid of 0/1. Only changes move a pin: 0->1 rises, 1->0 falls; 1->1 and 0->0 do nothing,
so a pin that stays raised keeps exactly the same height (and therefore the same picture) through later targets.

Level 0 = down, 1 = the settled raised state. The generator height is level * HOLD * that pin's fixed height factor;
a JSON '1' is that raised state, not 1 mm.

Rise (Hsinlung, 2026-10-10): 120-180 ms from the target time to settled, INCLUDING the pin's own start delay and the
dip / settle. Shape from the real clip (real_video/measure_rise.py): quick first move to most of the way, a dip, then
up to settled; about one pin in six starts late. Fall: 30-60 ms.
Each pin has a fixed character (seeded by the pin only); each actuation adds a small wobble (seeded by pin + count).
All numbers here are visual settings within the agreed ranges, not measurements."""
import json, hashlib
import numpy as np
from scipy.interpolate import PchipInterpolator

ROWS, COLS = 10, 9
RISE_MS = (120.0, 180.0)
FALL_MS = (30.0, 60.0)
# rise shape: share of the motion time -> share of the settled level (values set per pin below).
# The dip sits around 85-105 ms into a ~150 ms motion with a short floor, so that 30 fps frames, which show one
# instant each, still catch it in the third frame as in the real clip (a narrow dip fell between frames).
KNOTS = np.array([0.0, 0.20, 0.38, 0.55, 0.66, 0.82, 0.92, 1.0])


def load_targets(path):
    """-> (list of dict(seq, ts, grid), sha256). Rejects anything that is not 10 x 9 of 0/1 with rising ts."""
    raw = open(path, 'rb').read()
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, list) or not data:
        raise ValueError('expected a non-empty list of target records')
    out, prev = [], -np.inf
    for i, rec in enumerate(data):
        g = np.array(rec['frame'])
        if g.shape != (ROWS, COLS) or not np.isin(g, (0, 1)).all():
            raise ValueError('record %d: expected a 10 x 9 grid of 0/1' % i)
        ts = float(rec['ts'])
        if not np.isfinite(ts) or ts <= prev:
            raise ValueError('record %d: timestamps must increase' % i)
        prev = ts
        out.append(dict(seq=rec.get('seq', i), ts=ts, mode=rec.get('mode'), grid=g.astype(np.uint8)))
    return out, hashlib.sha256(raw).hexdigest()


def transitions(targets, lead_ms):
    """Changes only. Starts from all down. -> {(r, c): [dict(t_ms, to, seq)]}"""
    state = np.zeros((ROWS, COLS), np.uint8)
    ev = {(r, c): [] for r in range(ROWS) for c in range(COLS)}
    for tg in targets:
        t = lead_ms + tg['ts']
        for r, c in zip(*np.nonzero(tg['grid'] != state)):
            ev[(int(r), int(c))].append(dict(t_ms=t, to=int(tg['grid'][r, c]), seq=tg['seq']))
        state = tg['grid'].copy()
    return ev, state


def character(r, c):
    """Fixed for the life of the pin."""
    g = np.random.default_rng([7100, r, c])
    late = bool(g.random() < 1 / 6)
    p0 = g.uniform(0.60, 0.90); p1 = min(0.95, p0 + g.uniform(0.02, 0.08))
    r3 = g.uniform(0.72, 0.90); r4 = min(0.98, max(r3 + 0.04, g.uniform(0.90, 0.97)))
    dip = min(g.uniform(0.38, 0.72), min(p1, r3) - 0.10)
    return dict(late=late, delay_ms=float(g.uniform(24, 30) if late else g.uniform(0, 8)),
                rise_ms=float(g.uniform(140, 165)), fall_ms=float(g.uniform(38, 52)),
                p0=float(p0), p1=float(p1), dip=float(dip), r3=float(r3), r4=float(r4))


def actuation(ch, r, c, k, kind):
    """Character + small wobble for the k-th actuation of this pin. Clipped so the agreed ranges always hold."""
    g = np.random.default_rng([7200, r, c, k, 1 if kind == 'rise' else 0])
    if kind == 'fall':
        return dict(fall_ms=float(np.clip(ch['fall_ms'] + g.normal(0, 3), FALL_MS[0] + 2, FALL_MS[1] - 2)))
    delay = float(np.clip(ch['delay_ms'] + g.normal(0, 2), 0, 34))
    total = float(np.clip(ch['rise_ms'] + g.normal(0, 4), RISE_MS[0] + 5, RISE_MS[1] - 5))
    total = max(total, delay + 95)                     # keep enough motion time for the dip and settle
    p0 = float(np.clip(ch['p0'] + g.normal(0, 0.03), 0.55, 0.92)); p1 = float(min(0.96, max(p0, ch['p1'] + g.normal(0, 0.02))))
    r3 = float(np.clip(ch['r3'] + g.normal(0, 0.02), 0.68, 0.92)); r4 = float(min(0.985, max(r3 + 0.03, ch['r4'] + g.normal(0, 0.01))))
    dip = float(min(np.clip(ch['dip'] + g.normal(0, 0.03), 0.32, 0.78), min(p1, r3) - 0.08))
    return dict(delay_ms=delay, rise_ms=total, p0=p0, p1=p1, dip=dip, r3=r3, r4=r4)


class Pin:
    """Level of one pin at any time in ms. Segments start at each state change from wherever the pin was."""
    def __init__(self, r, c, events):
        self.r, self.c = r, c; self.ch = character(r, c); self.seg = []
        nr = nf = 0
        for e in events:
            h0 = self.level(e['t_ms'])
            if e['to'] == 1:
                a = actuation(self.ch, r, c, nr, 'rise'); nr += 1
                curve = PchipInterpolator(KNOTS, [0, a['p0'], a['p1'], a['dip'], a['dip'] + 0.03, a['r3'], a['r4'], 1.0])
                self.seg.append(dict(kind='rise', t_ms=e['t_ms'], seq=e['seq'], h0=h0, curve=curve, **a))
            else:
                a = actuation(self.ch, r, c, nf, 'fall'); nf += 1
                self.seg.append(dict(kind='fall', t_ms=e['t_ms'], seq=e['seq'], h0=h0, **a))

    def level(self, t):
        s = None
        for x in self.seg:
            if x['t_ms'] <= t: s = x
            else: break
        if s is None: return 0.0
        u = t - s['t_ms']
        if s['kind'] == 'fall':
            if u >= s['fall_ms']: return 0.0
            return float(s['h0'] * np.cos(0.5 * np.pi * u / s['fall_ms']))       # eases out of the raised state, lands at speed
        if u < s['delay_ms']: return float(s['h0'])
        m = (u - s['delay_ms']) / (s['rise_ms'] - s['delay_ms'])
        if m >= 1: return 1.0
        return float(s['h0'] + (1 - s['h0']) * min(1.0, max(0.0, float(s['curve'](m)))))

    def record(self):
        out = []
        for x in self.seg:
            d = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items() if k != 'curve'}
            d['end_ms'] = round(x['t_ms'] + (x['rise_ms'] if x['kind'] == 'rise' else x['fall_ms']), 4)
            out.append(d)
        return out


def build(targets, lead_ms):
    ev, final = transitions(targets, lead_ms)
    pins = {k: Pin(k[0], k[1], v) for k, v in ev.items() if v}
    return pins, ev, final


def levels(pins, t):
    L = np.zeros((ROWS, COLS))
    for (r, c), p in pins.items(): L[r, c] = p.level(t)
    return L


def last_motion_end(pins, default=0.0):
    """End of the last movement in ms; `default` when nothing ever moves."""
    return max((s['t_ms'] + (s['rise_ms'] if s['kind'] == 'rise' else s['fall_ms']) for p in pins.values() for s in p.seg),
               default=default)
