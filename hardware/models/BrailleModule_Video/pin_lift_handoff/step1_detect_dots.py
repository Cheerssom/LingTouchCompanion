"""Find the 90 pin heads in the all-down plate and order them as a 10 x 9 grid  ->  work/grid.npy
Constants below (search region, brightness 80, blob area) are tuned to THIS image at 1086x1448."""
import numpy as np, cv2, os, config
A = cv2.imread(config.BASE_IMG).astype(np.float32); g = A.mean(2)
reg = np.zeros(g.shape, np.uint8); reg[235:965, 150:945] = 1                 # the array area in this picture
m = ((g > 80) & (reg > 0)).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
dots = np.array([(cen[i][0], cen[i][1], st[i][4], st[i][2], st[i][3]) for i in range(1, n)
                 if 350 < st[i][4] < 1300 and 0.75 < st[i][2] / st[i][3] < 1.33 and st[i][4] / (st[i][2] * st[i][3]) > 0.6])
assert len(dots) == 90, 'expected 90 pin heads, found %d' % len(dots)
order = np.argsort(dots[:, 1]); rows = []; cur = [order[0]]
for i in order[1:]:
    if dots[i, 1] - dots[cur[-1], 1] > 20: rows.append(cur); cur = [i]
    else: cur.append(i)
rows.append(cur); assert [len(r) for r in rows] == [9] * 10, [len(r) for r in rows]
grid = np.zeros((10, 9, 5))
for r, idx in enumerate(rows): grid[r] = dots[sorted(idx, key=lambda i: dots[i, 0])]
np.save(os.path.join(config.WORK, 'grid.npy'), grid)
print('90 pin heads found. row y:', np.round(grid[:, :, 1].mean(1)).astype(int))
