"""Hold the hand-held real clip still on the module tops  ->  work/real_stack.npy  (frames x 600 x 520, grey)
Frame numbers everywhere are 0-based. The polygon and crop are specific to this clip (720x1280, 342 frames)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2, config
cap = cv2.VideoCapture(config.REAL_VIDEO); G = []
while True:
    ok, fr = cap.read()
    if not ok: break
    G.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32))
N = len(G); print('frames', N, 'fps', cap.get(cv2.CAP_PROP_FPS)); REF = 149
ref = G[REF]
poly = np.array([[0, 395], [110, 318], [200, 285], [250, 300], [480, 540], [470, 640], [360, 700], [270, 760], [160, 850], [0, 800]], np.int32)   # module tops in frame 149
mask = np.zeros(ref.shape, np.uint8); cv2.fillPoly(mask, [poly], 255)
crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6); refb = cv2.GaussianBlur(ref, (0, 0), 1.5)
W = {REF: np.eye(3, dtype=np.float32)}
def track(order):
    w = np.eye(3, dtype=np.float32)
    for i in order:
        try: _, w = cv2.findTransformECC(refb, cv2.GaussianBlur(G[i], (0, 0), 1.5), w.copy(), cv2.MOTION_HOMOGRAPHY, crit, mask, 5)
        except cv2.error: pass
        W[i] = w.copy()
track(range(REF + 1, N)); track(range(REF - 1, -1, -1))
x0, y0, x1, y1 = 0, 270, 520, 870; stack = np.zeros((N, y1 - y0, x1 - x0), np.uint8)
for i in range(N):
    stack[i] = np.clip(cv2.warpPerspective(G[i], W[i], (ref.shape[1], ref.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)[y0:y1, x0:x1], 0, 255)
np.save(os.path.join(config.WORK, 'real_stack.npy'), stack); print('saved (frames 0-5 are badly aligned: big camera move at the start)')
