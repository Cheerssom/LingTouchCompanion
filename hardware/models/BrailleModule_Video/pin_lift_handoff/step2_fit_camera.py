"""One pinhole camera for the whole picture  ->  work/cam.npz
15 modules x 6 pins, 2.5 mm pitch inside a module; each module is free to sit and turn where it likes on the plane.
ASSUMED, not measured: square pixels, no lens distortion, optical centre at the middle of the image.
(10/11 are an edited, re-framed picture, so this camera is only 'the camera this picture is consistent with'.)"""
import numpy as np, cv2, os, config
from scipy.optimize import least_squares
grid = np.load(os.path.join(config.WORK, 'grid.npy'))
H_img, W_img = cv2.imread(config.BASE_IMG).shape[:2]; pp = (W_img / 2, H_img / 2)
tmpl = np.array([[-2.5, -1.25], [0, -1.25], [2.5, -1.25], [-2.5, 1.25], [0, 1.25], [2.5, 1.25]])
mods = np.array([[grid[2 * mr + rr, 3 * mc + cc, :2] for rr in (0, 1) for cc in (0, 1, 2)] for mr in range(5) for mc in range(3)])   # (15,6,2)
ref = 7                                                                        # centre module pins down the coordinate frame
def world(pose):
    out = np.zeros((15, 6, 3))
    for m in range(15):
        ax, ay, ph = pose[m]; c, s = np.cos(ph), np.sin(ph)
        out[m, :, 0] = ax + c * tmpl[:, 0] - s * tmpl[:, 1]; out[m, :, 1] = ay + s * tmpl[:, 0] + c * tmpl[:, 1]
    return out
def unpack(p):
    pose = np.zeros((15, 3)); k = 7
    for m in range(15):
        if m == ref: continue
        pose[m] = p[k:k + 3]; k += 3
    return p[0], p[1:4], p[4:7], pose
def project(f, rvec, tvec, X):
    K = np.array([[f, 0, pp[0]], [0, f, pp[1]], [0, 0, 1.]])
    uv, _ = cv2.projectPoints(X.reshape(-1, 3).astype(np.float64), rvec, tvec, K, None); return uv.reshape(-1, 2)
def resid(p):
    f, rvec, tvec, pose = unpack(p); return (project(f, rvec, tvec, world(pose)) - mods.reshape(-1, 2)).ravel()
best = None
for tau0 in (-0.3, 0.3):
    for f0 in (900, 1400, 2500):
        p0 = [f0, tau0, 0, 0, 0, 0, f0 / 25.]; c0 = mods[ref].mean(0)
        for m in range(15):
            if m == ref: continue
            c = mods[m].mean(0); p0 += [(c[0] - c0[0]) / 25., (c[1] - c0[1]) / 25., 0.]
        r = least_squares(resid, np.array(p0, float), method='lm', max_nfev=4000); rms = np.sqrt((r.fun ** 2).mean())
        if best is None or rms < best[0]: best = (rms, r.x)
rms, p = best; f, rvec, tvec, pose = unpack(p)
R, _ = cv2.Rodrigues(rvec); C = -R.T @ tvec; Xw = world(pose); sgn = -1.0 if C[2] < 0 else 1.0     # sgn: which way is 'up towards the camera'
print('fit error: rms %.2f px, worst %.2f px | focal %.0f px | tilt %.1f deg | camera %.1f mm above the surface' %
      (rms, np.abs(resid(p)).max(), f, np.degrees(np.arccos(abs(R[2, 2]))), abs(C[2])))
Xh = Xw.copy(); Xh[:, :, 2] = sgn * 1.0
S = (project(f, rvec, tvec, Xh) - project(f, rvec, tvec, Xw)).reshape(15, 6, 2)
print('image shift per mm of rise, per module (dx, dy px):')
for mr in range(5): print('   ' + '   '.join('(%+.1f,%+.1f)' % tuple(S[mr * 3 + mc].mean(0)) for mc in range(3)))
np.savez(os.path.join(config.WORK, 'cam.npz'), f=f, rvec=rvec, tvec=tvec, pose=pose, Xw=Xw, sgn=sgn, pp=np.array(pp))
