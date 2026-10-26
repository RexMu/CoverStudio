# Sax Cover Studio Beta V0.9

以 Beta V0.8 為基礎：錄音模式多軌（最多 3 軌）。

- 模型：`Track`（名稱、錄音、長度、`backing_offset`、音量、靜音、聲道位置、效果、重錄紀錄）放在 `Project.tracks`；第一軌欄位仍在 `Project`，以 `MainTrack`／`Project.track(i)` 統一存取。每軌依伴奏對齊，在第一軌時間軸上的位置為 `offset - backing_offset`。新增 `track1_name`、`video_pan`、`backing_pan`；舊專案檔視為單軌。
- 引擎：`render_mix` 每軌各自套 `effect_filters`（EQ／壓縮／混響）、音量、`pan_filter` 後與伴奏 `amix`，總輸出限幅器作用於全部。
- 錄音：`recorder.monitor_mix`／`add_track` 產生耳機混音；`punch_playback(..., others=)` 在重錄時持續播放其他軌。新軌錄音（`MainWindow.fresh`）在自己的列上即時畫波形。
- 介面：軌道分頁（`track_tabs`）、`＋ 新增錄音軌`、軌道列「⋯」選單、`PanDialog`、錄音面板 `set_target()`；`Timeline` 依軌數分列（`TOP/BOTTOM/GAP` 與左側控制列一致），點波形列可選軌。

---

# Sax Cover Studio Beta V0.8

以 Beta V0.7 為基礎。

- 錄音面板：折疊標題改為整列透明 `QPushButton#foldButton`（▸／▾）；摘要用 `ElidedLabel` 單行省略、`short_device()` 去掉括號內的驅動說明；延遲未校正改為標題右側 `latency_warn`；`restore_hint()` 在錄音結束／失敗後還原提示文字。
- 中途重錄：`Timeline.punch_live`（起點、時間、峰值、顏色）即時畫新錄音，`override_duration` 延伸到伴奏結束。
- 配色：`widgets.TRACK_COLORS`（各軌初始色）與 `PUNCH_COLORS`（重錄色盤，依軌錯開起點）。
- CI：手動執行可取消「打包安裝檔」，只跑測試。

---

# Sax Cover Studio Beta V0.7

以 Beta V0.6 為基礎。

- 中途重錄（punch-in）：`recorder.punch_playback` 產生預備 3 秒的耳機混音（伴奏已乘耳機音量＋目前錄音，起點處淡出），`recorder.splice_punch` 依 take 的 start_offset 與延遲把新錄音接到起點（20 ms 交叉淡化），寫成新的合成 WAV。
- `Project.punches`（起點、第幾次）與 `Project.punch_undo`（重錄前的錄音檔、長度、片段）存進 `.saxproj`；舊專案檔沒有這兩欄時視為空。整段重錄會清空。
- `Timeline` 依 `Project.take_segments()` 分色畫第一軌並畫接縫線，滑鼠停留顯示重錄次數。
- 錄音面板：設定折疊卡（`record/settings_expanded`，預設展開）、摘要、`punch` 狀態、重錄／復原按鈕。

---

# Sax Cover Studio Beta V0.6

以 Beta V0.5 為基礎。

- 預覽：播放中變更音效設定時，延遲 600 ms 合併多次變更後重新算預覽，載入後回到原位置並自動繼續播放（`resume_after_render`、`pending_position`）。手動按播放重算時也保留位置。
- 錄音：`recorder.is_clipping` 以連續 3 個 |x| ≥ 0.999 的取樣判斷破音，經 `AudioSession.clipped` 通知面板；音量表色區改為 -12／-4 dB；顯示 3 秒峰值。
- 建置：GitHub Actions 打包 Windows 安裝檔；`make-boot-splash.py` 在 Windows 強制使用 windows 平台外掛並確認微軟正黑體存在，CI 設 `SAX_REQUIRE_SPLASH` 時開機圖失敗即停止。

---

# Sax Cover Studio Beta V0.4

以 Beta V0.3 為基礎。

## 介面

- 時間剪輯從主畫面移到浮動視窗（`saxstudio/edit_dialog.py`）。主畫面對齊列最左邊為「✂ 時間剪輯…」＋剪輯摘要。視窗含影片預覽（播放器畫面輸出暫時切到視窗）、播放、前後一格、起訖與剪輯工具、依伴奏自動裁剪、片段清單、可縮放波形（`MirrorTimeline` 與主畫面共用波形資料），「取消」還原開啟前的片段與復原紀錄。
- 新增「功能說明」視窗（`saxstudio/help_dialog.py`），內容為作者撰寫的介紹文與功能一覽。
- 新增米黃亮色主題（`saxstudio/theme.py`）：以暗色色碼為準建立對照表，樣式表、內嵌樣式與自繪元件（波形、EQ 曲線、開關、音量表）共用；文字對比皆達 4.5:1 以上。主題記在 `ui/theme`。
- 移除主畫面的折疊式剪輯區與 `ui/edits_expanded` 設定。

## 測試

- 介面測試新增：剪輯視窗（工具、與主畫面同步、取消還原、完成保留、縮放、前後一格）、主題切換與記憶、功能說明內容。

---

# Sax Cover Studio Beta V0.3

以 Beta V0.2 為基礎，新增錄音模式（第一版：單次錄音，重錄即取代）。

## 新增

- `Project.mode`（`video`／`record`）與 `Project.recording`；`Project.source` 是第一軌的來源檔。舊專案沒有這兩個欄位時視為 `video`。
- `saxstudio/recorder.py`：
  - `WavWriter`：邊錄邊寫的 float32 WAV，每次 flush 更新 RIFF 大小，當機後檔案仍可讀。
  - `click_track()`／`measure_latency()`：校正用節拍與匹配濾波量測（模擬測試誤差 < 0.1 ms）。
  - `AudioSession`：Qt 6 `QAudioSource`／`QAudioSink`，輸入監看、倒數、伴奏播放、伴奏播完 2 秒後自動停止、延遲校正。位移 = 伴奏開始時的錄音時間 + 校正延遲。
- `saxstudio/record_panel.py`：錄音面板（裝置、聲道、耳機輸出、倒數、音量表、耳機伴奏音量、延遲補償、錄音／停止／完成三種狀態）、新專案對話框、延遲校正對話框。
- 工具列改為「目前模式」顯示＋「新專案」；錄音模式時右側錄音面板取代影片預覽，對齊前奏按鈕改為位移說明；播放時鐘改用混音音訊；錄音中波形即時顯示。
- `tests/test_recorder.py`：以模擬音效卡（固定往返延遲、10 ms 擷取週期）跑真正的 `AudioSession`，驗證校正、倒數、伴奏播完自動停止、錄音時間對齊、倒數中停止會刪除檔案、取消校正不報錯。
- 介面測試新增錄音模式流程（建立、完成錄音、自動裁剪、預覽、匯出格式、存檔與重開、切回影片模式）。介面測試不會開啟真實麥克風。

## 限制

- 錄音需要 Qt 6（Windows 版 PySide6）；Qt 5 相容環境只顯示「不支援錄音」。
- 實際音效卡以約 10 ms 為單位傳送聲音，對齊可能有數毫秒誤差，可用伴奏位移微調。
- 錄音時不提供從耳機監聽自己的聲音（戴耳機錄音時直接聽樂器原聲）。

---

# Sax Cover Studio Beta V0.2

以 0.1.2 為基礎。

## 新增與修改

- 版本號改為 Beta V0.2（`saxstudio/__init__.py` 的 `__version__`），作者 Rex Mu | RexFactory；顯示於標題列、主畫面、啟動畫面、「關於」視窗；安裝程式加上 AppVerName／AppPublisher，輸出 `SaxCoverStudio-Setup-BetaV0.2.exe`。
- 啟動流程改由 `saxstudio/launcher.py` 執行：先顯示開頭畫面，再分段載入 NumPy／SciPy、建立主畫面、檢查 FFmpeg，並在畫面上顯示進度。打包時用 `scripts/make-boot-splash.py` 產生同樣的開頭畫面圖，交給 PyInstaller `--splash`，雙擊 EXE 後立即顯示。啟動失敗時顯示錯誤詳情，不會卡在開頭畫面。
- 效果區／影片區／音訊條改為可拖曳的分隔線（QSplitter），記住大小；新增「重設版面」。影片預覽最小尺寸縮小為 240×135。
- EQ 改為與 Comp／Revb 相同的折疊卡片，新專案預設關閉；快速音色會開啟 EQ。
- EQ／Comp／Revb 加上 ⓘ 說明小卡（`saxstudio/help_text.py`）。
- 快速音色改為按鈕列（`PresetBar`，保留 `currentIndex`／`setCurrentIndex` 介面），新增「↶ 還原套用前設定」。
- 依伴奏自動裁剪：`media.active_range()` 偵測伴奏有聲範圍（相對最大峰值 −40 dB），`Project.trim_to_backing()` 保留前後秒數並限制在影片範圍內。
- 數字欄上下按鈕加上箭頭圖示（`assets/spin-*.png`，含 @2x）。
- `Alignment.reliable` 屬性取代原本內嵌的可信度判斷（門檻不變）。

- 開頭畫面依使用者調整的 720×405 版面重新排版（標題 46 px、副標 16 px、讀取文字 14 px、底部 12 px），保留版本與作者。
- 修正開頭畫面先出現在左上方再跳到正中央：EXE 加上 per-monitor DPI 宣告（`installer/dpi-aware.manifest`），讓開機畫面從一開始就以實際像素置中；程式內的開頭畫面固定置中於主螢幕，初始進度與開機畫面相同，交接時看起來是同一個畫面。

## 相容性

- `.saxproj` 格式不變。舊專案的 EQ 開關依專案儲存的狀態還原。
- 引擎（`engine.py`）與匯出流程未修改。

---

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
