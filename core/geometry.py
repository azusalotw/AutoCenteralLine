# 基礎幾何工具：面積、點在多邊形、線段交點

from .constants import SNAP_TOL


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
