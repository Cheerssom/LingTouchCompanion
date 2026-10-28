"""Key detent test (2026-10-28): stop the twist key turning by itself.

Builds on tenon_test.py (same tenon, slot, lip, chamber and recess). Changes:
- key: bar and knob now clamp the lip (gap = lip + C_AX), bar 1.5 thick, and two
  small ridges under the knob ends;
- tray/cover blocks: four shallow grooves in the recess floor, at the locked
  (horizontal) and upright (insert) key angles. Nothing is added on the shell.
Turning the key the ridges ride on the floor and the knob ends bend out by RIDGE_H,
then drop into the next groove. Units mm; axes as in tenon_test.py.
Plate: tray block, cover block, key ridge 0.10, key ridge 0.15. The tenon is the
0.1 mm gap one already printed from Tenon_Test.3mf.
Run: python -B key_detent_test.py   (numpy, manifold3d, trimesh, matplotlib)
"""
import json, math
import numpy as np
import manifold3d as md
import trimesh
import tenon_test as T

H = T.H
C_AX = 0.05            # bar outer face to lip back face with the knob on the floor
BAR_T = 1.50           # thicker bar: 0.05 from the tenon end when seated
RIDGE_R = 3.80         # ridge centre radius on the knob
RIDGE_TOP = 0.40       # flat top width of the trapezoid ridge, flanks at 45 degrees
G_CLEAR = 0.05         # groove = ridge grown by this, all round
RIDGE_HS = (0.10, 0.15)
OVERHANG_DEG = 30      # Bambu default support threshold


def trapezoid(h, grow=0.0):
    """Ridge section in the (along-knob, Y) plane, base on Y=0, pointing -Y."""
    a, b = RIDGE_TOP / 2 + grow, RIDGE_TOP / 2 + h + grow   # top half, base half
    return md.CrossSection([[(-a, -h - grow), (a, -h - grow), (b, 0.01 + grow), (-b, 0.01 + grow)]])


def ridges(h, angle, seat=0.0, grow=0.0):
    """Both knob-end ridges (as a groove cutter when grow > 0)."""
    w = T.T_KEY / 2 + grow
    one = trapezoid(h, grow).extrude(2 * w).translate((0, 0, -w))   # section in XY, along Z
    m = one.translate((-RIDGE_R, T.Y_RECESS, 0)) + one.translate((RIDGE_R, T.Y_RECESS, 0))
    return m.rotate((0, -angle, 0)).translate((0, seat, 0))


def key(angle, h, seat=0.0, with_ridges=True):
    y_bar1 = T.Y_LIP_IN - C_AX
    y_knob0 = T.Y_RECESS
    r = lambda a, b: md.CrossSection.square((2 * a, 2 * b), center=True)
    m = (T.prism_y(r(T.BAR_HALF, T.T_KEY / 2), y_bar1 - BAR_T, y_bar1)
         + T.prism_y(r(T.SHAFT_HALF, T.T_KEY / 2), y_bar1 - .01, y_knob0 + .01)
         + T.prism_y(r(T.KNOB_HALF, T.T_KEY / 2), y_knob0, y_knob0 + T.KNOB_T))
    m = m.rotate((0, -angle, 0)).translate((0, seat, 0))
    return m + ridges(h, angle, seat) if with_ridges else m


def shells():
    tray, cover = T.shells()
    hmax = max(RIDGE_HS)
    g = ridges(hmax, 0, grow=G_CLEAR) + ridges(hmax, 90, grow=G_CLEAR)
    g = g ^ T.box((-6, T.Y_RECESS - 2, -6), (6, T.Y_RECESS + 0.005, 6))
    return tray - g, cover - g


vol = T.vol


def knob_lift(shell, h, a):
    """Outward shift the knob ends need to clear the floor at angle a (the bend)."""
    knob = T.prism_y(md.CrossSection.square((2 * T.KNOB_HALF, T.T_KEY), center=True),
                     T.Y_RECESS, T.Y_RECESS + T.KNOB_T).rotate((0, -a, 0)) + ridges(h, a)
    if vol(shell ^ knob) < 1e-6:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(25):
        m = (lo + hi) / 2
        if vol(shell ^ knob.translate((0, m, 0))) > 1e-7: lo = m
        else: hi = m
    return hi


def check():
    tray, cover = shells()
    shell = tray + cover
    ten = T.tenon(grow=T.TIGHT_GROW)
    res = {'tray/cover_overlap_mm3': round(vol(tray ^ cover), 6),
           'tenon_vs_shell_mm3': round(vol(shell ^ ten), 6),
           'tenon_insert_path_max_overlap_mm3': round(max(vol(shell ^ T.tenon(s, T.TIGHT_GROW))
                                                          for s in np.arange(0, 2 * T.W + 4, .25)), 6)}
    lo, hi = 0.0, 3.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if vol(cover.translate((0, 0, mid)) ^ ten) > 1e-6: hi = mid
        else: lo = mid
    res['cover_lift_free_play_mm'] = round(hi, 3)
    L = RIDGE_R - T.SHAFT_HALF
    ok = (res['tray/cover_overlap_mm3'] < 1e-4 and res['tenon_vs_shell_mm3'] < 1e-4
          and res['tenon_insert_path_max_overlap_mm3'] < 1e-4)
    for h in RIDGE_HS:
        r = {}
        r['seated_overlap_locked_mm3'] = round(vol((shell + ten) ^ key(0, h)), 6)
        r['seated_overlap_upright_mm3'] = round(vol((shell + ten) ^ key(90, h)), 6)
        r['insert_upright_path_max_overlap_mm3'] = round(max(vol((shell + ten) ^ key(90, h, s)) for s in np.arange(0, 8, .1)), 6)
        r['turn_without_ridges_max_overlap_mm3'] = round(max(vol((shell + ten) ^ key(a, h, with_ridges=False)) for a in np.arange(0, 90.1, 3)), 6)
        lifts = {a: round(knob_lift(shell, h, a), 3) for a in range(0, 91, 5)}
        r['knob_end_bend_by_angle_mm'] = lifts
        r['knob_end_bend_max_mm'] = max(lifts.values())
        r['key_out_0.3mm_blocked_mm3'] = round(vol(shell ^ key(0, h, .3, with_ridges=False)), 4)
        r['tenon_out_0.2mm_vs_key_mm3'] = round(vol(key(0, h, with_ridges=False) ^ T.tenon(.2, T.TIGHT_GROW)), 4)
        # estimate only: knob end as a cantilever from the shaft edge, bar/shell compliance ignored
        r['knob_bend_strain_estimate_pct'] = round(100 * 3 * T.KNOB_T * r['knob_end_bend_max_mm'] / (2 * L * L), 2)
        res[f'ridge_{h:.2f}'] = r
        ok = ok and (r['seated_overlap_locked_mm3'] < 1e-4 and r['seated_overlap_upright_mm3'] < 1e-4
                     and r['insert_upright_path_max_overlap_mm3'] < 1e-4
                     and r['turn_without_ridges_max_overlap_mm3'] < 1e-4
                     and lifts[0] == 0 and lifts[90] == 0 and min(lifts[a] for a in range(10, 81, 5)) > .8 * h
                     and r['key_out_0.3mm_blocked_mm3'] > .01 and r['tenon_out_0.2mm_vs_key_mm3'] > .01)
    res['key_axial_play_vs_lip_mm'] = C_AX
    res['bar_to_tenon_end_mm'] = round(T.Y_LIP_IN - C_AX - BAR_T - T.Y_CF, 3)
    res['all_checks_pass'] = bool(ok)
    return res, tray, cover


def print_layout(tray, cover):
    out = {'Detent_Test_Tray': tray.translate((0, 0, T.TRAY_Z)),
           'Detent_Test_Cover': cover.rotate((180, 0, 0)).translate((20, 0, T.COVER_Z))}
    for i, h in enumerate(RIDGE_HS):
        k = key(0, h)
        b = k.bounding_box()
        out[f'Detent_Test_Key_ridge{h:.2f}'] = k.translate((36 + 12 * i, -(b[1] + b[4]) / 2, -b[2]))
    return out


def overhangs(plate):
    """Downward faces steeper than the support threshold, not on the bed (mm2)."""
    res = {}
    for name, m in plate.items():
        tm = T.to_trimesh(m)
        down = tm.face_normals[:, 2] < -math.cos(math.radians(OVERHANG_DEG))
        on_bed = tm.triangles[:, :, 2].max(axis=1) < 0.01
        res[name] = round(float(tm.area_faces[down & ~on_bed].sum()), 4)
    return res


def preview(tray, cover, h=0.15):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle, Circle
    plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
    plt.rcParams['axes.unicode_minus'] = False
    polys = lambda cs: [np.array(p) for p in cs.to_polygons()]

    def draw(ax, cs, fc, ec, lw=.6, z=1, dy=None):
        for p in polys(cs):
            p = p.copy()
            if dy is not None: p[:, 1] += dy(p)
            ax.add_patch(Polygon(p, closed=True, fc=fc, ec=ec, lw=lw, zorder=z))

    fig = plt.figure(figsize=(15, 6.4))
    ax = fig.add_axes([0.03, 0.08, 0.36, 0.80])
    yfl = T.Y_RECESS - 0.03
    for m, c in ((tray, '#a9c8d6'), (cover, '#d0d6d4')):
        for p in polys(m.rotate((90, 0, 0)).slice(yfl)):
            p = p.copy(); p[:, 1] = -p[:, 1]
            ax.add_patch(Polygon(p, closed=True, fc=c, ec='#555', lw=.5, zorder=1))
    ax.add_patch(Circle((0, 0), T.RECESS_R, fill=False, ec='#333', lw=1.2, ls='--', zorder=3))
    ax.add_patch(Rectangle((-T.KNOB_HALF, -T.T_KEY / 2), 2 * T.KNOB_HALF, T.T_KEY, fc='#e0803c', ec='#8a3a0e', lw=1.2, alpha=.8, zorder=4))
    for sx in (-1, 1):
        ax.add_patch(Rectangle((sx * RIDGE_R - RIDGE_TOP / 2 - h, -T.T_KEY / 2), RIDGE_TOP + 2 * h, T.T_KEY, fc='#8a3a0e', ec='none', zorder=5))
    ax.add_patch(Rectangle((-T.T_KEY / 2, -T.KNOB_HALF), T.T_KEY, 2 * T.KNOB_HALF, fill=False, ec='#8a3a0e', lw=1.2, ls=':', zorder=4))
    ax.axhline(0, color='r', lw=.6, ls=':', zorder=2)
    ax.annotate('坑底 4 个浅槽（深 %.2f）\n锁住、竖着两个位置\n凸棱都落进去' % (max(RIDGE_HS) + G_CLEAR), xy=(0, 3.9), xytext=(2.2, 5.5),
                fontsize=10, arrowprops=dict(arrowstyle='->'), zorder=6)
    ax.annotate('扣两头底下的小凸棱', xy=(-RIDGE_R, 0.6), xytext=(-6.3, 4.2), fontsize=10, arrowprops=dict(arrowstyle='->'), zorder=6)
    ax.text(0, -5.6, '橙色＝扣拧到锁住（横着）；点线＝插进去时（竖着）', ha='center', fontsize=10)
    ax.text(-5.8, -1.2, '托盘', fontsize=11); ax.text(-5.8, 0.6, '前盖', fontsize=11)
    ax.set_xlim(-6.5, 6.5); ax.set_ylim(-6.3, 6.6); ax.set_aspect('equal')
    ax.set_title('正对手柄侧面的圆坑看', fontsize=12); ax.set_xlabel('mm')
    ten = T.tenon(grow=T.TIGHT_GROW)
    for col, (title, lift) in enumerate((('锁住：凸棱落在浅槽里，扣不受力', 0.0),
                                          ('拧的途中：凸棱压在坑底，扣外面那条两头被顶起 %.2f' % h, h))):
        ax = fig.add_axes([0.43 + col * 0.29, 0.08, 0.26, 0.80])
        draw(ax, tray.slice(-0.02), '#a9c8d6', '#555', .5)
        draw(ax, cover.slice(0.02), '#d0d6d4', '#555', .5)
        draw(ax, ten.slice(0.02), '#efb04a', '#8a5a10', .8)
        bend = None
        if lift:
            bend = lambda p: np.where(p[:, 1] >= T.Y_RECESS - h - .01,
                                      lift * np.clip((np.abs(p[:, 0]) - T.SHAFT_HALF) / (T.KNOB_HALF - T.SHAFT_HALF), 0, 1) ** 2, 0)
        draw(ax, key(0, h).slice(0.0), '#e0803c', '#8a3a0e', 1, 4, bend)
        ax.set_xlim(-5.5, 5.5); ax.set_ylim(T.Y_CF - 2.2, T.W + 1.0); ax.set_aspect('equal')
        ax.axhline(T.W, color='#555', lw=.8, ls='--')
        ax.text(5.3, T.W + .15, '手柄侧面', ha='right', fontsize=9)
        ax.text(-5.3, T.Y_CF - 1.6, '榫', fontsize=10); ax.text(3.4, T.Y_LIP_IN + .45, '口', fontsize=10)
        ax.set_title(title, fontsize=10.5); ax.set_xlabel('mm（沿扣的长度）')
    fig.suptitle('扣的咔哒：扣上小凸棱 + 坑底浅槽（真实尺寸切面，示意凸棱高 %.2f）' % h, fontsize=13)
    fig.savefig(H / 'key_detent_preview.png', dpi=130)


if __name__ == '__main__':
    res, tray, cover = check()
    plate = print_layout(tray, cover)
    res['overhang_area_needing_support_mm2'] = oh = overhangs(plate)
    res['all_checks_pass'] = bool(res['all_checks_pass'] and all(v < 0.01 for v in oh.values()))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    (H / 'key_detent_check.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf8')
    assert res['all_checks_pass']
    T.write3mf(H / 'Key_Detent_Test.3mf', plate)
    preview(tray, cover)
    print('wrote', H / 'Key_Detent_Test.3mf')
