"""10 and 11 are one picture: they differ only in four 53 px discs, and in 11 those discs are copies of the middle pin of the same row."""
import numpy as np, cv2, config
A = cv2.imread(config.BASE_IMG).astype(np.int32); B = cv2.imread(config.REF_IMG).astype(np.int32)
D = np.abs(A - B).max(2); ys, xs = np.nonzero(D > 0)
print('pixels that differ: %d of %d, inside x %d-%d, y %d-%d' % ((D > 0).sum(), D.size, xs.min(), xs.max(), ys.min(), ys.max()))
n, lab, st, cen = cv2.connectedComponentsWithStats((D > 0).astype(np.uint8), 8)
for i in range(1, n): print('  disc at (%d,%d) size %dx%d' % (st[i][0], st[i][1], st[i][2], st[i][3]))
S = 53
for name, x0, y0, sx, sy in [('top-left', 462, 526, 519, 526), ('top-right', 575, 526, 519, 526), ('bottom-left', 459, 581, 517, 581), ('bottom-right', 574, 581, 517, 581)]:
    m = D[y0:y0 + S, x0:x0 + S] > 0; d = (A[y0:y0 + S, x0:x0 + S] - A[sy:sy + S, sx:sx + S])[m]
    print('  11 %-12s minus middle pin of its row: mean BGR %s, spread %s' % (name, d.mean(0).round(1), d.std(0).round(1)))
