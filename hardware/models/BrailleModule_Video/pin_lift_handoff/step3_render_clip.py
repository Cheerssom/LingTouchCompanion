"""Test clip at original speed (30 fps)  ->  out/test_real_rhythm_varied.mp4   (the version Hsinlung looked at on 10/10)
The PATTERN below is made up for testing. The RISE / FALL shape is from the real clip (see real_video/measure_rise.py)."""
import numpy as np, cv2, subprocess, os, shutil, config
import generator as S
S.VARY = True
FPS = 30; DUR = 7.4; T = 1 / FPS
SUB = 6; SHUTTER = 0.5 / FPS          # each frame averages SUB instants across half a frame (ordinary camera blur)
HOLD = S.HOLD
# ---- what each pin is asked to do: (time s, 1 = up / 0 = down).  Made-up pattern.
ev = {(r, c): [] for r in range(10) for c in range(9)}
def mod(mr, mc): return [(2 * mr + a, 3 * mc + b) for a in (0, 1) for b in (0, 1, 2)]
for rc in mod(2, 1): ev[rc] += [(0.5, 1), (2.0, 0)]                      # whole centre module up 1.5 s, as in the real clip
for rc in [(8, 7), (8, 6), (9, 6)]: ev[rc] += [(2.7, 1), (6.7, 0)]        # three pins of one module, as in the real clip
t = 3.5
for r in range(0, 10, 2):                                                # one full row stepping down every 0.6 s
    for c in range(9):
        if (r, c) not in [(8, 7), (8, 6)]: ev[(r, c)] += [(t, 1), (t + 0.6, 0)]
    t += 0.6
# ---- how a rise looks, frame by frame, as a share of the settled state (0 = down, 1 = settled).
# Real clip, per pin: first frame .50-.94 (about one pin in six is a frame late), second a little higher,
# third frame = dip, same frame for the whole module, depth .29-.80, then back to full within 2-3 frames.
# CURRENT BEHAVIOUR: a fresh curve is drawn for every (pin, rise). Agreed change: keep a fixed character per pin
# (late or not, how deep it dips, how fast it settles) and add only a small wobble per rise -> change profile() only.
prof = {}
def profile(key, k):
    if (key, k) not in prof:
        g = np.random.default_rng(9000 + key[0] * 97 + key[1] * 13 + k * 7)
        p0 = g.uniform(0.55, 0.95); p1 = min(0.97, p0 + g.uniform(0, 0.10)); dip = min(p1, g.uniform(0.30, 0.80))
        r3 = g.uniform(0.65, 0.95); r4 = max(r3, g.uniform(0.88, 1.0))
        if g.random() < 1 / 6: p0 = 0.08
        prof[(key, k)] = (np.array([p0, p1, dip, r3, r4, 1.0, 1.0]), g.uniform(0.04, 0.07))     # curve, fall time s
    return prof[(key, k)]
def height(key, t):
    t_on = None; t_off = None; k = -1
    for (te, st) in sorted(ev[key]):
        if te > t: break
        if st: t_on = te; t_off = None; k += 1
        else: t_off = te
    if t_on is None: return 0.0
    pr, fall = profile(key, k); hf = S.PRE[key]['var']['hf'] if S.VARY else 1.0
    def up(tt):
        x = (tt - t_on) / T
        if x < 0: return 0.0
        i = int(np.floor(x))
        if i >= len(pr) - 1: return 1.0
        f = max(0.0, (x - i - 0.6) / 0.4)              # hold each value through the exposure, move between frames
        return float(pr[i] * (1 - f) + pr[i + 1] * f)
    if t_off is None: return HOLD * hf * up(t)
    return max(0.0, HOLD * hf * up(t_off) * (1 - (t - t_off) / fall))
h_img, w_img = S.BASE.shape[:2]; path = os.path.join(config.OUT, 'test_real_rhythm_varied.mp4')
ff = shutil.which('ffmpeg'); frames_dir = os.path.join(config.OUT, 'frames')
if ff:
    p = subprocess.Popen([ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (w_img, h_img), '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path], stdin=subprocess.PIPE)
else: os.makedirs(frames_dir, exist_ok=True)
for i in range(int(DUR * FPS)):
    t0 = i / FPS
    Hs = [np.array([[height((r, c), t0 + SHUTTER * (k + 0.5) / SUB) for c in range(9)] for r in range(10)]) for k in range(SUB)]
    Hs = [np.round(H / 0.02) * 0.02 for H in Hs]                           # 0.02 mm steps keep the per-pin cache small
    img = S.frame(Hs[0]) if all(np.array_equal(Hs[0], H) for H in Hs[1:]) else np.mean([S.frame(H) for H in Hs], 0)
    if ff: p.stdin.write(S.u8(img).tobytes())
    else: cv2.imwrite(os.path.join(frames_dir, '%04d.png' % i), S.u8(img))
if ff: p.stdin.close(); p.wait(); print('wrote', path)
else: print('ffmpeg not found - wrote PNG frames to', frames_dir)
