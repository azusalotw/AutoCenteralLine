# 前處理：端點 snap、過濾零長度

from .constants import SNAP_DECIMALS


def snap_lines(lines, decimals=SNAP_DECIMALS):
    out = []
    for p1, p2 in lines:
        sp1 = (round(p1[0], decimals), round(p1[1], decimals))
        sp2 = (round(p2[0], decimals), round(p2[1], decimals))
        if sp1 != sp2:
            out.append((sp1, sp2))
    return out
