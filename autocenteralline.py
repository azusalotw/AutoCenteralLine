import ezdxf
from collections import defaultdict


SNAP_TOL = 1e-3   # 端點 snap 容差（公尺）
COVER_TOL = 1e-3  # 區間覆蓋容差


# ==========================================
# Step 1: 讀取 DXF，萃取所有 LINE 端點對
# ==========================================
def read_dxf_lines(filepath):
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    lines = []
    for e in msp.query("LINE"):
        p1 = (e.dxf.start.x, e.dxf.start.y)
        p2 = (e.dxf.end.x, e.dxf.end.y)
        lines.append((p1, p2))

    # 同時支援 LWPOLYLINE（為相容未來圖檔）
    for pl in msp.query("LWPOLYLINE"):
        pts = [(p[0], p[1]) for p in pl.get_points()]
        for i in range(len(pts) - 1):
            lines.append((pts[i], pts[i + 1]))
        if pl.is_closed:
            lines.append((pts[-1], pts[0]))

    return lines


# ==========================================
# Step 2: 端點 snap，過濾零長度
# ==========================================
SNAP_DECIMALS = 3  # 對應 SNAP_TOL = 1e-3


def snap_lines(lines, decimals=SNAP_DECIMALS):
    out = []
    for p1, p2 in lines:
        sp1 = (round(p1[0], decimals), round(p1[1], decimals))
        sp2 = (round(p2[0], decimals), round(p2[1], decimals))
        if sp1 != sp2:
            out.append((sp1, sp2))
    return out


MAX_WALL_THICKNESS = 4.0   # 牆/板厚度上限（公尺）— 避免外框上下邊配對成貫穿全結構
MAX_EXTENSION = 2.0        # 中心線延伸到鄰近垂直 CL 的最大距離


# ==========================================
# Step 3: 偵測閉合多邊形（每個連通分量視為一個多邊形）
# ==========================================
def find_closed_polygons(lines):
    """每個連通分量假設為簡單閉合多邊形（每頂點度數為 2）。
    回傳 [polygon, ...]，每個 polygon 是順序排列的頂點列表。"""
    adj = defaultdict(list)
    for p1, p2 in lines:
        adj[p1].append(p2)
        adj[p2].append(p1)

    polygons = []
    visited = set()
    for start in list(adj.keys()):
        if start in visited:
            continue
        polygon = [start]
        visited.add(start)
        prev = None
        current = start
        ok = True
        while True:
            nbrs = adj[current]
            if len(nbrs) != 2:
                ok = False
                break
            nxt = nbrs[0] if nbrs[0] != prev else nbrs[1]
            if nxt == start:
                break
            if nxt in visited:
                ok = False
                break
            polygon.append(nxt)
            visited.add(nxt)
            prev, current = current, nxt
        if ok and len(polygon) >= 3:
            polygons.append(polygon)
    return polygons


def signed_area(poly):
    n = len(poly)
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def point_in_polygon(pt, poly):
    """Ray casting，回傳布林。"""
    x, y = pt
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_int = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside


# ==========================================
# Step 4: 識別外框與內室
# ==========================================
def classify_polygons(polygons):
    """面積最大者為外框；中心點落在外框內者為內室。"""
    if not polygons:
        return None, []
    sorted_by_area = sorted(polygons, key=lambda p: abs(signed_area(p)), reverse=True)
    outer = sorted_by_area[0]
    chambers = []
    for poly in sorted_by_area[1:]:
        cx = sum(v[0] for v in poly) / len(poly)
        cy = sum(v[1] for v in poly) / len(poly)
        if point_in_polygon((cx, cy), outer):
            chambers.append(poly)
    return outer, chambers


# ==========================================
# Step 5: 抽取中心線（+/-1 表面配對 + 厚度上限）
# ==========================================
def extract_centerlines(outer, chambers, max_thickness=MAX_WALL_THICKNESS):
    """通用化版本：對每個多邊形邊標上 +1/-1（牆材料側）後做雙向配對。
    外框走 CCW、內室走 CW，使「牆材料」一致落在邊行進方向的左側。"""
    if outer is None:
        return []

    h_surfaces, v_surfaces = [], []

    def add(poly, is_outer):
        # 標準化旋向：外框 CCW(+area)、內室 CW(-area)
        sign = signed_area(poly)
        if (is_outer and sign < 0) or ((not is_outer) and sign > 0):
            poly = poly[::-1]
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

    add(outer, is_outer=True)
    for c in chambers:
        add(c, is_outer=False)

    return _pair_surfaces(h_surfaces, max_thickness, axis="h") + \
           _pair_surfaces(v_surfaces, max_thickness, axis="v")


def _pair_surfaces(surfaces, max_thickness, axis):
    """沿主軸由小到大掃描；遇 -1 時與最近 +1（≤ max_thickness）配對成中心線。"""
    by_coord = defaultdict(list)
    for c, a, b, s in surfaces:
        by_coord[round(c, 4)].append((a, b, s))
    sorted_coords = sorted(by_coord.keys())

    centerlines = []
    pending = []  # [(coord, sec_min, sec_max), ...] 累積中的 +1 表面

    for c in sorted_coords:
        # 過期（距離超過厚度上限）的 pending 丟棄
        pending = [p for p in pending if c - p[0] <= max_thickness + 1e-6]

        # 先處理 -1（關閉牆）
        for a, b, s in by_coord[c]:
            if s != -1:
                continue
            new_pending = []
            for pc, pa, pb in pending:
                oa, ob = max(pa, a), min(pb, b)
                if ob > oa + 1e-6:
                    mid = (pc + c) / 2.0
                    if axis == "h":
                        centerlines.append(((oa, mid), (ob, mid)))
                    else:
                        centerlines.append(((mid, oa), (mid, ob)))
                    if pa < oa - 1e-6:
                        new_pending.append((pc, pa, oa))
                    if pb > ob + 1e-6:
                        new_pending.append((pc, ob, pb))
                else:
                    new_pending.append((pc, pa, pb))
            pending = new_pending

        # 再處理 +1（開啟新牆）
        for a, b, s in by_coord[c]:
            if s == +1:
                pending.append((c, a, b))

    return centerlines


# ==========================================
# Step 6: 中心線延伸到交會處（補上 raw 配對留下的縫隙）
# ==========================================
def extend_to_intersections(centerlines, max_extension=MAX_EXTENSION,
                            tol=SNAP_TOL):
    """每條 CL 的端點延伸到最近、且能涵蓋它的垂直 CL 上。"""
    h_lines = [(i, l) for i, l in enumerate(centerlines)
               if abs(l[0][1] - l[1][1]) < tol]
    v_lines = [(i, l) for i, l in enumerate(centerlines)
               if abs(l[0][0] - l[1][0]) < tol]
    out = list(centerlines)

    def _dist_to_range(v, lo, hi):
        """v 與區間 [lo, hi] 的最小距離；v 在區間內則為 0。"""
        return max(0.0, lo - v, v - hi)

    def extend_endpoints(line, perpendiculars, axis):
        """axis='h'：line 為水平，perpendiculars 為垂直 CL 列表。
        延伸條件放寬：y 不必落在垂直 CL 的 y 範圍內，
        只需「y 與垂直 CL 的 y 範圍的距離 ≤ max_extension」即可。"""
        if axis == "h":
            y = line[0][1]
            a, b = sorted([line[0][0], line[1][0]])
            cands_lo, cands_hi = [], []
            for _, pl in perpendiculars:
                px = pl[0][0]
                py1, py2 = sorted([pl[0][1], pl[1][1]])
                if _dist_to_range(y, py1, py2) <= max_extension + tol:
                    if px < a - tol and a - px <= max_extension:
                        cands_lo.append(px)
                    elif px > b + tol and px - b <= max_extension:
                        cands_hi.append(px)
            if cands_lo:
                a = max(cands_lo)
            if cands_hi:
                b = min(cands_hi)
            return ((a, y), (b, y))
        else:
            x = line[0][0]
            a, b = sorted([line[0][1], line[1][1]])
            cands_lo, cands_hi = [], []
            for _, pl in perpendiculars:
                py = pl[0][1]
                px1, px2 = sorted([pl[0][0], pl[1][0]])
                if _dist_to_range(x, px1, px2) <= max_extension + tol:
                    if py < a - tol and a - py <= max_extension:
                        cands_lo.append(py)
                    elif py > b + tol and py - b <= max_extension:
                        cands_hi.append(py)
            if cands_lo:
                a = max(cands_lo)
            if cands_hi:
                b = min(cands_hi)
            return ((x, a), (x, b))

    # 兩輪：先延伸 H 用原始 V，再延伸 V 用已延伸的 H
    for hi, hl in h_lines:
        out[hi] = extend_endpoints(hl, v_lines, axis="h")
    h_lines_updated = [(i, out[i]) for i, _ in h_lines]
    for vi, vl in v_lines:
        out[vi] = extend_endpoints(vl, h_lines_updated, axis="v")
    return out


# ==========================================
# Step 7: 建立節點-桿件模型（沿用既有邏輯）
# ==========================================
def build_model(centerlines, snap_tol=SNAP_TOL):
    nodes = []   # [(id, x, y), ...]
    elements = []  # [(id, n1, n2), ...]

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


def split_at_intersections(lines, tol=SNAP_TOL):
    """把每條線在與其他線的交點處切開。"""
    result = []
    for i, line in enumerate(lines):
        cuts = [line[0], line[1]]
        for j, other in enumerate(lines):
            if i == j:
                continue
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
        for k in range(len(unique) - 1):
            result.append((unique[k], unique[k + 1]))
    return result


def line_intersection(l1, l2):
    (x1, y1), (x2, y2) = l1
    (x3, y3), (x4, y4) = l2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def point_on_segment(pt, line, tol):
    (x1, y1), (x2, y2) = line
    return (min(x1, x2) - tol <= pt[0] <= max(x1, x2) + tol and
            min(y1, y2) - tol <= pt[1] <= max(y1, y2) + tol)


# ==========================================
# Step 8: 輸出
# ==========================================
def write_dxf(nodes, elements, filepath):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    node_dict = {nid: (x, y) for nid, x, y in nodes}
    for eid, n1, n2 in elements:
        msp.add_line(node_dict[n1], node_dict[n2],
                     dxfattribs={"layer": "ANALYTICAL"})
    for nid, x, y in nodes:
        msp.add_circle((x, y), 0.05, dxfattribs={"layer": "NODES"})
    doc.saveas(filepath)


def write_sap2000_s2k(nodes, elements, filepath):
    """輸出 SAP2000 .s2k (Interactive Database) 格式"""
    with open(filepath, "w") as f:
        f.write("TABLE:  \"PROGRAM CONTROL\"\n")
        f.write("   ProgramName=SAP2000   Version=22.0.0\n\n")

        f.write("TABLE:  \"JOINT COORDINATES\"\n")
        for nid, x, y in nodes:
            f.write(f"   Joint={nid}   CoordSys=GLOBAL   "
                    f"CoordType=Cartesian   XorR={x}   Y={y}   Z=0\n")
        f.write("\n")

        f.write("TABLE:  \"CONNECTIVITY - FRAME\"\n")
        for eid, n1, n2 in elements:
            f.write(f"   Frame={eid}   JointI={n1}   JointJ={n2}   "
                    f"IsCurved=No\n")
        f.write("\nEND TABLE DATA\n")


# ==========================================
# 主程式
# ==========================================
if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog
    import os

    # 建立隱藏的 tkinter 主視窗
    root = tk.Tk()
    root.withdraw()
    
    # 彈出檔案選擇對話框
    file_path = filedialog.askopenfilename(
        title="選擇 DXF 檔案",
        filetypes=[("DXF Files", "*.dxf"), ("All Files", "*.*")]
    )
    
    if not file_path:
        print("未選擇檔案，程式結束。")
        raise SystemExit()
        
    print(f"讀取檔案: {file_path}")
    raw = read_dxf_lines(file_path)
    print(f"讀入 {len(raw)} 條線段")

    snapped = snap_lines(raw)
    print(f"snap 後 {len(snapped)} 條")

    polygons = find_closed_polygons(snapped)
    print(f"偵測到 {len(polygons)} 個閉合多邊形")
    for p in polygons:
        xs = [v[0] for v in p]
        ys = [v[1] for v in p]
        print(f"  頂點數={len(p):2d}  bbox=({min(xs):.3f}, {min(ys):.3f})–"
              f"({max(xs):.3f}, {max(ys):.3f})  area={abs(signed_area(p)):.3f}")

    outer, chambers = classify_polygons(polygons)
    if outer is None:
        raise SystemExit("找不到外框")
    print(f"外框頂點數: {len(outer)}")
    print(f"內室: {len(chambers)} 個")

    raw_cls = extract_centerlines(outer, chambers)
    print(f"原始中心線 {len(raw_cls)} 條")

    centerlines = raw_cls
    for _ in range(3):          # 多輪延伸：讓步階接點收斂
        centerlines = extend_to_intersections(centerlines)
    print(f"延伸後 {len(centerlines)} 條")

    nodes, elements = build_model(centerlines)
    print(f"節點 {len(nodes)} 個, 桿件 {len(elements)} 條")

    # 根據輸入的檔案路徑，產生輸出檔名
    base_name = os.path.splitext(file_path)[0]
    out_dxf = f"{base_name}_analytical.dxf"
    out_s2k = f"{base_name}.s2k"

    write_dxf(nodes, elements, out_dxf)
    write_sap2000_s2k(nodes, elements, out_s2k)
    print(f"完成！已輸出:\n  - {out_dxf}\n  - {out_s2k}")
