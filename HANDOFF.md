# 交接說明（給新對話的 Claude）

> 這份檔案只用於交接。新對話讀完並確認接手後，請**刪除本檔並 commit／push**（使用者已同意）。

## 1. 專案概要

- **Sax Cover Studio**：薩克斯風 Cover 錄製與混音桌面工具。Python 3.12 + PySide6（Qt6）+ NumPy/SciPy，所有影音處理用 FFmpeg 在本機完成。
- 作者標示：`Rex Mu | RexFactory`。介面與說明全部**繁體中文**。
- 版本：Beta V0.2 起每次 +0.1，V0.9 之後是 V0.10…直到正式版。**目前 Beta V0.5**（`saxstudio/__init__.py` 的 `__version__`）。
- GitHub：`RexMu/CoverStudio`，分支 `main`。
- 平台：Windows 11（主要）＋ macOS Apple Silicon（只做 M 系列）。

## 2. 與使用者合作的方式

- 用繁體中文回答。使用者常說「先不要實作 先討論」「先與我確認」：**有這類字眼時只分析與提案，不要改程式**。
- 大改 UI 前，先做 UI 預覽圖（HTML 模擬畫面截圖）給使用者確認。
- 使用者會自己調 UI；他給的版本就是新的基準。
- 每次交付：bump 版本（`__init__.py`、`installer/SaxCoverStudio.iss` 的 AppVersion／VersionInfoVersion、`scripts/build-windows.ps1` 的安裝檔名、`tests/test_ui.py` 的版本斷言、README），commit 後 push 到 GitHub，必要時也打包 source zip 給使用者。
- 使用者在 Windows 跑 `build-windows.cmd`（會先跑全部測試），在 M4 MacBook Air 跑 `build-mac.command`。測試失敗時他會截圖傳來。

## 3. 開發環境限制（雲端容器）

- **容器裡沒有 Qt**（PyPI 被擋，pip 裝不到 PySide6），`tests/test_ui.py` 無法在這裡執行。
  - 替代做法：用「寬鬆的假 Qt 模組」執行 `MainWindow()` 建構，抓屬性順序錯誤等問題（上一個對話抓到 clip_list 的錯誤就是這樣）。做法：建立假的 `PyQt5` 套件，任何屬性都回傳 Stub；但 saxstudio 類別上、名稱屬於程式中 `self.X =` 的屬性若尚未設定就丟 AttributeError。這只能抓部分問題。
- 容器的 FFmpeg 是 6.1，`test_core` 中兩個混響測試會失敗（需要 FFmpeg ≥ 7.1），屬已知狀況；其餘 core／recorder 測試應全過。
- 無法在這裡測 Mac 打包、錄音裝置、麥克風權限。

## 4. 程式結構（saxstudio/）

| 檔案 | 內容 |
|---|---|
| `app.py` | MainWindow：工具列（模式徽章、新專案、匯入伴奏、開啟、儲存、重設版面、功能說明、關於）、兩軌控制、時間軸、EQ/壓縮/混響面板、錄音模式流程、主題切換、macOS 麥克風權限（`microphone_allowed`） |
| `engine.py` | FFmpeg filter graph：`render_mix`（預覽）與 `export`；alimiter −1 dBFS；MP3 libmp3lame 320k、WAV pcm_s24le、MP4 libx264 |
| `media.py` | `binary()` 找 tools/ffmpeg(.exe)（PyInstaller 時用 `sys._MEIPASS`）、probe、解碼、波形、`check_ffmpeg`（最低 7.1） |
| `model.py` | Project（mode: 影片／錄音、clips、effects、offset）、存檔 `.saxproj` |
| `alignment.py` | 前奏比對算伴奏位移 |
| `recorder.py` / `record_panel.py` | 錄音（QAudioSource/QAudioSink、邊錄邊寫 WAV、延遲校正 click track + matched filter）、錄音面板、NewProjectDialog、CalibrationDialog |
| `edit_dialog.py` | 「✂ 時間剪輯…」浮動視窗（影片預覽、可縮放雙軌波形 MirrorTimeline、起訖／分割／刪除、自動裁剪）；完成保留、取消還原 |
| `help_dialog.py` / `help_text.py` | 「功能說明」視窗；`ABOUT_HTML` 是使用者提供的介紹文字，**需逐字保留**；EQ/COMP/REVB 說明、快速音色 PRESETS |
| `theme.py` | 暗色／米黃亮色：所有顏色以暗色 hex 撰寫，`c()`／`css()` 依 `LIGHT_MAP` 轉換；`apply()` 會在切換時重套樣式 |
| `effect_panels.py` | ToggleSwitch、InfoButton、PresetBar、CollapsibleEffect |
| `widgets.py` | EQGraph、Timeline、MirrorTimeline、Worker |
| `branding.py` / `launcher.py` | 啟動畫面（720×405，與 PyInstaller boot splash 無縫銜接）、分段載入進度 |
| `qt.py` | PySide6 為主，PyQt5 後備 |

其他：`scripts/build-windows.ps1`（PyInstaller onedir + splash + DPI manifest → Inno Setup，輸出 `dist\installer\SaxCoverStudio-Setup-BetaV0.5.exe`）、`scripts/build-mac.sh` + `scripts/SaxCoverStudio-mac.spec` + `scripts/fetch-ffmpeg-mac.sh` + 根目錄 `build-mac.command`、`tools/ffmpeg-macos-arm64.env`（FFmpeg 9.0.2，Martin Riedl arm64 版，SHA256 + lock 檔驗證）。

設計重點：效果（EQ/壓縮/混響）只作用在第一軌；伴奏只有音量與位移。錄音模式在建立專案時決定，主畫面不能切換。重錄只換錄音，保留其他設定。錄音模式只匯出 WAV/MP3。

## 5. 目前狀態與待辦

**最新 commit**：`bda6a6a Mac scripts: brace variables for macOS bash 3.2…`

已修正、等待使用者回報結果：
1. **Windows**：上次打包剩 1 個測試失敗（切換主題時 `QListView.update()` 參數錯誤），已改用 `W.QWidget.update(widget)`。使用者尚未回報修正後打包是否成功。
2. **Mac**：macOS 內建 bash 3.2 會把 `$VAR` 後面緊接的中文當成變數名稱，導致 FFmpeg 沒下載，測試找不到 ffmpeg。已把 Mac 腳本中所有變數改成 `${VAR}`，下載失敗會立刻停止，測試前也會確認 ffmpeg/ffprobe 可執行。請使用者只替換 `scripts` 資料夾（保留已裝好的 `.venv-mac`）再雙擊 `build-mac.command`。**尚未回報結果**。
   - Mac 需要 Python 3.12（使用者原本裝 3.15，PySide6 6.9 不支援），建議 python.org 的 3.12.10 安裝檔。
   - 在 Mac 要驗證：App 能開、首次錄音會詢問麥克風權限、延遲校正後錄音與伴奏對齊、右鍵「打開」繞過 Gatekeeper。

注意事項：
- V0.4 的 UI 在當時其實沒有在真正的 Qt 上跑過（現在已修好兩個錯誤）。Qt 相關修改要格外小心：PySide6 的 overload／方法遮蔽（例如 item view 的 `update(index)`）、建立順序。
- Mac 腳本一律用 `${VAR}`，避免 bash 3.2 問題。

之前討論過、尚未實作的方向（使用者曾詢問可行性，未決定）：
- Android／iOS App 版本（僅討論）。
- 音色預覽品質、GPU 加速、AI 音源分離（去除原音中的現場伴奏）——僅討論，未排入。
- 錄音模式之後可能的進階功能：多次錄音（multi-take）等，第一版刻意保持簡單。

## 6. 授權

FFmpeg（含 libx264）為 GPL；散布安裝檔時需附 `tools/licenses/` 內的授權與原始碼來源說明（Mac 腳本會自動產生 `tools/licenses/BUILD.txt`）。詳見 `THIRD_PARTY.md`。
