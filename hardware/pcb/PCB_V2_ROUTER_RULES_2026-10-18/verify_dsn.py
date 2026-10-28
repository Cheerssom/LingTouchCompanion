"""Read-only checker for a future EasyEDA DSN; exits nonzero on mismatch."""
import csv
import pathlib
import re
import sys


def parse(text):
    stack, roots = [], []
    for token in re.findall(r'"(?:\\.|[^"\\])*"|\x27[^\x27]*\x27|[()]|[^\s()]+', text):
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            stack.pop()
        else:
            stack[-1].append(token)
    if stack or len(roots) != 1:
        raise ValueError('Unbalanced DSN')
    return roots[0]


def children(node, name):
    return [x for x in node if isinstance(x, list) and x and x[0] == name]


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python verify_dsn.py exported.dsn')
    base = pathlib.Path(__file__).resolve().parent
    assignments = {r['net']: r for r in csv.DictReader(
        (base / 'net-rule-assignment.csv').open(encoding='utf-8-sig'))}
    root = parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    structure = children(root, 'structure')[0]
    network = children(root, 'network')[0]
    library = children(root, 'library')[0]
    errors = []
    nets = {x[1].strip("'\"") for x in children(network, 'net')}
    if nets != set(assignments):
        errors.append(f'Net set: missing={sorted(set(assignments)-nets)}, extra={sorted(nets-set(assignments))}')
    layers = {x[1]: x for x in children(structure, 'layer')}
    if len(layers) != 6:
        errors.append(f'Expected 6 layers, got {len(layers)}')
    for layer, net in [('Inner1', 'GND'), ('Inner4', 'VCC')]:
        node = layers.get(layer, [])
        if children(node, 'type') != [['type', 'power']] or children(node, 'use_net') != [['use_net', net]]:
            errors.append(f'{layer}: expected power / {net}')
    for layer in ['TopLayer', 'Inner2', 'Inner3', 'BottomLayer']:
        if children(layers.get(layer, []), 'type') != [['type', 'signal']]:
            errors.append(f'{layer}: expected signal')
    vias = {x[1]: x for x in children(library, 'padstack') if x[1].startswith('via')}
    classes = {x[1].strip("'\""): x for x in children(network, 'class')}
    for net, row in assignments.items():
        node = classes.get(net, [])
        rules = children(node, 'rule')
        width = children(rules[0], 'width') if rules else []
        clearance = children(rules[0], 'clearance') if rules else []
        expected = float(row['outer_default_mm']) / .0254
        if not width or abs(float(width[0][1]) - expected) > .06:
            errors.append(f'{net}: expected outer width {expected:.3f} mil')
        if not clearance or abs(float(clearance[0][1]) - .102/.0254) > .06:
            errors.append(f'{net}: expected clearance approximately 4.02 mil')
        circuits = children(node, 'circuit')
        used = children(circuits[0], 'use_via') if circuits else []
        via = vias.get(used[0][1]) if used else None
        if not via:
            errors.append(f'{net}: undefined use_via')
            continue
        circles = [x[1] for x in children(via, 'shape') if len(x)>1 and x[1][0]=='circle']
        expected_diameter = (.65 if row['via_rule']=='V2_VIA_POWER' else .5)/.0254
        if len(circles)!=6 or {x[1] for x in circles} != set(layers) or any(abs(float(x[2])-expected_diameter)>.06 for x in circles):
            errors.append(f'{net}: expected six-layer via copper diameter {expected_diameter:.3f} mil')
    if errors:
        print('FAIL: ' + str(len(errors)) + ' mismatches')
        print('\n'.join(errors))
        return 1
    print('PASS: 196 nets, six layers, GND/VCC power types, per-net outer widths/clearance and via copper diameters.')
    print('Drill sizes, parallel-via counts, actual return routing and DRC must be checked in EDA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
