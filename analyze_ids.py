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

for eid, n1, n2, lbl, t in elements:
    print(f"E{eid}: N{n1}-N{n2} {lbl} t={t:.3f}")
