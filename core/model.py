# 節點-桿件模型建立

from .constants import SNAP_TOL
from .geometry import line_intersection, point_on_segment


def _cut_points(line, all_lines, tol):
    """line 與 all_lines 的所有交點，沿主軸排序並去重後回傳。"""
    cuts = [line[0], line[1]]
    for other in all_lines:
        inter = line_intersection(line, other)
        if inter and point_on_segment(inter, line, tol):
            cuts.append(inter)
    if abs(line[1][0] - line[0][0]) > abs(line[1][1] - line[0][1]):
        cuts.sort(key=lambda p: p[0])
    else:
        cuts.sort(key=lambda p: p[1])
    unique = [cuts[0]]
    for p in cuts[1:]:
        if abs(p[0] - unique[-1][0]) > tol or abs(p[1] - unique[-1][1]) > tol:
            unique.append(p)
    return unique


def split_at_intersections(lines, tol=SNAP_TOL):
    """把每條線在與其他線的交點處切開。"""
    result = []
    for line in lines:
        pts = _cut_points(line, lines, tol)
        for k in range(len(pts) - 1):
            result.append((pts[k], pts[k + 1]))
    return result


def build_model(centerlines, snap_tol=SNAP_TOL):
    nodes = []
    elements = []

    def get_or_add_node(pt):
        for nid, nx, ny in nodes:
            if abs(nx - pt[0]) < snap_tol and abs(ny - pt[1]) < snap_tol:
                return nid
        new_id = len(nodes) + 1
        nodes.append((new_id, pt[0], pt[1]))
        return new_id

    split_lines = split_at_intersections(centerlines, snap_tol)
    for ln in split_lines:
        n1 = get_or_add_node(ln[0])
        n2 = get_or_add_node(ln[1])
        if n1 != n2:
            elements.append((len(elements) + 1, n1, n2))
    return nodes, elements


def _collect_unique_points(cuts_per_line, snap_tol):
    raw_pts = []
    for cuts in cuts_per_line:
        for pt in cuts:
            if not any(abs(pt[0] - p[0]) < snap_tol and abs(pt[1] - p[1]) < snap_tol
                       for p in raw_pts):
                raw_pts.append(pt)
    raw_pts.sort(key=lambda p: (p[1], p[0]))
    return raw_pts


def _find_node_id(pt, nodes, snap_tol):
    for nid, nx, ny in nodes:
        if abs(nx - pt[0]) < snap_tol and abs(ny - pt[1]) < snap_tol:
            return nid
    return None


def _collect_elements(sorted_triples, cuts_per_line, nodes, snap_tol):
    node_pos = {nid: (x, y) for nid, x, y in nodes}
    horizontals, verticals = [], []
    seen_pairs = set()
    for (_, label, thickness), cuts in zip(sorted_triples, cuts_per_line):
        for k in range(len(cuts) - 1):
            n1 = _find_node_id(cuts[k], nodes, snap_tol)
            n2 = _find_node_id(cuts[k + 1], nodes, snap_tol)
            if n1 == n2:
                continue
            pair_key = (min(n1, n2), max(n1, n2))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            dy = abs(node_pos[n2][1] - node_pos[n1][1])
            dx = abs(node_pos[n2][0] - node_pos[n1][0])
            (verticals if dy > dx else horizontals).append((n1, n2, label, thickness))
    return horizontals, verticals, node_pos


def build_model_with_properties(triples, snap_tol=SNAP_TOL):
    """triples = [(centerline, label, thickness), ...]
    回傳 (nodes, elements) 其中 elements = [(id, n1, n2, label, thickness), ...]。"""
    centerlines = [cl for cl, _, _ in triples]
    sorted_triples = sorted(triples, key=lambda t: t[1] == "月台")
    cuts_per_line = [_cut_points(line, centerlines, snap_tol)
                     for line, _, _ in sorted_triples]

    raw_pts = _collect_unique_points(cuts_per_line, snap_tol)
    nodes = [(i + 1, p[0], p[1]) for i, p in enumerate(raw_pts)]

    horizontals, verticals, node_pos = _collect_elements(
        sorted_triples, cuts_per_line, nodes, snap_tol)

    def mid_y(e):
        return (node_pos[e[0]][1] + node_pos[e[1]][1]) / 2

    def mid_x(e):
        return (node_pos[e[0]][0] + node_pos[e[1]][0]) / 2

    main_h = sorted([e for e in horizontals if e[2] != "月台"], key=lambda e: (mid_y(e), mid_x(e)))
    plat_h = sorted([e for e in horizontals if e[2] == "月台"], key=lambda e: (mid_y(e), mid_x(e)))
    main_v = sorted([e for e in verticals   if e[2] != "月台"], key=lambda e: (mid_x(e), mid_y(e)))
    plat_v = sorted([e for e in verticals   if e[2] == "月台"], key=lambda e: (mid_x(e), mid_y(e)))

    elements = [(i + 1, n1, n2, lbl, t)
                for i, (n1, n2, lbl, t) in enumerate(main_h + main_v + plat_h + plat_v)]

    return nodes, elements
