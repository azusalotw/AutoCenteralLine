# 依厚度分類結構構件

from .constants import PLATFORM_THICKNESS_THRESHOLD, MAX_WALL_THICKNESS
from .centerline import extract_centerlines_with_thickness


def classify_by_thickness(thickness, threshold=PLATFORM_THICKNESS_THRESHOLD):
    """依厚度分類構件：≤ threshold → '月台'；其餘 → '主結構'。"""
    return "月台" if thickness <= threshold else "主結構"


def classify_centerlines(centerlines_with_thickness,
                         threshold=PLATFORM_THICKNESS_THRESHOLD):
    """將 [(中心線, 厚度), ...] 批次分類，回傳 [(中心線, 分類字串), ...]。"""
    return [(cl, classify_by_thickness(t, threshold))
            for cl, t in centerlines_with_thickness]


def classify_centerlines_full(centerlines_with_thickness,
                               threshold=PLATFORM_THICKNESS_THRESHOLD):
    """批次分類並保留厚度，回傳 [(中心線, 分類字串, 厚度), ...]。"""
    return [(cl, classify_by_thickness(t, threshold), t)
            for cl, t in centerlines_with_thickness]


def classify_centerlines_from_geometry(outer, chambers,
                                       max_thickness=MAX_WALL_THICKNESS,
                                       threshold=PLATFORM_THICKNESS_THRESHOLD):
    """多邊形幾何直接回傳帶分類標籤的中心線 [(中心線, '月台'|'主結構'), ...]。"""
    return classify_centerlines(
        extract_centerlines_with_thickness(outer, chambers, max_thickness),
        threshold=threshold,
    )


def classify_centerlines_from_geometry_full(outer, chambers,
                                            max_thickness=MAX_WALL_THICKNESS,
                                            threshold=PLATFORM_THICKNESS_THRESHOLD):
    """多邊形幾何直接回傳三元組 [(中心線, 分類字串, 厚度), ...]。"""
    return classify_centerlines_full(
        extract_centerlines_with_thickness(outer, chambers, max_thickness),
        threshold=threshold,
    )
