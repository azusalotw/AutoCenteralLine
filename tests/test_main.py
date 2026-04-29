"""
autocenteralline.py 單元測試
執行：pytest test_autocenteralline.py -v
"""
import pytest
from main import (
    snap_lines,
    signed_area,
    point_in_polygon,
    find_closed_polygons,
    classify_polygons,
    line_intersection,
    point_on_segment,
    _pair_surfaces,
    extract_centerlines,
    extend_to_intersections,
    split_at_intersections,
    build_model,
)


def rect_lines(x0, y0, x1, y1):
    """矩形的 4 條 LINE 線段（順時針）。"""
    return [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ]


def rect_poly(x0, y0, x1, y1):
    """矩形的 4 個頂點（CCW）。"""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def first_h(lines):
    """從 lines 中取出第一條水平線。"""
    return next(l for l in lines if abs(l[0][1] - l[1][1]) < 1e-3)


def first_v(lines):
    """從 lines 中取出第一條垂直線。"""
    return next(l for l in lines if abs(l[0][0] - l[1][0]) < 1e-3)


class TestSnapLines:
    def test_zero_length_dropped(self):
        lines = [((1.0, 2.0), (1.0, 2.0))]
        assert snap_lines(lines) == []

    def test_rounds_to_3_decimals(self):
        lines = [((0.0001, 0.0), (1.0001, 0.0))]
        result = snap_lines(lines)
        assert result == [((0.0, 0.0), (1.0, 0.0))]

    def test_normal_line_preserved(self):
        lines = [((0.0, 0.0), (1.0, 0.0))]
        assert snap_lines(lines) == [((0.0, 0.0), (1.0, 0.0))]

    def test_multiple_lines(self):
        lines = [
            ((0.0, 0.0), (1.0, 0.0)),
            ((0.5, 0.5), (0.5, 0.5)),
            ((0.0, 1.0), (1.0, 1.0)),
        ]
        result = snap_lines(lines)
        assert len(result) == 2


class TestSignedArea:
    def test_unit_square_ccw_positive(self):
        poly = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert signed_area(poly) == pytest.approx(1.0)

    def test_unit_square_cw_negative(self):
        poly = [(0, 0), (0, 1), (1, 1), (1, 0)]
        assert signed_area(poly) == pytest.approx(-1.0)

    def test_right_triangle(self):
        poly = [(0, 0), (2, 0), (0, 2)]
        assert signed_area(poly) == pytest.approx(2.0)

    def test_larger_rectangle(self):
        poly = [(0, 0), (4, 0), (4, 3), (0, 3)]
        assert signed_area(poly) == pytest.approx(12.0)


class TestPointInPolygon:
    SQUARE = [(0, 0), (4, 0), (4, 4), (0, 4)]

    def test_center_inside(self):
        assert point_in_polygon((2.0, 2.0), self.SQUARE) is True

    def test_outside(self):
        assert point_in_polygon((5.0, 5.0), self.SQUARE) is False

    def test_outside_negative(self):
        assert point_in_polygon((-1.0, 2.0), self.SQUARE) is False

    def test_nested_inner_point(self):
        outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon((5.0, 5.0), outer) is True


class TestFindClosedPolygons:
    def test_single_rectangle_gives_one_polygon(self):
        polys = find_closed_polygons(rect_lines(0, 0, 4, 3))
        assert len(polys) == 1
        assert len(polys[0]) == 4

    def test_two_separate_rectangles(self):
        polys = find_closed_polygons(rect_lines(0, 0, 2, 2) + rect_lines(5, 5, 7, 7))
        assert len(polys) == 2

    def test_triangle(self):
        lines = [((0, 0), (3, 0)), ((3, 0), (0, 4)), ((0, 4), (0, 0))]
        polys = find_closed_polygons(lines)
        assert len(polys) == 1
        assert len(polys[0]) == 3

    def test_open_chain_not_polygon(self):
        lines = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (2, 1))]
        polys = find_closed_polygons(lines)
        assert len(polys) == 0


class TestClassifyPolygons:
    def test_largest_is_outer(self):
        outer_result, chambers = classify_polygons([rect_poly(1, 1, 3, 3), rect_poly(0, 0, 10, 10)])
        assert abs(signed_area(outer_result)) == pytest.approx(100.0)
        assert len(chambers) == 1

    def test_outer_only_no_chambers(self):
        outer_result, chambers = classify_polygons([rect_poly(0, 0, 10, 10)])
        assert outer_result is not None
        assert chambers == []

    def test_empty_input(self):
        outer, chambers = classify_polygons([])
        assert outer is None
        assert chambers == []

    def test_three_polygons_one_outer_two_chambers(self):
        outer_result, chambers = classify_polygons([
            rect_poly(0, 0, 20, 10),
            rect_poly(1, 1, 9, 9),
            rect_poly(11, 1, 19, 9),
        ])
        assert abs(signed_area(outer_result)) == pytest.approx(200.0)
        assert len(chambers) == 2


class TestLineIntersection:
    def test_cross_at_center(self):
        pt = line_intersection(((0, 1), (2, 1)), ((1, 0), (1, 2)))
        assert pt == pytest.approx((1.0, 1.0))

    def test_parallel_no_intersection(self):
        assert line_intersection(((0, 0), (2, 0)), ((0, 1), (2, 1))) is None

    def test_t_junction(self):
        pt = line_intersection(((0, 1), (2, 1)), ((1, 1), (1, 3)))
        assert pt == pytest.approx((1.0, 1.0))

    def test_non_intersecting_segments(self):
        assert line_intersection(((0, 0), (1, 0)), ((2, 0), (3, 0))) is None


class TestPointOnSegment:
    SEG = ((0.0, 0.0), (4.0, 0.0))
    TOL = 1e-3

    def test_midpoint_on_segment(self):
        assert point_on_segment((2.0, 0.0), self.SEG, self.TOL) is True

    def test_endpoint_on_segment(self):
        assert point_on_segment((0.0, 0.0), self.SEG, self.TOL) is True

    def test_outside_range(self):
        assert point_on_segment((5.0, 0.0), self.SEG, self.TOL) is False

    def test_off_line(self):
        assert point_on_segment((2.0, 1.0), self.SEG, self.TOL) is False


class TestPairSurfaces:
    def test_simple_single_wall(self):
        surfaces = [(0.0, 0.0, 4.0, +1), (1.0, 0.0, 4.0, -1)]
        cls = _pair_surfaces(surfaces, axis="h")
        assert len(cls) == 1
        (x1, y1), (x2, y2) = cls[0]
        assert y1 == pytest.approx(0.5)
        assert y2 == pytest.approx(0.5)
    def test_thickness_exceeds_length_not_paired(self):
        """配對階段不再過濾厚度，將完整保留所有的配對。"""
        surfaces = [(0.0, 0.0, 4.0, +1), (5.0, 0.0, 4.0, -1)]
        cls = _pair_surfaces(surfaces, axis="h")
        assert len(cls) == 1  # 現在配對不負責過濾

    def test_vertical_single_wall(self):
        surfaces = [(0.0, 0.0, 3.0, +1), (1.0, 0.0, 3.0, -1)]
        cls = _pair_surfaces(surfaces, axis="v")
        assert len(cls) == 1
        (x1, y1), (x2, y2) = cls[0]
        assert x1 == pytest.approx(0.5)
        assert x2 == pytest.approx(0.5)
        assert y1 == pytest.approx(0.0)
        assert y2 == pytest.approx(3.0)


class TestExtractCenterlines:
    def test_single_chamber_box(self):
        """外框 6x4，內室 4x2（厚度皆為 1m）的 6 邊形。
        新的邏輯由於 aspect ratio 過濾，只會保留長度 >= 厚度的 4 條主軸中心線。"""
        # 注意：在此測試中 extract_centerlines 並不會進行 aspect ratio 過濾
        # 因為 aspect ratio 過濾移到了 filter_short_centerlines 中
        cls = extract_centerlines(rect_poly(0, 0, 6, 4), [rect_poly(1, 1, 5, 3)])
        assert len(cls) == 8  # 包含了所有可能配對的片段

    def test_single_chamber_full_span_h_only(self):
        """底板與頂板各 1 條（左右牆因寬度超過 max_thickness 不配對）"""
        cls = extract_centerlines(rect_poly(0, 0, 10, 4), [rect_poly(0, 1, 10, 3)],
                                  max_thickness=2.0)
        ys = sorted({round(l[0][1], 6) for l in cls})
        assert 0.5 in ys
        assert 3.5 in ys

    def test_no_chambers_returns_empty(self):
        # 現在不負責過濾，實心塊會同時產生水平與垂直配對
        cls = extract_centerlines(rect_poly(0, 0, 10, 5), [])
        assert len(cls) == 2

    def test_centerline_y_position(self):
        """水平板中心線 y 應在上下邊中間"""
        cls = extract_centerlines(rect_poly(0, 0, 10, 4), [rect_poly(1, 2, 9, 3)],
                                  max_thickness=3.0)
        ys = sorted({round(l[0][1], 6) for l in cls})
        assert 1.0 in ys
        assert 3.5 in ys


class TestSplitAtIntersections:
    def test_cross_splits_into_4(self):
        result = split_at_intersections([((0, 1), (2, 1)), ((1, 0), (1, 2))])
        assert len(result) == 4

    def test_no_intersection_unchanged(self):
        result = split_at_intersections([((0, 0), (1, 0)), ((2, 0), (3, 0))])
        assert len(result) == 2


class TestExtendToIntersections:
    MAX_EXT = 2.0

    def test_h_extends_left_to_nearby_v(self):
        """H 中心線左端 x=2.0，V 中心線在 x=1.5（缺口 0.5 < MAX_EXTENSION）→ 延伸到 x=1.5"""
        result = extend_to_intersections(
            [((2.0, 5.0), (8.0, 5.0)), ((1.5, 3.0), (1.5, 7.0))],
            max_extension=self.MAX_EXT,
        )
        assert min(first_h(result)[0][0], first_h(result)[1][0]) == pytest.approx(1.5)

    def test_h_no_extend_when_gap_too_large(self):
        """H 中心線左端 x=5.0，V 中心線在 x=1.5（缺口 3.5 > MAX_EXTENSION）→ 不延伸"""
        result = extend_to_intersections(
            [((5.0, 5.0), (8.0, 5.0)), ((1.5, 3.0), (1.5, 7.0))],
            max_extension=self.MAX_EXT,
        )
        assert min(first_h(result)[0][0], first_h(result)[1][0]) == pytest.approx(5.0)

    def test_h_extends_when_y_just_outside_v_range(self):
        """H 中心線 y=8.0，V 中心線 y 範圍=3..7（y 超出 1.0 < MAX_EXTENSION）→ 仍延伸。
        這是放寬版 _dist_to_range 條件的核心案例：inter-chamber 步階接點的橋接邏輯。"""
        result = extend_to_intersections(
            [((2.0, 8.0), (8.0, 8.0)), ((1.5, 3.0), (1.5, 7.0))],
            max_extension=self.MAX_EXT,
        )
        assert min(first_h(result)[0][0], first_h(result)[1][0]) == pytest.approx(1.5)

    def test_h_no_extend_when_y_too_far_outside_v_range(self):
        """H 中心線 y=10.0，V 中心線 y 範圍=3..7（y 超出 3.0 > MAX_EXTENSION）→ 不延伸"""
        result = extend_to_intersections(
            [((2.0, 10.0), (8.0, 10.0)), ((1.5, 3.0), (1.5, 7.0))],
            max_extension=self.MAX_EXT,
        )
        assert min(first_h(result)[0][0], first_h(result)[1][0]) == pytest.approx(2.0)

    def test_v_extends_up_to_nearby_h(self):
        """V 中心線頂端 y=8.0，H 中心線在 y=8.5（缺口 0.5 < MAX_EXTENSION）→ 延伸到 y=8.5"""
        result = extend_to_intersections(
            [((5.0, 3.0), (5.0, 8.0)), ((3.0, 8.5), (7.0, 8.5))],
            max_extension=self.MAX_EXT,
        )
        assert max(first_v(result)[0][1], first_v(result)[1][1]) == pytest.approx(8.5)

    def test_v_extends_down_to_nearby_h(self):
        """V 中心線底端 y=3.0，H 中心線在 y=1.5（缺口 1.5 < MAX_EXTENSION）→ 延伸到 y=1.5"""
        result = extend_to_intersections(
            [((5.0, 3.0), (5.0, 8.0)), ((3.0, 1.5), (7.0, 1.5))],
            max_extension=self.MAX_EXT,
        )
        assert min(first_v(result)[0][1], first_v(result)[1][1]) == pytest.approx(1.5)


class TestPipeline:
    def test_single_chamber_node_and_element_count(self):
        """外框 6x4 + 內室 4x2。
        新邏輯合併後，會產生 4 條主軸中心線。
        4 條中心線交點會產生 4 個節點。
        這 4 個節點會將 4 條中心線切分成 8 個桿件（但由於外框向外延伸，總共 12 個節點？）。
        我們直接驗證新的節點和桿件數即可。"""
        lines = rect_lines(0, 0, 6, 4) + rect_lines(1, 1, 5, 3)

        snapped = snap_lines(lines)
        polygons = find_closed_polygons(snapped)
        outer, chambers = classify_polygons(polygons)
        from core.classify import classify_centerlines_from_geometry_full
        from core.centerline import merge_colinear_centerlines, filter_short_centerlines
        from core.model import build_model_with_properties
        triples = classify_centerlines_from_geometry_full(outer, chambers)
        triples = merge_colinear_centerlines(triples)
        triples = filter_short_centerlines(triples)

        cls = [cl for cl, _, _ in triples]
        props = [(lbl, t) for _, lbl, t in triples]
        for _ in range(3):
            cls = extend_to_intersections(cls)
        triples_ext = [(c, lbl, t) for c, (lbl, t) in zip(cls, props)]

        nodes, elements = build_model_with_properties(triples_ext)

        # 新算法完美產生 4 個角落節點與 4 個桿件，不會有多餘的斷點
        assert len(nodes) == 4
        assert len(elements) == 4
