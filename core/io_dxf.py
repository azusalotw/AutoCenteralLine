# DXF 讀取與輸出

import ezdxf

from .constants import SNAP_TOL, _LABEL_TO_LAYER, _ID_H


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


def write_dxf(nodes, elements, filepath):
    doc = ezdxf.new("R2010")
    doc.styles.new("MSJH", dxfattribs={"font": "微軟正黑體"})
    msp = doc.modelspace()
    node_dict = {nid: (x, y) for nid, x, y in nodes}

    for eid, n1, n2, *extra in elements:
        label = extra[0] if extra else None
        layer = _LABEL_TO_LAYER.get(label, "ANALYTICAL")
        x1, y1 = node_dict[n1]
        x2, y2 = node_dict[n2]
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})

        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # 垂直桿件：編號往右偏；水平桿件：編號往上偏
        is_vert = abs(x2 - x1) < SNAP_TOL
        off = (_ID_H * 0.6 if is_vert else 0,
               0 if is_vert else _ID_H * 0.6)
        msp.add_text(str(eid), dxfattribs={"layer": layer, "height": _ID_H,
                                           "insert": (mx + off[0], my + off[1]),
                                           "style": "MSJH", "color": 2})

    for nid, x, y in nodes:
        msp.add_circle((x, y), 0.05, dxfattribs={"layer": "NODES"})
        msp.add_text(str(nid), dxfattribs={"layer": "NODES", "height": _ID_H,
                                           "insert": (x + 0.15, y + 0.15),
                                           "style": "MSJH", "color": 4})
    doc.saveas(filepath)


def write_dxf_classified(labeled_centerlines, filepath):
    """將帶分類標籤的中心線輸出為 DXF，依標籤分層：
    '月台' → layer='PLATFORM'，'主結構' → layer='MAIN_STRUCTURE'。"""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for (p1, p2), label in labeled_centerlines:
        layer = _LABEL_TO_LAYER.get(label, "ANALYTICAL")
        msp.add_line(p1, p2, dxfattribs={"layer": layer})
    doc.saveas(filepath)
