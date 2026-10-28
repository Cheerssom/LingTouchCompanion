"""Rebuild the V2 rule pack for planes: VCC/GND fan out to In4/In1, a few power nets 0.5 mm, rest 0.18 mm.
Net list comes from the current cloud schematic netlist (after the 2026-10-18 simplification)."""
import csv, json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / '.pcba-workflow/v2-schematic-review-20261018/edit'))
from pnet import parse  # noqa: E402

nets, _ = parse(str(here.parent / '.pcba-workflow/v2-schematic-review-20261018/edit/net4.net'))
names = sorted(set(nets.values()))

PLANE = {'VCC': 'In4 VCC plane', 'GND': 'In1 GND plane'}
POWER = {'VBUS': 3.0, 'VIN_SYS': 3.0, 'MAIN_SW': 4.1, 'VCCS': 1.0, 'SMA_SW': 1.0,
         'ESP_SW': 0.5, 'ESP_5V_RAW': 0.5, 'V5S': 0.5}
W = {'V2_SIGNAL': 0.18, 'V2_POWER': 0.5, 'V2_PLANE_FANOUT': 0.4}

rules = json.load(open(here / 'V2_DesignRules.json', encoding='utf-8'))
track = rules['Physics']['Track']
tmpl = track['V2_SIGNAL']
new = {}
for name, w in W.items():
    r = json.loads(json.dumps(tmpl))
    r['editName'] = name
    r['isSetDefault'] = name == 'V2_SIGNAL'
    for lay in r['form']['data'].values():
        lay['minValue'] = 0.1
        lay['defaultValue'] = w
        lay['maxValue'] = 5
    new[name] = r
rules['Physics']['Track'] = new
json.dump(rules, open(here / 'V2_DesignRules.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

rows, members = [], {k: [] for k in W}
for n in names:
    if n in PLANE:
        tr, via, basis = 'V2_PLANE_FANOUT', 'V2_VIA_POWER', PLANE[n] + ': short pad-to-via fan-out only'
    elif n in POWER:
        tr, via, basis = 'V2_POWER', 'V2_VIA_POWER', '%.1f A; widen by hand / pour after routing where it carries >1 A' % POWER[n]
    else:
        tr, via, basis = 'V2_SIGNAL', 'V2_VIA_SIGNAL', 'signal or coil (<=0.2 A)'
    members[tr].append(n)
    rows.append({'net': n, 'current_A': POWER.get(n, ''), 'track_rule': tr, 'via_rule': via,
                 'outer_default_mm': W[tr], 'inner_default_mm': W[tr], 'basis': basis})
with open(here / 'net-rule-assignment.csv', 'w', encoding='utf-8-sig', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0]))
    wr.writeheader()
    wr.writerows(rows)
with open(here / 'net-class-members.txt', 'w', encoding='utf-8') as f:
    for k, v in members.items():
        if k != 'V2_SIGNAL':
            f.write('%s (%d)\n%s\n\n' % (k, len(v), ', '.join(v)))
    f.write('V2_SIGNAL (%d): every other net (default rule, nothing to assign)\n' % len(members['V2_SIGNAL']))
print(len(names), {k: len(v) for k, v in members.items()})
