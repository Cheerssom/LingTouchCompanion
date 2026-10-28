"""Read the rhythm of the three real movements off the stabilised clip (run stabilise.py first).
'share' = how much a frame looks like the settled raised state: 0 = same as down, 1 = same as settled up.
It is a likeness of the picture, NOT a height in mm."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2, config
st = np.load(os.path.join(config.WORK, 'real_stack.npy')).astype(np.float32); N = len(st)
def share(frames, dn, up, box):
    x0, y0, x1, y1 = box
    D = np.mean([st[i][y0:y1, x0:x1] for i in dn], 0); U = np.mean([st[i][y0:y1, x0:x1] for i in up], 0); out = []
    for f in frames:
        F = st[f][y0:y1, x0:x1]; best = None
        for dy in range(-2, 3):                        # allow 2 px of leftover camera wobble
            for dx in range(-2, 3):
                Fs = np.roll(np.roll(F, dy, 0), dx, 1)[3:-3, 3:-3]; Dc = D[3:-3, 3:-3]; dd = (U[3:-3, 3:-3] - Dc).ravel()
                a = float(((Fs - Dc).ravel() @ dd) / (dd @ dd)); r = np.sqrt(np.mean((Fs - (Dc + a * (U[3:-3, 3:-3] - Dc))) ** 2))
                if best is None or r < best[1]: best = (a, r)
        out.append('%d:%.2f' % (f, best[0]))
    return '  '.join(out)
M3 = (235, 105, 355, 205); M5 = (375, 225, 475, 335)       # right column: third module, bottom module (stack coordinates)
print('whole module, frame:share')
print(' third module rises  ', share(range(255, 264), range(250, 257), range(262, 267), M3))
print(' third module falls  ', share(range(299, 304), range(303, 309), range(294, 300), M3))
print(' bottom module rises ', share(range(68, 78), range(62, 69), range(76, 82), M5))
# every pin on its own: brightness of the pixels that change, scaled 0 (down) .. 1 (settled)
b = np.stack([cv2.GaussianBlur(f, (0, 0), 1.0) for f in st]); good = np.arange(8, N)
rng = np.percentile(b[good], 97, axis=0) - np.percentile(b[good], 3, axis=0)
m = (rng > 45).astype(np.uint8); m[:, 470:] = 0; m[430:] = 0; m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, lab, stt, cen = cv2.connectedComponentsWithStats(m, 8)
def pins(box):
    x0, y0, x1, y1 = box; return [i for i in range(1, n) if stt[i][4] >= 60 and x0 <= cen[i][0] <= x1 and y0 <= cen[i][1] <= y1]
def curve(i, dn, up, frames):
    s = b[:, lab == i].mean(1); lo = s[dn[0]:dn[1]].mean(); hi = s[up[0]:up[1]].mean(); return ' '.join('%.2f' % ((s[f] - lo) / (hi - lo)) for f in frames)
print('per pin, third module rise, frames 256-263:');
for i in pins((250, 120, 340, 195)): print('   pin at (%3d,%3d): ' % tuple(cen[i]), curve(i, (240, 256), (264, 298), range(256, 264)))
print('per pin, third module fall, frames 300-303:')
for i in pins((250, 120, 340, 195)): print('   pin at (%3d,%3d): ' % tuple(cen[i]), curve(i, (304, 330), (264, 298), range(300, 304)))
print('per pin, bottom module rise, frames 69-77:')
for i in pins((395, 240, 435, 315)): print('   pin at (%3d,%3d): ' % tuple(cen[i]), curve(i, (55, 68), (78, 120), range(69, 78)))
