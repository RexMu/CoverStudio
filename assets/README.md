# 品牌圖像

- `app-icon.png`：使用者確認的戴耳機薩克斯風透明圖稿。
- `app-icon.ico`：相同圖稿的多尺寸格式轉換；包含 16、20、24、32、40、48、64、96、128、256 px。
- `splash-art.png`：同角色的啟動插畫背景；名稱與載入文字由 Qt 繪製，適應視窗尺寸。

圖稿由本次對話的 image generation 工具產生。此版本沒有使用替代的擬人化調音台角色。
PyInstaller 將整個 `assets` 資料夾放入執行包；`branding.asset_path()` 同時處理原始碼與 `_MEIPASS` 的資源路徑。
