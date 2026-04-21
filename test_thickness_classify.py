"""
厚度分類功能測試
執行：pytest test_thickness_classify.py -v
"""
import pytest
import ezdxf
from autocenteralline import (
    build_model_with_properties,
    classify_by_thickness,
    classify_centerlines,
    classify_centerlines_full,
    classify_centerlines_from_geometry,
    classify_centerlines_from_geometry_full,
    extract_centerlines_with_thickness,
    write_dxf_classified,
)


class TestClassifyByThickness:
    def test_thin_member_is_platform(self):
        assert classify_by_thickness(0.1) == "月台"

    def test_thick_member_is_main_structure(self):
        """三角測量：確認厚 0.5m 的構件確實回傳「主結構」，而非兩者都回傳「月台」。"""
        assert classify_by_thickness(0.5) == "主結構"

    def test_boundary_exactly_threshold_is_platform(self):
        """邊界：恰好 0.2m（= threshold）→ 應為「月台」（<= 包含等於）。"""
        assert classify_by_thickness(0.2) == "月台"

    def test_just_over_threshold_is_main_structure(self):
        """邊界：0.201m（略超 threshold）→ 應為「主結構」。"""
        assert classify_by_thickness(0.201) == "主結構"


class TestClassifyCenterlines:
    def test_single_thin_centerline(self):
        """一條薄中心線（0.1m）→ 回傳 [(中心線, '月台')]。"""
        cl = ((0.0, 0.0), (1.0, 0.0))
        result = classify_centerlines([(cl, 0.1)])
        assert result == [(cl, "月台")]

    def test_mixed_centerlines_classified_independently(self):
        """三角測量：混合輸入，每條依自己的厚度獨立分類，順序保留。"""
        cl1 = ((0.0, 0.0), (1.0, 0.0))  # 0.1m → 月台
        cl2 = ((0.0, 1.0), (1.0, 1.0))  # 0.5m → 主結構
        result = classify_centerlines([(cl1, 0.1), (cl2, 0.5)])
        assert result == [(cl1, "月台"), (cl2, "主結構")]


class TestClassifyCenterlinesFromGeometry:
    def test_mixed_geometry_produces_both_labels(self):
        """端對端：外框 2×1 + 內室（薄板 0.1m，厚牆 0.5m）→ 同時出現「月台」與「主結構」。
        幾何：outer 2×1、inner 0.5..1.5 × 0.1..0.9
          底板/頂板厚 0.1m ≤ 0.2m → 月台
          左牆/右牆厚 0.5m > 0.2m → 主結構"""
        outer = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]
        inner = [(0.5, 0.1), (1.5, 0.1), (1.5, 0.9), (0.5, 0.9)]
        labeled = classify_centerlines_from_geometry(outer, [inner], max_thickness=1.0)
        labels = {label for _, label in labeled}
        assert "月台" in labels
        assert "主結構" in labels


class TestClassifyCenterlinesFullWithThicknessPreserved:
    def test_returns_label_and_thickness_as_triple(self):
        """classify_centerlines_full 保留厚度：回傳 [(中心線, 標籤, 厚度), ...]。"""
        cl = ((0.0, 0.0), (1.0, 0.0))
        result = classify_centerlines_full([(cl, 0.15)])
        centerline, label, thickness = result[0]
        assert centerline == cl
        assert label == "月台"
        assert thickness == pytest.approx(0.15)

    def test_thick_member_preserves_main_structure_label_and_thickness(self):
        """三角測量：厚 0.5m 的構件 → 標籤「主結構」且厚度值保留為 0.5。"""
        cl = ((0.0, 0.0), (1.0, 0.0))
        result = classify_centerlines_full([(cl, 0.5)])
        centerline, label, thickness = result[0]
        assert centerline == cl
        assert label == "主結構"
        assert thickness == pytest.approx(0.5)


class TestClassifyCenterlinesFromGeometryFull:
    def test_geometry_returns_triples_with_both_labels(self):
        """幾何管線全輸出：outer 2×1 + inner（薄板 0.1m、厚牆 0.5m）→
        三元組同時出現「月台」與「主結構」，且各自厚度值正確保留。"""
        outer = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]
        inner = [(0.5, 0.1), (1.5, 0.1), (1.5, 0.9), (0.5, 0.9)]
        result = classify_centerlines_from_geometry_full(outer, [inner], max_thickness=1.0)
        labels = {label for _, label, _ in result}
        thicknesses_by_label = {label: t for _, label, t in result}
        assert "月台" in labels
        assert "主結構" in labels
        assert thicknesses_by_label["月台"] == pytest.approx(0.1)
        assert thicknesses_by_label["主結構"] == pytest.approx(0.5)


class TestWriteDxfClassified:
    def test_creates_platform_and_main_structure_layers(self, tmp_path):
        """分類 DXF 輸出：月台 → layer='PLATFORM'，主結構 → layer='MAIN_STRUCTURE'。"""
        cl1 = ((0.0, 0.0), (1.0, 0.0))
        cl2 = ((0.0, 1.0), (1.0, 1.0))
        labeled = [(cl1, "月台"), (cl2, "主結構")]
        out = str(tmp_path / "classified.dxf")
        write_dxf_classified(labeled, out)
        doc = ezdxf.readfile(out)
        layer_names = {e.dxf.layer for e in doc.modelspace()}
        assert "PLATFORM" in layer_names
        assert "MAIN_STRUCTURE" in layer_names


class TestBuildModelWithProperties:
    def test_elements_carry_label_and_thickness(self):
        """build_model_with_properties：兩條不相交的中心線 → 2 個桿件，
        各自帶有正確的 label 和 thickness。
        桿件格式：(id, n1, n2, label, thickness)。
        主結構先編號（ID=1），月台後編號（ID=2）。"""
        cl1 = ((0.0, 0.0), (4.0, 0.0))  # 水平，月台 0.1m
        cl2 = ((0.0, 2.0), (4.0, 2.0))  # 水平，主結構 0.5m
        triples = [(cl1, "月台", 0.1), (cl2, "主結構", 0.5)]
        _, elements = build_model_with_properties(triples)
        assert len(elements) == 2
        props = {eid: (label, t) for eid, _, _, label, t in elements}
        assert props[1] == ("主結構", pytest.approx(0.5))
        assert props[2] == ("月台", pytest.approx(0.1))

    def test_split_segments_inherit_source_thickness(self):
        """三角測量：兩條中心線相交 → split 後產生 4 個桿件，
        水平線的兩段均帶厚度 0.1m，垂直線的兩段均帶厚度 0.5m。"""
        cl_h = ((0.0, 1.0), (4.0, 1.0))  # 水平，月台 0.1m
        cl_v = ((2.0, 0.0), (2.0, 3.0))  # 垂直，主結構 0.5m
        triples = [(cl_h, "月台", 0.1), (cl_v, "主結構", 0.5)]
        _, elements = build_model_with_properties(triples)
        assert len(elements) == 4
        labels = [label for _, _, _, label, _ in elements]
        assert labels.count("月台") == 2
        assert labels.count("主結構") == 2
        h_thicknesses = [t for _, _, _, lbl, t in elements if lbl == "月台"]
        v_thicknesses = [t for _, _, _, lbl, t in elements if lbl == "主結構"]
        assert all(t == pytest.approx(0.1) for t in h_thicknesses)
        assert all(t == pytest.approx(0.5) for t in v_thicknesses)

    def test_main_structure_ids_precede_platform_ids(self):
        """排序：月台輸入在前，主結構在後 → 輸出中所有主結構 ID < 所有月台 ID。
        確保不管輸入順序，主結構桿件編號永遠先於月台桿件。"""
        cl1 = ((0.0, 0.0), (4.0, 0.0))  # 月台 — 輸入在前
        cl2 = ((0.0, 2.0), (4.0, 2.0))  # 主結構 — 輸入在後
        triples = [(cl1, "月台", 0.1), (cl2, "主結構", 0.5)]
        _, elements = build_model_with_properties(triples)
        main_ids = [eid for eid, _, _, lbl, _ in elements if lbl == "主結構"]
        platform_ids = [eid for eid, _, _, lbl, _ in elements if lbl == "月台"]
        assert max(main_ids) < min(platform_ids)


class TestExtractCenterlinesWithThickness:
    def test_geometry_produces_thickness_pairs(self):
        """整合：外框 6×4 + 內室各邊 1m 厚，max_thickness=2.0 → 4 條主構件厚度均為 1.0m。
        不加 max_thickness 則角落殘餘段會與外框對側配對得厚度 4.0m（此為正確演算法行為，
        測試此處明確給定上限以隔離主構件）。"""
        outer = [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)]
        inner = [(1.0, 1.0), (5.0, 1.0), (5.0, 3.0), (1.0, 3.0)]
        pairs = extract_centerlines_with_thickness(outer, [inner], max_thickness=2.0)
        thicknesses = [t for _, t in pairs]
        assert all(t == pytest.approx(1.0) for t in thicknesses)
