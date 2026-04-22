# 中心線抽取、表面配對、端點延伸

from collections import defaultdict

from .constants import SNAP_TOL, MAX_WALL_THICKNESS, MAX_EXTENSION
from .geometry import signed_area


# ==========================================
# 表面抽取（+/-1 標記）
# ==========================================
def _ensure_winding(poly, is_outer):
    """確保外框走 CCW(+area)、內室走 CW(-area)；若方向不對則反轉。"""
    need_ccw = is_outer
    is_ccw = signed_area(poly) > 0
    if need_ccw != is_ccw:
        return poly[::-1]
    return poly


def _collect_edges(poly, h_surfaces, v_surfaces):
    """將多邊形的水平 / 垂直邊分別加入對應列表，標記 +1/-1（牆材料側）。"""
    n = len(poly)
    for i in range(n):
        v1, v2 = poly[i], poly[(i + 1) % n]
        dx, dy = v2[0] - v1[0], v2[1] - v1[1]
        if abs(dy) < SNAP_TOL and abs(dx) > SNAP_TOL:  # 水平邊
            y = (v1[1] + v2[1]) / 2
            xa, xb = sorted([v1[0], v2[0]])
            # 東向（dx>0）→ 牆在北 +1；西向 → 牆在南 -1
            h_surfaces.append((y, xa, xb, +1 if dx > 0 else -1))
        elif abs(dx) < SNAP_TOL and abs(dy) > SNAP_TOL:  # 垂直邊
            x = (v1[0] + v2[0]) / 2
            ya, yb = sorted([v1[1], v2[1]])
            # 南向（dy<0）→ 牆在東 +1；北向 → 牆在西 -1
            v_surfaces.append((x, ya, yb, +1 if dy < 0 else -1))


def _extract_surfaces(outer, chambers):
    """多邊形 → (h_surfaces, v_surfaces)：對每條邊標 +1/-1（牆材料側）。
    外框走 CCW(+area)、內室走 CW(-area)，使牆材料一致落在行進方向的左側。"""
    h_surfaces, v_surfaces = [], []
    _collect_edges(_ensure_winding(outer, is_outer=True), h_surfaces, v_surfaces)
    for c in chambers:
        _collect_edges(_ensure_winding(c, is_outer=False), h_surfaces, v_surfaces)
    return h_surfaces, v_surfaces


# ==========================================
# 表面配對（+1/-1 → 中心線）
# ==========================================
def _make_centerline(axis, oa, ob, mid):
    """依軸向建立中心線端點對。"""
    if axis == "h":
        return ((oa, mid), (ob, mid))
    return ((mid, oa), (mid, ob))


def _match_pending(pending, a, b, mid_coord, axis, result):
    """將一條 -1 表面與所有 pending +1 表面做重疊配對。
    回傳更新後的 pending 列表；配對成功的中心線加入 result。"""
    new_pending = []
    for pc, pa, pb in pending:
        oa, ob = max(pa, a), min(pb, b)
        if ob <= oa + 1e-6:
            new_pending.append((pc, pa, pb))
            continue
        mid = (pc + mid_coord) / 2.0
        result.append((_make_centerline(axis, oa, ob, mid), mid_coord - pc))
        if pa < oa - 1e-6:
            new_pending.append((pc, pa, oa))
        if pb > ob + 1e-6:
            new_pending.append((pc, ob, pb))
    return new_pending


def _process_neg_surfaces(by_coord_c, pending, c, axis, result):
    """處理同一座標上所有 -1 表面，與 pending 配對後回傳更新的 pending。"""
    for a, b, s in by_coord_c:
        if s != -1:
            continue
        pending = _match_pending(pending, a, b, c, axis, result)
    return pending


def _pair_surfaces_with_thickness(surfaces, max_thickness, axis):
    """沿主軸掃描，配對 +1/-1 表面，回傳 [(中心線, 厚度), ...]。"""
    by_coord = defaultdict(list)
    for c, a, b, s in surfaces:
        by_coord[round(c, 4)].append((a, b, s))
    sorted_coords = sorted(by_coord.keys())

    result = []
    pending = []  # [(coord, sec_min, sec_max), ...] 累積中的 +1 表面

    for c in sorted_coords:
        pending = [p for p in pending if c - p[0] <= max_thickness + 1e-6]
        pending = _process_neg_surfaces(by_coord[c], pending, c, axis, result)
        for a, b, s in by_coord[c]:
            if s == +1:
                pending.append((c, a, b))

    return result


def _pair_surfaces(surfaces, max_thickness, axis):
    """沿主軸由小到大掃描；遇 -1 時與最近 +1（≤ max_thickness）配對成中心線。"""
    return [cl for cl, _ in _pair_surfaces_with_thickness(surfaces, max_thickness, axis)]


# ==========================================
# 公開 API：中心線抽取
# ==========================================
def extract_centerlines(outer, chambers, max_thickness=MAX_WALL_THICKNESS):
    """多邊形 → 中心線列表（丟棄厚度資訊）。"""
    if outer is None:
        return []
    h_surfaces, v_surfaces = _extract_surfaces(outer, chambers)
    return (_pair_surfaces(h_surfaces, max_thickness, axis="h") +
            _pair_surfaces(v_surfaces, max_thickness, axis="v"))


def extract_centerlines_with_thickness(outer, chambers,
                                       max_thickness=MAX_WALL_THICKNESS):
    """多邊形 → [(中心線, 厚度), ...] 供 classify_centerlines 使用。"""
    if outer is None:
        return []
    h_surfaces, v_surfaces = _extract_surfaces(outer, chambers)
    return (_pair_surfaces_with_thickness(h_surfaces, max_thickness, axis="h") +
            _pair_surfaces_with_thickness(v_surfaces, max_thickness, axis="v"))


# ==========================================
# 端點延伸
# ==========================================
def _dist_to_range(v, lo, hi):
    """v 與區間 [lo, hi] 的最小距離；v 在區間內則為 0。"""
    return max(0.0, lo - v, v - hi)


def _find_extension_bounds(primary, a, b, perpendiculars,
                           primary_idx, secondary_idx,
                           max_extension, tol):
    """沿主軸 (primary_idx) 尋找 lo/hi 方向最近的垂直 CL 座標。
    primary: 本線的固定座標值 (y for H, x for V)
    a, b: 本線的範圍端點 (已排序, a < b)
    回傳 (new_a, new_b)。"""
    cands_lo, cands_hi = [], []
    for _, pl in perpendiculars:
        p_fixed = pl[0][primary_idx]
        s1, s2 = sorted([pl[0][secondary_idx], pl[1][secondary_idx]])
        if _dist_to_range(primary, s1, s2) > max_extension + tol:
            continue
        if p_fixed < a - tol and a - p_fixed <= max_extension:
            cands_lo.append(p_fixed)
        elif p_fixed > b + tol and p_fixed - b <= max_extension:
            cands_hi.append(p_fixed)
    if cands_lo:
        a = max(cands_lo)
    if cands_hi:
        b = min(cands_hi)
    return a, b


def _extend_line(line, perpendiculars, axis, max_extension, tol):
    """將一條中心線的端點延伸到最近的垂直 CL 上。"""
    if axis == "h":
        primary_idx, secondary_idx = 0, 1
        fixed = line[0][1]
        a, b = sorted([line[0][0], line[1][0]])
    else:
        primary_idx, secondary_idx = 1, 0
        fixed = line[0][0]
        a, b = sorted([line[0][1], line[1][1]])
    a, b = _find_extension_bounds(fixed, a, b, perpendiculars,
                                  primary_idx, secondary_idx,
                                  max_extension, tol)
    if axis == "h":
        return ((a, fixed), (b, fixed))
    return ((fixed, a), (fixed, b))


def extend_to_intersections(centerlines, max_extension=MAX_EXTENSION,
                            tol=SNAP_TOL):
    """每條 CL 的端點延伸到最近、且能涵蓋它的垂直 CL 上。"""
    h_lines = [(i, l) for i, l in enumerate(centerlines)
               if abs(l[0][1] - l[1][1]) < tol]
    v_lines = [(i, l) for i, l in enumerate(centerlines)
               if abs(l[0][0] - l[1][0]) < tol]
    out = list(centerlines)

    # 兩輪：先延伸 H 用原始 V，再延伸 V 用已延伸的 H
    for hi, hl in h_lines:
        out[hi] = _extend_line(hl, v_lines, "h", max_extension, tol)
    h_lines_updated = [(i, out[i]) for i, _ in h_lines]
    for vi, vl in v_lines:
        out[vi] = _extend_line(vl, h_lines_updated, "v", max_extension, tol)
    return out
