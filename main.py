# autocenteralline.py — 主程式入口 + 向後相容的 re-export
#
# 所有函數實作已拆分至 core/ 子套件。
# 此檔案僅負責：
#   1. re-export 所有 public API（讓 `from autocenteralline import ...` 不壞）
#   2. `if __name__ == "__main__"` 互動式執行流程

# === re-export（向後相容） ===
from core.constants import (  # noqa: F401
    SNAP_TOL, COVER_TOL, SNAP_DECIMALS,
    MAX_WALL_THICKNESS, MAX_EXTENSION,
    PLATFORM_THICKNESS_THRESHOLD,
)
from core.io_dxf import read_dxf_lines, write_dxf, write_dxf_classified  # noqa: F401
from core.io_xlsx import write_analytical_xlsx  # noqa: F401
from core.geometry import (  # noqa: F401
    signed_area, point_in_polygon,
    line_intersection, point_on_segment,
)
from core.preprocessing import snap_lines  # noqa: F401
from core.polygon import find_closed_polygons, classify_polygons  # noqa: F401
from core.centerline import (  # noqa: F401
    extract_centerlines, extract_centerlines_with_thickness,
    extend_to_intersections,
    _pair_surfaces,
)
from core.classify import (  # noqa: F401
    classify_by_thickness,
    classify_centerlines, classify_centerlines_full,
    classify_centerlines_from_geometry,
    classify_centerlines_from_geometry_full,
)
from core.model import (  # noqa: F401
    build_model, build_model_with_properties,
    split_at_intersections,
)

# ==========================================
# 主程式 (GUI)
# ==========================================
import tkinter as tk
from tkinter import filedialog, scrolledtext
import os
import threading
import traceback

class AutoCenterlineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Central Line Generator")
        self.geometry("800x600")
        
        self.create_widgets()
        
    def create_widgets(self):
        # 頂部控制區
        frame_top = tk.Frame(self, padx=10, pady=10)
        frame_top.pack(side=tk.TOP, fill=tk.X)
        
        self.btn_select = tk.Button(
            frame_top, 
            text="選擇 DXF 檔案並執行", 
            command=self.select_file_and_run,
            font=("Arial", 12)
        )
        self.btn_select.pack(side=tk.LEFT)
        
        # 訊息輸出區
        frame_text = tk.Frame(self, padx=10, pady=10)
        frame_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(frame_text, state='disabled', font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        """將訊息輸出至 GUI 的文字區塊"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.update_idletasks()
        
    def log_clear(self):
        """清除文字區塊內容"""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def select_file_and_run(self):
        file_path = filedialog.askopenfilename(
            title="選擇 DXF 檔案",
            filetypes=[("DXF Files", "*.dxf"), ("All Files", "*.*")]
        )
        
        if not file_path:
            self.log("未選擇檔案，取消執行。")
            return
            
        self.log_clear()
        
        # 在背景執行緒處理，避免 GUI 卡頓
        threading.Thread(target=self.process_file, args=(file_path,), daemon=True).start()

    def process_file(self, file_path):
        self.btn_select.config(state=tk.DISABLED)
        try:
            self.log(f"讀取檔案: {file_path}")
            raw = read_dxf_lines(file_path)
            self.log(f"讀入 {len(raw)} 條線段")

            snapped = snap_lines(raw)
            self.log(f"snap 後 {len(snapped)} 條")

            polygons = find_closed_polygons(snapped)
            self.log(f"偵測到 {len(polygons)} 個閉合多邊形")
            for p in polygons:
                xs = [v[0] for v in p]
                ys = [v[1] for v in p]
                self.log(f"  頂點數={len(p):2d}  bbox=({min(xs):.3f}, {min(ys):.3f})–"
                         f"({max(xs):.3f}, {max(ys):.3f})  area={abs(signed_area(p)):.3f}")

            outer, chambers = classify_polygons(polygons)
            if outer is None:
                self.log("錯誤: 找不到外框")
                return
            self.log(f"外框頂點數: {len(outer)}")
            self.log(f"內室: {len(chambers)} 個")

            # 取得帶厚度與分類的中心線三元組
            triples = classify_centerlines_from_geometry_full(outer, chambers)
            self.log(f"原始中心線 {len(triples)} 條")

            # 延伸端點（保留 label/thickness：extend 不改變條數與順序）
            cls = [cl for cl, _, _ in triples]
            props = [(label, t) for _, label, t in triples]
            for _ in range(3):
                cls = extend_to_intersections(cls)
            triples_ext = [(cl, label, t) for cl, (label, t) in zip(cls, props)]
            self.log(f"延伸後 {len(triples_ext)} 條")

            nodes, elements = build_model_with_properties(triples_ext)
            self.log(f"節點 {len(nodes)} 個, 桿件 {len(elements)} 條\n")
            
            self.log(f"{'桿件ID':>6}  {'節點1':>5}  {'節點2':>5}  {'類型':>6}  {'厚度(m)':>8}")
            self.log("-" * 42)
            for eid, n1, n2, label, thickness in elements:
                self.log(f"{eid:>6}  {n1:>5}  {n2:>5}  {label:>6}  {thickness:>8.3f}")

            # 根據輸入的檔案路徑，產生輸出檔名並存入 outputs/ 資料夾
            input_filename = os.path.basename(file_path)
            base_name = os.path.splitext(input_filename)[0]
            
            out_dir = "outputs"
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
                
            out_dxf = os.path.join(out_dir, f"{base_name}_analytical.dxf")
            out_xlsx = os.path.join(out_dir, f"{base_name}_analytical.xlsx")

            write_dxf(nodes, elements, out_dxf)
            write_analytical_xlsx(nodes, elements, out_xlsx)
            self.log(f"\n完成！已輸出至 {out_dir}/:\n  - {os.path.basename(out_dxf)}\n  - {os.path.basename(out_xlsx)}")

        except Exception as e:
            self.log(f"發生錯誤:\n{traceback.format_exc()}")
        finally:
            self.btn_select.config(state=tk.NORMAL)

if __name__ == "__main__":
    app = AutoCenterlineApp()
    app.mainloop()
