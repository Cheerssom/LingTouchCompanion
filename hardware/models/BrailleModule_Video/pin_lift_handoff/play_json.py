"""Play a JSON target sequence on the photo plate  ->  out/lingchu_json.mp4 plus records for independent checking.

    python play_json.py [--targets inputs/lingchu_frames_1791643082241.json] [--name lingchu_json]

Needs work/grid.npy and work/cam.npz (step1_detect_dots.py, step2_fit_camera.py).
Timeline: all down for LEAD_MS, targets at LEAD_MS + ts, then the first frame at or after both the last movement and the
last target time shows the final settled target, held for TAIL_MS (whatever that target is; no clearing is added).
Each output frame shows the pin levels at its start time (one instant, no shutter blending:
blending two pin positions draws a double outline). JSON row 0 = top row of the picture, column 0 = left, unmirrored.

Records written next to the video:
  <name>_events.json          targets, per-pin fixed character, every rise/fall with its timing, frame numbers
  <name>_frames.csv           every frame x every pin that ever moves: target, level, height mm actually rendered
  <name>_trajectory_ms.npz    level of all 90 pins at every millisecond
  <name>_check.json           checks run on the raw (pre-encoding) frames and on the decoded video"""
import argparse, json, os, shutil, subprocess, csv
import numpy as np, cv2
import config, motion

FPS = 30; LEAD_MS = 500.0; TAIL_MS = 1000.0
QH = 0.002                                   # rendered height step, mm (keeps the per-pin cache small)


def frame_time(i): return i * 1000.0 / FPS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--targets', default=os.path.join(config.HERE, 'inputs', 'lingchu_frames_1791643082241.json'))
    ap.add_argument('--name', default='lingchu_json')
    ap.add_argument('--crf', type=int, default=10)
    a = ap.parse_args()
    import generator as S
    S.VARY = True
    targets, sha = motion.load_targets(a.targets)
    pins, ev, final = motion.build(targets, LEAD_MS)
    HF = np.array([[S.PRE[(r, c)]['var']['hf'] for c in range(9)] for r in range(10)])
    last_ts = LEAD_MS + targets[-1]['ts']
    end_move = motion.last_motion_end(pins, default=LEAD_MS)
    # first frame at or after the last movement ends and the last target is applied: the final settled target
    k_down = int(np.ceil(max(end_move, last_ts) * FPS / 1000.0 - 1e-9))
    N = k_down + int(round(TAIL_MS * FPS / 1000.0))
    base = S.u8(S.BASE)

    def heights(t):
        return np.round(motion.levels(pins, t) * S.HOLD * HF / QH) * QH

    def window_mask(r, c, h):
        P = S.PRE[(r, c)]; m = np.zeros(base.shape[:2], bool)
        if h > 1e-4:
            win, wm = S.dot_layer(r, c, h); m[P['y0']:P['y0'] + S.S, P['x0']:P['x0'] + S.S] = wm
        return m

    out_mp4 = os.path.join(config.OUT, a.name + '.mp4')
    ff = shutil.which('ffmpeg'); assert ff, 'ffmpeg not on PATH'
    h_img, w_img = base.shape[:2]
    enc = subprocess.Popen([ff, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (w_img, h_img),
                            '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', str(a.crf), '-preset', 'slow', '-pix_fmt', 'yuv420p',
                            '-movflags', '+faststart', out_mp4], stdin=subprocess.PIPE)
    moving = sorted(pins)
    rows = []; Hall = []; prev = None; prevH = None
    chk = dict(start_frames_equal_base=[], end_frames_equal_final=[], final_target_raised=int(final.sum()), held_pin_max_diff=0, held_pin_checks=0,
               held_violations=[], stray_change_px=[], unchanged_frame_pairs=0)
    for i in range(N):
        t = frame_time(i); H = heights(t); Hall.append(H)
        img = S.u8(S.frame(H))
        enc.stdin.write(img.tobytes())
        L = motion.levels(pins, t)
        for (r, c) in moving:
            tgt = 0
            for e in ev[(r, c)]:
                if e['t_ms'] <= t: tgt = e['to']
            rows.append((i, round(t, 3), r, c, tgt, round(L[r, c], 5), round(float(H[r, c]), 4)))
        if i < k_down and not H.any() and not any(e['t_ms'] <= t for v in ev.values() for e in v):
            chk['start_frames_equal_base'].append((i, bool(np.array_equal(img, base))))
        if i == k_down: final_img = img
        if i >= k_down: chk['end_frames_equal_final'].append((i, bool(np.array_equal(img, final_img))))
        if prev is not None:
            changed = np.nonzero(H != prevH)
            allowed = np.zeros(base.shape[:2], bool)
            for r, c in zip(*changed): allowed |= window_mask(r, c, prevH[r, c]) | window_mask(r, c, H[r, c])
            diff = np.abs(img.astype(np.int16) - prev.astype(np.int16)).max(2) > 0
            stray = int((diff & ~allowed).sum())
            if stray: chk['stray_change_px'].append((i, stray))
            if not changed[0].size and not diff.any(): chk['unchanged_frame_pairs'] += 1
            # pins raised and unchanged on both frames: their own pixels must be identical
            for r, c in zip(*np.nonzero((H == prevH) & (H > 1e-4))):
                m = window_mask(r, c, H[r, c])
                d = int(np.abs(img[m].astype(np.int16) - prev[m].astype(np.int16)).max())
                chk['held_pin_checks'] += 1; chk['held_pin_max_diff'] = max(chk['held_pin_max_diff'], d)
                if d: chk['held_violations'].append((i, int(r), int(c), d))
        prev = img; prevH = H
    enc.stdin.close(); rc = enc.wait()

    # ---- records
    stem = os.path.join(config.OUT, a.name)
    with open(stem + '_frames.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['frame', 't_ms', 'row', 'col', 'target', 'level', 'height_mm']); w.writerows(rows)
    T = np.arange(0, int(np.ceil(frame_time(N))) + 1)
    lev = np.stack([motion.levels(pins, float(t)) for t in T]).astype(np.float32)
    np.savez_compressed(stem + '_trajectory_ms.npz', t_ms=T, level=lev, height_factor=HF, hold_mm=S.HOLD)
    fr = lambda t: t * FPS / 1000.0
    rec = dict(source=dict(path=os.path.relpath(a.targets, config.HERE), sha256=sha, records=len(targets),
                           ts_ms=[t['ts'] for t in targets], seq=[t['seq'] for t in targets]),
               timeline=dict(fps=FPS, lead_ms=LEAD_MS, tail_ms=TAIL_MS, frames=N, duration_ms=frame_time(N),
                             last_motion_end_ms=round(end_move, 3), last_target_ms=last_ts, first_final_frame=k_down,
                             frame_sample='levels at frame start time i*1000/fps, one instant per frame'),
               mapping='JSON row r, col c -> picture row r (top=0), col c (left=0); unmirrored',
               heights=dict(hold_mm=S.HOLD, rendered_step_mm=QH, note='JSON 1 = settled level 1 = HOLD x fixed per-pin height factor'),
               ranges_ms=dict(rise=motion.RISE_MS, fall=motion.FALL_MS),
               pins={'%d,%d' % k: dict(character={kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in p.ch.items()},
                                        height_factor=round(float(HF[k]), 4),
                                        actuations=[dict(x, event_frame=round(fr(x['t_ms']), 3), end_frame=round(fr(x['end_ms']), 3))
                                                    for x in p.record()])
                     for k, p in sorted(pins.items())})
    json.dump(rec, open(stem + '_events.json', 'w'), indent=1)

    # ---- timing from the millisecond trajectory
    tim = []
    for (r, c), p in sorted(pins.items()):
        for x in p.seg:
            t0 = int(x['t_ms']); s = lev[t0:, r, c]
            if x['kind'] == 'rise':
                moved = int(np.argmax(s > x['h0'] + 1e-6)); settled = int(np.argmax(s >= 1.0 - 1e-9))
                f0 = int(np.ceil(fr(x['t_ms']) - 1e-9)); fs = [round(p.level(frame_time(j)), 3) for j in range(f0, f0 + 7)]
                tim.append(dict(pin=[r, c], kind='rise', t_ms=t0, start_delay_ms=moved, settled_ms=settled, frames_from=f0, frame_levels=fs,
                                dip_visible_in_frames=bool(any(fs[j] < max(fs[:j]) - 0.05 for j in range(1, len(fs)))),
                                ok=bool(motion.RISE_MS[0] <= settled <= motion.RISE_MS[1] and (s[settled:settled + 300] >= 1 - 1e-9).all())))
            else:
                down = int(np.argmax(s <= 1e-9))
                tim.append(dict(pin=[r, c], kind='fall', t_ms=t0, down_ms=down, ok=bool(motion.FALL_MS[0] <= down <= motion.FALL_MS[1])))
    chk['timing'] = tim; chk['timing_all_ok'] = all(x['ok'] for x in tim)
    # 1->1: between a settled rise and the next event the level never changes
    hold_ok = True
    for (r, c), p in pins.items():
        for x, y in zip(p.seg, p.seg[1:] + [None]):
            if x['kind'] != 'rise': continue
            a0 = int(np.ceil(x['t_ms'] + x['rise_ms'])); b0 = int(y['t_ms']) if y else len(T)
            hold_ok &= bool((lev[a0:b0 + 1 if y else b0, r, c] == 1.0).all())
    chk['raised_hold_level_constant'] = hold_ok
    chk['ffmpeg_returncode'] = rc

    # ---- decoded video: frame count, and how much the encoder disturbs still frames
    cap = cv2.VideoCapture(out_mp4); dec = []; n = 0; still = []; dprev = None
    while True:
        ok, f = cap.read()
        if not ok: break
        if dprev is not None and np.array_equal(Hall[n], Hall[n - 1]):
            still.append(int(np.abs(f.astype(np.int16) - dprev.astype(np.int16)).max()))
        dprev = f; n += 1
    chk['decoded_frames'] = n; chk['decoded_fps'] = cap.get(cv2.CAP_PROP_FPS)
    chk['decoded_still_pairs'] = len(still)
    chk['decoded_still_max_diff'] = max(still) if still else 0
    chk['decoded_still_diff_histogram'] = {str(v): still.count(v) for v in sorted(set(still))}
    s0 = chk['start_frames_equal_base']; s1 = chk['end_frames_equal_final']
    chk['summary'] = dict(start_still_frames=sum(1 for _, e in s0 if e), start_still_ms=round(sum(1 for _, e in s0 if e) * 1000 / FPS, 1),
                          end_still_frames=sum(1 for _, e in s1 if e), end_still_ms=round(sum(1 for _, e in s1 if e) * 1000 / FPS, 1),
                          held_violations=len(chk['held_violations']), stray_change_frames=len(chk['stray_change_px']),
                          rises_with_visible_dip='%d/%d' % (sum(x.get('dip_visible_in_frames', False) for x in tim), sum(x['kind'] == 'rise' for x in tim)))
    json.dump(chk, open(stem + '_check.json', 'w'), indent=1)
    print('wrote', out_mp4, '| frames', N, 'decoded', n, '| ffmpeg rc', rc)
    print(json.dumps(chk['summary']), '| timing ok', chk['timing_all_ok'], '| raised hold constant', hold_ok,
          '| held pin max diff', chk['held_pin_max_diff'], 'over', chk['held_pin_checks'], 'checks')


if __name__ == '__main__':
    main()
