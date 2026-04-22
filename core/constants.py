# 全域常數定義

SNAP_TOL = 1e-3       # 端點 snap 容差（公尺）
COVER_TOL = 1e-3      # 區間覆蓋容差
SNAP_DECIMALS = 3     # 對應 SNAP_TOL = 1e-3

MAX_WALL_THICKNESS = 4.0   # 牆/板厚度上限（公尺）— 避免外框上下邊配對成貫穿全結構
MAX_EXTENSION = 2.0        # 中心線延伸到鄰近垂直 CL 的最大距離

PLATFORM_THICKNESS_THRESHOLD = 0.2  # 月台厚度上限（公尺）

_LABEL_TO_LAYER = {
    "月台": "PLATFORM",
    "主結構": "MAIN_STRUCTURE",
}

_ID_H = 0.25  # 編號文字高度
