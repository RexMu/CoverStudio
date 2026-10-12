# Sax Cover Studio 0.1.2

本版本以使用者上傳的 `SaxStudio-0.1.1-source.zip` 為基礎，使用已確認的戴耳機薩克斯風角色。

## 介面與品牌

- 主視窗、專案選擇器、錯誤視窗及安裝程式顯示名稱改為 Sax Cover Studio。
- 新增 PNG 與 10 個尺寸的 ICO，涵蓋 Win11 常見 DPI 的圖示尺寸。Qt 視窗、應用程式、EXE、安裝程式與捷徑皆接上同一圖示；程序與捷徑共用 `SaxCoverStudio.Desktop` AppUserModelID。
- 新增啟動畫面，保留約 0.9 秒的展示時間，初始化後自動關閉並交接給主視窗；FFmpeg 檢查沿用原有流程。
- Comp／Revb 改為左側滑動開關、右側展開箭頭。顯示狀態、停用時的灰色參數；開關支援滑鼠及鍵盤焦點。
- 預設收合。新專案的壓縮與混響預設關閉；其餘預設值、參數、範圍保持 0.1.1。開啟舊專案時還原儲存的狀態；自然乾聲／溫暖／明亮／柔和等原有音色預設保留效果啟用行為。
- 新增根目錄 `build-windows.cmd` 與 `build-installer.cmd`，降低找不到打包腳本的操作困難。

## 相容性

- `.saxproj` 仍使用原有 version 1 格式與欄位，未更換副檔名。
- 保留 `SaxStudio/SaxStudio` 的 QSettings 名稱，以延續 0.1.1 的時間剪輯收合偏好。
- Inno Setup 保留原 AppId，顯示名稱、EXE 名稱與新安裝預設目錄改為新品牌。
- `engine.py`、`alignment.py`、`media.py`、`qt.py`、`widgets.py` 與上傳版本逐位元一致；音訊處理、對齊、剪輯、播放同步及匯出不新增演算法。

## 打包輸出

- 可攜版：`dist\SaxCoverStudio\SaxCoverStudio.exe`（整個資料夾一起保留）。
- 安裝版：`dist\installer\SaxCoverStudio-Setup-0.1.2.exe`。

此原始碼包未附預建 Windows EXE。Windows 的安裝、實際工作列與播放裝置仍待實機驗證。
