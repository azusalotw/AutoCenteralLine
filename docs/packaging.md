# 打包方式

在專案根目錄執行：

```powershell
.\.venv\Scripts\pyinstaller.exe --clean --noconfirm main.spec
```

打包完成後，執行檔會輸出到：

```text
dist\main.exe
```

注意事項：

- 請使用專案內的 `.venv`，不要用系統預設 `python`。
- `main.spec` 已包含目前的打包設定，通常不需要重新產生。
- 若要重新打包，直接重跑同一行指令即可覆蓋 `dist\main.exe`。
