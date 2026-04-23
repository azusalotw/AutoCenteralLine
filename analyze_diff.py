import sys; sys.path.insert(0, '.')
from core import *

raw = read_dxf_lines('samples/E剖-分析.dxf')
snapped = snap_lines(raw)
polygons = find_closed_polygons(snapped)
outer, chambers = classify_polygons(polygons)
triples = classify_centerlines_from_geometry_full(outer, chambers)
triples = merge_colinear_centerlines(triples)
triples = filter_short_centerlines(triples)

cls = [cl for cl, _, _ in triples]
props = [(label, t) for _, label, t in triples]
for _ in range(3):
    cls = extend_to_intersections(cls)
triples_ext = [(cl, label, t) for cl, (label, t) in zip(cls, props)]

nodes, elements = build_model_with_properties(triples_ext)

# Compare with expected
import ezdxf
doc = ezdxf.readfile('outputs/E剖-分析_analytical-true.dxf')
msp = doc.modelspace()
expected_lines = set()
for e in msp:
    if e.dxftype() == 'LINE':
        s = (round(e.dxf.start.x, 3), round(e.dxf.start.y, 3))
        e2 = (round(e.dxf.end.x, 3), round(e.dxf.end.y, 3))
        expected_lines.add((min(s, e2), max(s, e2)))

node_pos = {nid: (round(x, 3), round(y, 3)) for nid, x, y in nodes}
actual_lines = set()
for eid, n1, n2, lbl, t in elements:
    s = node_pos[n1]
    e2 = node_pos[n2]
    actual_lines.add((min(s, e2), max(s, e2)))

print(f"Expected: {len(expected_lines)} elements")
print(f"Actual:   {len(actual_lines)} elements")
print(f"\nIn expected but not actual:")
for l in sorted(expected_lines - actual_lines):
    print(f"  {l}")
print(f"\nIn actual but not expected:")
for l in sorted(actual_lines - expected_lines):
    print(f"  {l}")
