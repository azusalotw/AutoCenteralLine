# 閉合多邊形偵測與分類

from collections import defaultdict

from .geometry import signed_area, point_in_polygon


def _trace_polygon(adj, start, visited):
    """從 start 沿鄰接表走一圈，回傳 (polygon, ok)。
    成功條件：每個節點度數恰好為 2，且能回到 start。"""
    polygon = [start]
    visited.add(start)
    prev, current = None, start
    while True:
        nbrs = adj[current]
        if len(nbrs) != 2:
            return polygon, False
        nxt = nbrs[0] if nbrs[0] != prev else nbrs[1]
        if nxt == start:
            return polygon, True
        if nxt in visited:
            return polygon, False
        polygon.append(nxt)
        visited.add(nxt)
        prev, current = current, nxt


def find_closed_polygons(lines):
    """每個連通分量假設為簡單閉合多邊形（每頂點度數為 2）。
    回傳 [polygon, ...]，每個 polygon 是順序排列的頂點列表。"""
    adj = defaultdict(list)
    for p1, p2 in lines:
        adj[p1].append(p2)
        adj[p2].append(p1)

    polygons = []
    visited = set()
    for start in adj:
        if start in visited:
            continue
        polygon, ok = _trace_polygon(adj, start, visited)
        if ok and len(polygon) >= 3:
            polygons.append(polygon)
    return polygons


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
