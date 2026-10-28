"""Re-check the load-bearing handle facts in VERIFIED_FACTS.md (about 10 s, read-only).

Run from the repository root:
    3mf/.runtime/structural-runtime/Scripts/python.exe -B 3mf/Handle/check_facts.py
Every line prints OK or MISMATCH. If a source hash changed, the facts derived from it
must be re-derived instead of reused.
"""
from pathlib import Path
import hashlib, json, sys
import numpy as np
import trimesh
import xml.etree.ElementTree as ET

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
sys.path.insert(0, str(H))
ok_all = True


def report(label, ok, detail=''):
    global ok_all
    ok_all &= bool(ok)
    print(('OK       ' if ok else 'MISMATCH ') + label + (f'  [{detail}]' if detail else ''))


# 1. source identity ------------------------------------------------------------------
SOURCES = {
    '3mf/Handle/inputs/Handle_Original.3mf': '25cd55ec492a72cccf81dd1d16a50490106574b93a2b63005601ec6ab786d6c6',
    '3mf/PCB/3D_PCB1_5_2026-09-15_no_U31-U45_U48_headers.step': '3b427f43deababdec1f0ef87a5221a4a84809a873733b7f3a75bbd58cd2469a4',
    '3mf/PCB/inputs/3D_PCB1_5_2026-09-15.step': 'bc137079b08c6e28868dd377544d98e749a99668405f34cabf4c29b9ed15f2aa',
    'BrailleModule_Video/inputs/Braille_Module_Reference.pdf': '1023de23891d9c1ee49d44fdf72487f79399e4074987c87cec90a39941b0b1b0',
    '3mf/Handle/Coaxial_v1/inputs/YD-ESP32-S3_Metric.pdf': '23098cc8e1195bff1f6040cca85c4e2536a6a7eae21d3bda1c2c2962ec3cbd19',
}
for rel, h in SOURCES.items():
    p = ROOT / rel
    report(f'sha256 {rel}', p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == h)

# 2. PCB1_5 drill holes (handle frame, lateral pose already +2.75 mm Z) -----------------
cache = H / 'Coaxial_v1' / 'cache'
idx = json.loads((cache / 'pcb_parts.json').read_text())
D = np.load(cache / 'pcb_parts.npz')
key = [p['key'] for p in idx if p['short'] == 'Board'][0]
board = trimesh.Trimesh(D[key + '_v'], D[key + '_f'], process=True)
y_mid = float(board.vertices[:, 1].mean())
holes = []
for L in board.section(plane_origin=[0, y_mid, 0], plane_normal=[0, 1, 0]).discrete:
    xz = L[:, [0, 2]]; ext = np.ptp(xz, 0)
    if ext.max() < 20:
        holes.append([*(xz.max(0) + xz.min(0)) / 2, *ext])
holes = np.array(holes)
pins = holes[np.abs(holes[:, 2] - 0.6) < 0.02]
mid = pins[(pins[:, 1] > -4) & (pins[:, 1] < 4) & (pins[:, 0] < 85)]
row_x = np.unique(np.round(mid[:, 0], 3))
mod_x = [(row_x[2 * k] + row_x[2 * k + 1]) / 2 for k in range(5)]
mod_z = float((mid[:, 1].min() + mid[:, 1].max()) / 2)
sw1 = holes[(np.abs(holes[:, 2] - 1.0) < 0.05) & (holes[:, 0] < 50)][:, :2].mean(0)
board_zc = float((board.vertices[:, 2].max() + board.vertices[:, 2].min()) / 2)
report('board outline centred in Z after +2.75 mm', abs(board_zc) < 0.05, f'centre Z {board_zc:.3f}')
report('middle module row pin pattern on Z~0', abs(mod_z) < 0.1, f'Z {mod_z:.3f}')
report('SW1 on the same centre line', abs(sw1[1] - mod_z) < 0.2, f'SW1 Z {sw1[1]:.3f}')
report('module body centres X 52.79 + 6.5k (SW1 at X 44.5)',
       np.allclose(mod_x, 52.786 + 6.5 * np.arange(5), atol=0.02) and abs(sw1[0] - 44.5) < 0.02,
       ', '.join(f'{v:.2f}' for v in mod_x))
print('         -> Codex studies used Z -2.75 mm of this pose (borrowed header placeholders).')

# 3. original cover openings vs the real footprint ----------------------------------------
from source import read_source
rows, members = read_source()
st = ET.fromstring(members['Metadata/model_settings.config'])
r = [r for r in rows if r['name'] == 'cover'][0]
rec = st.find("object[@id='%s']" % r['build_object_id'])
off = np.array([float(rec.find("part/metadata[@key='source_offset_%s']" % a).get('value')) for a in 'xyz'])
cover = trimesh.Trimesh(r['v'] + off, r['f'], process=False)
openings = [(L[:, 0].min(), L[:, 0].max(), L[:, 2].min(), L[:, 2].max())
            for L in cover.section(plane_origin=[0, 22.5, 0], plane_normal=[0, 1, 0]).discrete if np.ptp(L[:, 0]) < 100]
slots = sorted(o for o in openings if o[1] - o[0] > 20)
hole = [o for o in openings if o[1] - o[0] < 10][0]
x_shift = (mod_x[0] - 3.0) - slots[0][0]
report('old cover slots 32.0 long, widths 10/9/10', all(abs((s[1] - s[0]) - 32.0) < 0.05 for s in slots),
       ', '.join(f'{s[3]-s[2]:.1f}' for s in slots))
report('old cover hole-to-slot spacing differs from board by ~1.79 mm', abs(x_shift - 1.786) < 0.05, f'{x_shift:.3f} mm')

# 4. original tail is open above the stop lobe ------------------------------------------
import manifold3d as md
def man(rr):
    rec = st.find("object[@id='%s']" % rr['build_object_id'])
    o = np.array([float(rec.find("part/metadata[@key='source_offset_%s']" % a).get('value')) for a in 'xyz'])
    m = trimesh.Trimesh(rr['v'] + o, rr['f'], process=False)
    return md.Manifold.batch_boolean([md.Manifold(md.Mesh64(np.ascontiguousarray(p.vertices, np.float64),
                                      np.ascontiguousarray(p.faces, np.uint64))) for p in m.split(only_watertight=False)], md.OpType.Add)
cov_end = man(r).rotate((0, -90, 0)).slice(229.9).area()
report('old cover has no tail end wall', cov_end < 250, f'section area at X 229.9 = {cov_end:.0f} mm2')

print('\nALL OK' if ok_all else '\nSOME FACTS CHANGED - re-derive before reuse')
