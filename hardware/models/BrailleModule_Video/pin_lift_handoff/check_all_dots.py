"""Look at every pin before trusting a clip  ->  out/plate_all_up.png, out/check_all_90_pins.png
The sheet shows each pin down (upper) and raised (lower). Every bug found so far was visible here first."""
import numpy as np, cv2, os, config
import generator as S
HF = np.array([[S.PRE[(r, c)]['var']['hf'] for c in range(9)] for r in range(10)])
up = S.frame(S.HOLD * HF if S.VARY else np.full((10, 9), S.HOLD))
cv2.imwrite(os.path.join(config.OUT, 'plate_all_up.png'), S.u8(up))
R = 26; s = 4; rows = []
for r in range(10):
    a = []; b = []
    for c in range(9):
        cx, cy = int(round(S.grid[r, c, 0])), int(round(S.grid[r, c, 1]))
        a.append(cv2.resize(S.u8(S.BASE[cy - R:cy + R, cx - R:cx + R]), None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC))
        b.append(cv2.resize(S.u8(up[cy - R:cy + R, cx - R:cx + R]), None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC))
    rows += [np.concatenate(a, 1), np.concatenate(b, 1), np.full((6, a[0].shape[1] * 9, 3), 255, np.uint8)]
cv2.imwrite(os.path.join(config.OUT, 'check_all_90_pins.png'), np.concatenate(rows, 0))
fits = np.sqrt(np.array([[S.PRE[(r, c)]['fit'] for c in range(9)] for r in range(10)]))
print('outline fit error per pin (share of radius): median %.3f, worst %.3f' % (np.median(fits), fits.max()))
