# FFmpeg 工具

Windows 建置前，將 **FFmpeg 7.1 或更新的 64 位元 static build** 的 `ffmpeg.exe`、`ffprobe.exe` 放在此目錄。
Static build 不需要另外搬運 FFmpeg 的 DLL。請選擇含 `libx264`、`libmp3lame`、`afir`、`acompressor`、`alimiter` 的完整版本。

來源：[FFmpeg 官方下載頁](https://ffmpeg.org/download.html#build-windows)。本專案不自動下載執行檔。
保留下載版本、檔案 SHA256、該版本的授權文件及對應原始碼來源；授權資料可放在 `tools/licenses/`，建置時會複製到成品。
請在 `tools/licenses/BUILD.txt` 記錄供應者、版本、下載位置與來源，供正式分發前核對。

開發時也可用系統 PATH 裡的 ffmpeg / ffprobe；打包腳本則要求兩個 EXE 都在此目錄。
