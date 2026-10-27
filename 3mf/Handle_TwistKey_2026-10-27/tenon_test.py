"""Real-size test coupon for the twist-key tenon (front joint dimensions).

Hourglass tenon across the tray/cover split Z=0, inserted along +Y -> -Y into a
slot that is blind at the far side. A flat key goes through the slot mouth with
its bar upright, then turns 90 degrees: the bar sits behind the lip and stops
the tenon backing out; the tenon stops the key going deeper. Units mm.
X = along the cane, Y = across the handle (tenon axis), Z = up.
Run: python -B tenon_test.py   (numpy, manifold3d, trimesh, matplotlib)
"""
from pathlib import Path
import json, math
import numpy as np
import manifold3d as md
import trimesh

H = Path(__file__).resolve().parent

# ---- real front-joint dimensions (handle 37.17 wide at the front tenon) ----
W = 18.58                      # half width of the handle at the tenon
TW, WAIST, TH = 4.45, 2.85, 7.0  # hourglass tenon: end width, waist, height
CLEAR = 0.20                   # slot clearance per face, whole length
FAR_SKIN = 2.0                 # slot stops this far inside the far side face
END_PLAY = 0.30                # tenon end to blind slot end
# key (flat, printed lying down; thickness T_KEY is its width in every section)
T_KEY = 2.4
BAR_HALF, BAR_T = 3.40, 1.20   # bar behind the lip
SHAFT_HALF = 1.10              # shaft through the lip (2.2 x 2.4)
KNOB_HALF, KNOB_T = 4.20, 1.00 # ridge in the surface recess, turned by nail/coin
# pockets in the shell, measured inward from the side face
RECESS_R, RECESS_D = 4.50, 1.80   # knob recess (knob top sits 0.8 below the face)
LIP_T = 1.50
CHAMBER_R, CHAMBER_D = 3.75, 1.60
SHAFT_RELIEF_R = 1.85            # round relief in the lip so the shaft can turn
TIGHT_GROW = 0.10                # second tenon: 0.1 mm bigger per face (0.1 mm gap)
# coupon body
BLOCK_X, TRAY_Z, COVER_Z = 6.0, 8.0, 8.0

Y_RECESS = W - RECESS_D           # recess floor = lip outer face
Y_LIP_IN = Y_RECESS - LIP_T       # lip back face
Y_CF = Y_LIP_IN - CHAMBER_D       # chamber floor = slot end = tenon end
Y_FAR = -W + FAR_SKIN             # blind end of the slot


def box(a, b):
    a = np.array(a, float); b = np.array(b, float)
    return md.Manifold.cube(b - a).translate(a)


def prism_y(section, y0, y1):
    """Extrude an (X, Z) CrossSection along Y from y0 to y1."""
    return section.extrude(y1 - y0).rotate((90, 0, 0)).translate((0, y1, 0))


def disc_y(r, y0, y1, n=128):
    return md.Manifold.cylinder(y1 - y0, r, r, n).rotate((-90, 0, 0)).translate((0, y0, 0))


def hourglass(offset=0.0):
    w, n, h = TW / 2, WAIST / 2, TH / 2
    cs = md.CrossSection([[(-w, -h), (w, -h), (n, 0), (w, h), (-w, h), (-n, 0)]])
    return cs.offset(offset, md.JoinType.Miter, 3.0) if offset else cs


def key(angle_deg, seat=0.0):
    """Key with its bar along `angle_deg` in the XZ plane (0 = horizontal = locked,
    90 = upright = insert). seat shifts it along +Y (out) from the seated position."""
    y_bar0 = Y_CF                       # bar inner face touches the tenon end
    y_bar1 = y_bar0 + BAR_T
    y_knob1 = W - 0.8
    y_knob0 = y_knob1 - KNOB_T
    r = lambda a, b: md.CrossSection.square((2 * a, 2 * b), center=True)
    parts = [prism_y(r(BAR_HALF, T_KEY / 2), y_bar0, y_bar1),
             prism_y(r(SHAFT_HALF, T_KEY / 2), y_bar1 - .01, y_knob0 + .01),
             prism_y(r(KNOB_HALF, T_KEY / 2), y_knob0, y_knob1)]
    m = parts[0] + parts[1] + parts[2]
    return m.rotate((0, -angle_deg, 0)).translate((0, seat, 0))


def tenon(shift=0.0, grow=0.0):
    return prism_y(hourglass(grow), Y_FAR + END_PLAY, Y_CF).translate((0, shift, 0))


def shells():
    cut = prism_y(hourglass(CLEAR), Y_FAR, W + 1)          # slot + mouth through the lip
    cut += disc_y(CHAMBER_R, Y_CF, Y_LIP_IN)               # key chamber
    cut += disc_y(SHAFT_RELIEF_R, Y_LIP_IN - .01, W + 1)    # shaft relief through the lip
    cut += disc_y(RECESS_R, Y_RECESS, W + 1)               # knob recess
    tray = box((-BLOCK_X, -W, -TRAY_Z), (BLOCK_X, W, 0)) - cut
    cover = box((-BLOCK_X, -W, 0), (BLOCK_X, W, COVER_Z)) - cut
    return tray, cover


def vol(m):
    return m.volume() if not m.is_empty() else 0.0


def check():
    tray, cover = shells()
    shell = tray + cover
    res = {}
    t0, k_lock = tenon(), key(0)
    parts = {'tray': tray, 'cover': cover, 'tenon': t0, 'key_locked': k_lock}
    names = list(parts)
    res['assembled_overlaps_mm3'] = {f'{a}/{b}': round(vol(parts[a] ^ parts[b]), 6)
                                     for i, a in enumerate(names) for b in names[i + 1:]}
    # tenon slides in from the open side with no key present
    res['tenon_insert_path_max_overlap_mm3'] = round(max(vol(shell ^ tenon(s)) for s in np.arange(0, 2 * W + 4, .25)), 6)
    # key upright slides in along the mouth
    res['key_insert_path_max_overlap_mm3'] = round(max(vol((shell + t0) ^ key(90, s)) for s in np.arange(0, 8, .1)), 6)
    # key turns 90 degrees in place (centre of its axial play)
    res['key_turn_max_overlap_mm3'] = round(max(vol((shell + t0) ^ key(a, .2)) for a in np.arange(0, 90.1, 3)), 6)
    # locked: key cannot back out, tenon cannot back out or go deeper
    res['locked_key_out_0.6mm_overlap_mm3'] = round(vol(shell ^ key(0, .6)), 4)
    res['locked_key_out_3mm_overlap_mm3'] = round(vol(shell ^ key(0, 3)), 4)
    res['tenon_out_0.6mm_vs_locked_key_mm3'] = round(vol(key(0, .4) ^ tenon(.6)), 4)
    res['tenon_deeper_0.4mm_vs_blind_end_mm3'] = round(vol(shell ^ tenon(-.4)), 4)
    # split: cover lifted 0.4 mm with the tenon in place
    # how far the cover can lift before the hourglass flanks catch (bisection)
    lo, hi = 0.0, 3.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if vol(cover.translate((0, 0, mid)) ^ t0) > 1e-6: hi = mid
        else: lo = mid
    res['cover_lift_free_play_mm'] = round(hi, 3)
    tt = tenon(grow=TIGHT_GROW); lo, hi = 0.0, 3.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if vol(cover.translate((0, 0, mid)) ^ tt) > 1e-6: hi = mid
        else: lo = mid
    res['cover_lift_free_play_tight_tenon_mm'] = round(hi, 3)
    res['tight_tenon_insert_path_max_overlap_mm3'] = round(max(vol(shell ^ tenon(s, TIGHT_GROW)) for s in np.arange(0, 2 * W + 4, .25)), 6)
    res['cover_lift_1.5mm_vs_tenon_mm3'] = round(vol(cover.translate((0, 0, 1.5)) ^ t0), 4)
    res['axial_play_key_mm'] = round(Y_LIP_IN - (Y_CF + BAR_T), 3)
    res['bar_overlap_behind_lip_mm'] = round(BAR_HALF - (WAIST / 2 + CLEAR + (TW - WAIST) / 2 * (T_KEY / 2) / (TH / 2)), 3)
    res['knob_overlap_on_lip_when_upright_mm'] = round(KNOB_HALF - (TH / 2 + CLEAR), 3)
    ok = (all(v < 1e-4 for v in res['assembled_overlaps_mm3'].values())
          and res['tenon_insert_path_max_overlap_mm3'] < 1e-4
          and res['tight_tenon_insert_path_max_overlap_mm3'] < 1e-4
          and res['key_insert_path_max_overlap_mm3'] < 1e-4
          and res['key_turn_max_overlap_mm3'] < 1e-4
          and res['locked_key_out_0.6mm_overlap_mm3'] > .01
          and res['locked_key_out_3mm_overlap_mm3'] > .01
          and res['tenon_out_0.6mm_vs_locked_key_mm3'] > .01
          and res['tenon_deeper_0.4mm_vs_blind_end_mm3'] > .01
          and res['cover_lift_1.5mm_vs_tenon_mm3'] > .01)
    res['all_checks_pass'] = bool(ok)
    return res, parts


def to_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.array(mesh.vert_properties[:, :3]), np.array(mesh.tri_verts), process=True)


def print_layout(parts):
    """Each part in its print pose, laid out on the plate (Z=0 is the bed)."""
    out = {}
    tray = parts['tray']                                   # bottom on the bed
    out['Tenon_Test_Tray'] = tray.translate((0, 0, TRAY_Z))
    cover = parts['cover'].rotate((180, 0, 0))             # outer top face on the bed
    out['Tenon_Test_Cover'] = cover.translate((20, 0, COVER_Z))
    ten = parts['tenon']                                   # flat face on the bed
    b = ten.bounding_box(); out['Tenon_Test_Tenon_gap0.2'] = ten.translate((36, 0, -b[2]))
    ten = tenon(grow=TIGHT_GROW)
    b = ten.bounding_box(); out['Tenon_Test_Tenon_gap0.1'] = ten.translate((45, 0, -b[2]))
    k = key(0)                                             # locked pose already lies flat
    b = k.bounding_box()
    out['Tenon_Test_Key'] = k.translate((58, -(b[1] + b[4]) / 2, -b[2]))
    out['Tenon_Test_Key_spare'] = k.translate((70, -(b[1] + b[4]) / 2, -b[2]))
    return out


def write3mf(path, objects):
    ns = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<model unit="millimeter" xml:lang="en-US" xmlns="{ns}">', '<resources>']
    for i, (name, m) in enumerate(objects.items(), 1):
        tm = to_trimesh(m)
        assert tm.is_watertight, name
        lines.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>')
        lines += [f'<vertex x="{v[0]:.5f}" y="{v[1]:.5f}" z="{v[2]:.5f}"/>' for v in tm.vertices]
        lines.append('</vertices><triangles>')
        lines += [f'<triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}"/>' for f in tm.faces]
        lines.append('</triangles></mesh></object>')
    lines.append('</resources><build>')
    lines += [f'<item objectid="{i}" transform="1 0 0 0 1 0 0 0 1 100 100 0"/>' for i in range(1, len(objects) + 1)]
    lines.append('</build></model>')
    import zipfile
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model', '\n'.join(lines))


if __name__ == '__main__':
    res, parts = check()
    print(json.dumps(res, indent=1, ensure_ascii=False))
    assert res['all_checks_pass']
    plate = print_layout(parts)
    write3mf(H / 'Tenon_Test.3mf', plate)
    (H / 'tenon_test_check.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf8')
    print('wrote', H / 'Tenon_Test.3mf')
