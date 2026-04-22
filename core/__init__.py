# AutoCenteralLine 核心套件
# 透過此 __init__.py 統一匯出所有子模組的 public API，
# 維持與舊 autocenteralline 模組完全相同的使用介面。

from core.constants import (
    SNAP_TOL, COVER_TOL, SNAP_DECIMALS,
    MAX_WALL_THICKNESS, MAX_EXTENSION,
    PLATFORM_THICKNESS_THRESHOLD,
)
from core.io_dxf import read_dxf_lines, write_dxf, write_dxf_classified
from core.io_xlsx import write_analytical_xlsx
from core.geometry import (
    signed_area, point_in_polygon,
    line_intersection, point_on_segment,
)
from core.preprocessing import snap_lines
from core.polygon import (
    find_closed_polygons, classify_polygons,
)
from core.centerline import (
    extract_centerlines, extract_centerlines_with_thickness,
    extend_to_intersections,
)
from core.classify import (
    classify_by_thickness,
    classify_centerlines, classify_centerlines_full,
    classify_centerlines_from_geometry,
    classify_centerlines_from_geometry_full,
)
from core.model import (
    build_model, build_model_with_properties,
    split_at_intersections,
)
