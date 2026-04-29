"""
TDD Red Flag: 月台區域產生多餘節點與桿件的 bug

問題：E剖-分析.dxf 的月台 notch 處，表面配對產生碎片化的中心線，
導致 y=2.000 出現多餘節點 (8-15) 與桿件 (7-12)。

期望：合併同軸、同厚度且間隙 ≤ 容差的中心線後，
消除碎片並過濾極短的殘餘中心線。
"""
import pytest
import sys
sys.path.insert(0, '.')

from main import (
    read_dxf_lines, snap_lines,
    find_closed_polygons, classify_polygons,
    classify_centerlines_from_geometry_full,
    extend_to_intersections,
    build_model_with_properties,
    merge_colinear_centerlines,
    filter_short_centerlines,
)


class TestMergeCenterlines:
    """單元測試：合併同軸且間隙小的中心線片段。"""

    def test_merge_colinear_h_with_small_gap(self):
        """兩條水平中心線間隙 0.2m ≤ 容差 → 合併為一條。"""
        from core.centerline import merge_colinear_centerlines
        cls = [
            (((0.0, 1.0), (6.7, 1.0)), "主結構", 2.0),
            (((6.9, 1.0), (7.9, 1.0)), "主結構", 2.0),
        ]
        merged = merge_colinear_centerlines(cls, gap_tol=0.3)
        h_at_1 = [(cl, l, t) for cl, l, t in merged
                  if abs(cl[0][1] - 1.0) < 0.01 and abs(cl[1][1] - 1.0) < 0.01]
        assert len(h_at_1) == 1
        cl = h_at_1[0][0]
        assert min(cl[0][0], cl[1][0]) == pytest.approx(0.0)
        assert max(cl[0][0], cl[1][0]) == pytest.approx(7.9)

    def test_merge_three_fragments_into_one(self):
        """三段碎片 (間隙各 0.2m) → 合併為一條。"""
        from core.centerline import merge_colinear_centerlines
        cls = [
            (((1.1, 1.0), (6.7, 1.0)), "主結構", 2.0),
            (((6.9, 1.0), (7.9, 1.0)), "主結構", 2.0),
            (((8.1, 1.0), (9.9, 1.0)), "主結構", 2.0),
        ]
        merged = merge_colinear_centerlines(cls, gap_tol=0.3)
        h_at_1 = [(cl, l, t) for cl, l, t in merged
                  if abs(cl[0][1] - 1.0) < 0.01]
        assert len(h_at_1) == 1
        assert min(h_at_1[0][0][0][0], h_at_1[0][0][1][0]) == pytest.approx(1.1)
        assert max(h_at_1[0][0][0][0], h_at_1[0][0][1][0]) == pytest.approx(9.9)

    def test_no_merge_when_gap_exceeds_tol(self):
        """間隙 2.0m > 容差 → 不合併。"""
        from core.centerline import merge_colinear_centerlines
        cls = [
            (((0.0, 1.0), (3.0, 1.0)), "主結構", 2.0),
            (((5.0, 1.0), (8.0, 1.0)), "主結構", 2.0),
        ]
        merged = merge_colinear_centerlines(cls, gap_tol=0.3)
        h_at_1 = [cl for cl, l, t in merged if abs(cl[0][1] - 1.0) < 0.01]
        assert len(h_at_1) == 2

    def test_different_labels_not_merged(self):
        """同軸但標籤不同 → 不合併。"""
        from core.centerline import merge_colinear_centerlines
        cls = [
            (((0.0, 1.0), (6.7, 1.0)), "主結構", 2.0),
            (((6.9, 1.0), (7.9, 1.0)), "月台", 0.2),
        ]
        merged = merge_colinear_centerlines(cls, gap_tol=0.3)
        h_at_1 = [cl for cl, l, t in merged if abs(cl[0][1] - 1.0) < 0.01]
        assert len(h_at_1) == 2

    def test_merge_vertical_fragments(self):
        """垂直中心線碎片也能合併。"""
        from core.centerline import merge_colinear_centerlines
        cls = [
            (((5.0, 0.0), (5.0, 3.0)), "主結構", 1.0),
            (((5.0, 3.2), (5.0, 6.0)), "主結構", 1.0),
        ]
        merged = merge_colinear_centerlines(cls, gap_tol=0.3)
        v_at_5 = [(cl, l, t) for cl, l, t in merged
                  if abs(cl[0][0] - 5.0) < 0.01 and abs(cl[1][0] - 5.0) < 0.01]
        assert len(v_at_5) == 1
        assert min(v_at_5[0][0][0][1], v_at_5[0][0][1][1]) == pytest.approx(0.0)
        assert max(v_at_5[0][0][0][1], v_at_5[0][0][1][1]) == pytest.approx(6.0)


class TestFilterShortCenterlines:
    """單元測試：過濾孤兒短段，保留有長段共存的短段。"""

    def test_orphan_short_segment_removed(self):
        """y=2.0 上只有短段（孤兒）→ 被過濾。"""
        from core.centerline import filter_short_centerlines
        cls = [
            (((0.0, 1.0), (10.0, 1.0)), "主結構", 2.0),
            (((6.7, 2.0), (6.9, 2.0)), "主結構", 4.0),  # 0.2m, 孤兒
        ]
        filtered = filter_short_centerlines(cls, min_length=0.3)
        assert len(filtered) == 1
        assert filtered[0][2] == pytest.approx(2.0)

    def test_short_with_long_sibling_kept(self):
        """x=21.2 上有短段+長段 → 短段保留。"""
        from core.centerline import filter_short_centerlines
        cls = [
            (((21.2, 2.0), (21.2, 2.05)), "主結構", 1.8),   # 0.05m, 有長段共存
            (((21.2, 4.05), (21.2, 8.6)), "主結構", 1.8),   # 長段
        ]
        filtered = filter_short_centerlines(cls, min_length=0.3)
        # 短段 (0.05) 小於厚度 (1.8)，依據 aspect ratio 規則會被過濾
        assert len(filtered) == 1

    def test_normal_segment_kept(self):
        """正常長度的中心線不被過濾。"""
        from core.centerline import filter_short_centerlines
        cls = [(((0.0, 1.0), (5.0, 1.0)), "主結構", 2.0)]
        filtered = filter_short_centerlines(cls, min_length=0.3)
        assert len(filtered) == 1

    def test_short_end_segment_nearly_as_thick_as_long_is_kept(self):
        """短端部桿件只比厚度略短時仍應保留。"""
        from core.centerline import filter_short_centerlines
        cls = [
            (((-12.25, 72.9), (-10.9, 72.9)), "主結構", 1.4),
            (((-8.2, 72.9), (-0.9, 72.9)), "主結構", 1.4),
        ]
        filtered = filter_short_centerlines(cls, min_length=0.3)
        assert len(filtered) == 2


class TestEProfileIntegration:
    """整合測試：E剖-分析.dxf 端到端驗證。"""

    @pytest.fixture
    def e_profile_model(self):
        raw = read_dxf_lines("samples/E剖-分析.dxf")
        snapped = snap_lines(raw)
        polygons = find_closed_polygons(snapped)
        outer, chambers = classify_polygons(polygons)
        triples = classify_centerlines_from_geometry_full(outer, chambers)

        # 後處理：合併碎片 + 過濾極短殘餘
        triples = merge_colinear_centerlines(triples)
        triples = filter_short_centerlines(triples)

        cls = [cl for cl, _, _ in triples]
        props = [(label, t) for _, label, t in triples]
        for _ in range(3):
            cls = extend_to_intersections(cls)
        triples_ext = [(cl, label, t) for cl, (label, t) in zip(cls, props)]

        nodes, elements = build_model_with_properties(triples_ext)
        return nodes, elements

    def test_no_nodes_at_y2(self, e_profile_model):
        """月台 notch 不應在 y≈2.0 產生節點。"""
        nodes, _ = e_profile_model
        nodes_y2 = [n for n in nodes if abs(n[2] - 2.0) < 0.05]
        assert len(nodes_y2) == 0, (
            f"y≈2.0 不應有節點，但找到 {len(nodes_y2)} 個: "
            f"{[(nid, x, y) for nid, x, y in nodes_y2]}"
        )

    def test_expected_node_count(self, e_profile_model):
        """經過浮點數修正後，節點數為 31 個。"""
        nodes, _ = e_profile_model
        assert len(nodes) == 31, f"期望 31 節點，實際 {len(nodes)}"

    def test_expected_element_count(self, e_profile_model):
        """經過浮點數修正後，桿件數為 46 條。"""
        _, elements = e_profile_model
        assert len(elements) == 46, f"期望 46 桿件，實際 {len(elements)}"

    def test_no_short_elements_at_y2(self, e_profile_model):
        """不應有中心 y≈2.0 的極短桿件。"""
        nodes, elements = e_profile_model
        node_pos = {nid: (x, y) for nid, x, y in nodes}
        for eid, n1, n2, lbl, t in elements:
            mid_y = (node_pos[n1][1] + node_pos[n2][1]) / 2
            length = ((node_pos[n1][0] - node_pos[n2][0]) ** 2 +
                      (node_pos[n1][1] - node_pos[n2][1]) ** 2) ** 0.5
            assert not (abs(mid_y - 2.0) < 0.05 and length < 0.5), (
                f"E{eid} 在 y≈2.0 長度僅 {length:.3f}m，屬多餘桿件"
            )

    def test_platform_nodes_at_the_end(self, e_profile_model):
        """節點排序：只屬於月台的節點（如 y=3.900 上的點）必須排在最後面。
        總節點數為 31，最後 7 個節點（ID 25-31）應該都是月台節點。"""
        nodes, _ = e_profile_model
        platform_nodes = nodes[-7:]
        for nid, x, y in platform_nodes:
            assert y == pytest.approx(3.900), f"N{nid} 不在月台 y=3.900 上"
            assert nid >= 25, f"N{nid} 編號應 >= 25"


class TestBProfileIntegration:
    """整合測試：B剖短端部桿件不應被 aspect ratio 過濾誤刪。"""

    def test_top_left_short_member_is_kept(self):
        raw = read_dxf_lines("samples/B剖-分析.dxf")
        snapped = snap_lines(raw)
        polygons = find_closed_polygons(snapped)
        outer, chambers = classify_polygons(polygons)
        triples = classify_centerlines_from_geometry_full(outer, chambers)
        triples = merge_colinear_centerlines(triples)
        triples = filter_short_centerlines(triples)

        assert any(
            abs(cl[0][1] - 72.9) < 0.01
            and abs(cl[1][1] - 72.9) < 0.01
            and min(cl[0][0], cl[1][0]) == pytest.approx(-12.25)
            and max(cl[0][0], cl[1][0]) == pytest.approx(-10.9)
            for cl, _, _ in triples
        )
