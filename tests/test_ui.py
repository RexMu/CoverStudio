import os
import copy
import numpy as np
from scipy.io import wavfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from saxstudio.app import MainWindow
from saxstudio.model import Clip, Project
from saxstudio.qt import QT6, QtCore, QtWidgets
from saxstudio.media import binary, run


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.temp = tempfile.TemporaryDirectory(prefix="sax-ui-tests-")
        cls.root = Path(cls.temp.name)
        cls.original_settings_format = QtCore.QSettings.defaultFormat()
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
        QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, str(cls.root/"settings"))
        for name, seconds in [("短片", 2), ("長片", 4)]:
            path = cls.root/f"{name}.mp4"
            run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i",
                 f"testsrc2=size=160x90:rate=30:duration={seconds}", "-f", "lavfi", "-i",
                 f"sine=frequency=440:duration={seconds}", "-c:v", "libx264", "-threads", "2",
                 "-c:a", "aac", "-shortest", str(path)])
        # 1 s silence, 1 s tone, 2 s silence: audible backing range is 1.0-2.0 s.
        rate = 48000
        tone = np.zeros(rate*4, np.float32)
        tone[rate:2*rate] = .3*np.sin(2*np.pi*660*np.arange(rate)/rate)
        cls.padded_backing = cls.root/"前後靜音伴奏.wav"
        wavfile.write(cls.padded_backing, rate, tone)
        cls.backing = cls.root/"伴奏.wav"
        run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=4",
             str(cls.backing)])

    @classmethod
    def tearDownClass(cls):
        QtCore.QSettings.setDefaultFormat(cls.original_settings_format)
        cls.temp.cleanup()

    def setUp(self):
        # Device/codec playback is a Win11 integration check. These tests cover
        # actual widgets, worker handoff, settings, rendering and project editing.
        self.source_patch = patch("saxstudio.app.source")
        self.source_patch.start()
        # Sound-card I/O is covered by tests/test_recorder.py with a simulated
        # device; UI tests must never open the real microphone.
        self.audio_patch = patch("saxstudio.recorder.audio_available", return_value=False)
        self.audio_patch.start()
        settings = QtCore.QSettings("SaxStudio", "SaxStudio")
        settings.remove("ui/theme")
        from saxstudio import theme
        theme.set_theme(theme.DARK)
        self.window = MainWindow()
        self.errors = []
        self.window.show_error = self.errors.append
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        if self.window.job:
            self.window.job.cancel.set()
            self.wait_job()
        self.window.dirty = False
        self.window.close()
        self.source_patch.stop()
        self.audio_patch.stop()
        self.app.processEvents()

    def wait_job(self):
        deadline = time.monotonic()+30
        while self.window.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.app.processEvents()
        self.assertFalse(self.window.busy, "background operation did not finish")
        self.assertEqual(self.errors, [])

    def import_video(self, name="長片"):
        path = str(self.root/f"{name}.mp4")
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(path, "")):
            self.window.import_video()
        self.wait_job()

    def test_import_settings_preview_edit_save_reload(self):
        self.import_video()
        w = self.window
        self.assertEqual(w.mark_end.value(), 4)
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(self.backing), "")):
            w.import_backing()
        self.wait_job()
        w.offset.setValue(325.5)
        w.volume_fields[1][0].setValue(-9)
        w.bands[1][1].setValue(-3)
        w.prepare_preview(False)
        self.assertFalse(w.limiter.isEnabled())
        self.wait_job()
        self.assertFalse(w.preview_dirty)
        self.assertTrue(Path(w.preview_path).is_file())
        w.seek(1)
        w.split()
        w.seek(3)
        w.split()
        w.clip_list.setCurrentRow(1)
        w.delete_clip()
        self.assertEqual(w.project.clips, [Clip(0, 1), Clip(3, 4)])
        w.undo()
        self.assertEqual(len(w.project.clips), 3)
        w.mark_start.setValue(.5)
        w.mark_end.setValue(3.5)
        w.trim()
        self.assertAlmostEqual(w.project.output_duration, 3)
        path = self.root/"演奏混音.saxproj"
        with patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(str(path), "")):
            w.save_project()
        self.assertFalse(w.dirty)
        saved = Project.load(path)
        self.assertEqual(saved.offset, .3255)
        self.assertEqual(saved.effects.bands[1].gain, -3)
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
            w.open_project()
        self.wait_job()
        self.assertEqual(w.project.clips, saved.clips)
        self.assertEqual(w.offset.value(), 325.5)
        self.assertFalse(w.dirty)

    def test_reimport_longer_video_updates_trim_endpoint(self):
        self.import_video("短片")
        self.assertEqual(self.window.mark_end.value(), 2)
        self.window.dirty = False
        self.import_video("長片")
        self.assertEqual(self.window.mark_end.value(), 4)

    def test_invalid_trim_does_not_destroy_clips(self):
        self.import_video()
        w = self.window
        w.mark_start.setValue(3)
        w.mark_end.setValue(1)
        w.trim()
        self.assertTrue(self.errors)
        self.assertEqual(w.project.clips, [Clip(0, 4)])
        self.assertEqual(w.project.output_duration, 4)

    def test_edit_dialog_shows_tools_cancel_restores_done_keeps(self):
        self.import_video()
        w = self.window
        self.assertIn("未剪輯", w.edits_summary.text())
        self.assertTrue(w.edit_button.isEnabled())
        self.assertIs(w.mark_start, w.edit_dialog.mark_start)
        self.assertIs(w.clip_list, w.edit_dialog.clip_list)
        w.open_edit_dialog()
        self.app.processEvents()
        self.assertTrue(w.edit_dialog.isVisible())
        self.assertIs(w.edit_dialog.video_stack.currentWidget(), w.edit_dialog.video_widget)
        # The edit window's waveform shows the same material as the main one.
        self.assertIs(w.edit_timeline.video_wave, w.timeline.video_wave)
        w.seek(2)
        self.assertEqual(w.edit_timeline.position, 2)
        self.assertIn("00:02.000", w.edit_dialog.time_label.text())
        w.split()
        self.assertEqual(len(w.project.clips), 2)
        w.edit_dialog.reject()
        self.app.processEvents()
        self.assertFalse(w.edit_dialog.isVisible())
        self.assertEqual(w.project.clips, [Clip(0, 4)])
        self.assertIn("未剪輯", w.edits_summary.text())
        w.open_edit_dialog()
        w.seek(1)
        w.split()
        w.edit_dialog.zoom.setValue(4)
        self.assertIn("4", w.edit_dialog.zoom_label.text())
        w.edit_dialog.accept()
        self.app.processEvents()
        self.assertEqual(len(w.project.clips), 2)
        self.assertIn("2 段", w.edits_summary.text())
        w.step_frame(1)
        self.assertAlmostEqual(w.position, 1 + 1/30, places=6)

    def test_theme_toggle_recolours_and_is_remembered(self):
        from saxstudio import theme
        from saxstudio.app import style_sheet
        w = self.window
        self.assertFalse(theme.is_light())
        self.assertIn("米黃", w.theme_button.text())
        w.toggle_theme()
        self.assertTrue(theme.is_light())
        self.assertEqual(QtCore.QSettings("SaxStudio", "SaxStudio").value("ui/theme"), "light")
        self.assertIn("#f5eedc", style_sheet())
        self.assertNotIn("#101923", style_sheet())
        self.assertEqual(theme.c("#101b27"), "#fbf5e6")
        self.assertIn("暗色", w.theme_button.text())
        # A new window starts in the remembered theme.
        other = MainWindow()
        self.assertTrue(theme.is_light())
        other.dirty = False
        other.close()
        w.toggle_theme()
        self.assertFalse(theme.is_light())
        self.assertIn("#101923", style_sheet())

    def test_help_dialog_shows_introduction_and_features(self):
        from saxstudio.help_dialog import HelpDialog
        dialog = HelpDialog(self.window)
        text = dialog.browser.toPlainText()
        self.assertIn("專為薩克斯風愛好者打造", text)
        self.assertIn("分軌錄音，讓每個聲音都能獨立調整", text)
        self.assertIn("功能一覽", text)
        self.assertIn("時間剪輯", text)
        dialog.close()

    def test_preset_keeps_master_limiter(self):
        self.import_video()
        w = self.window
        w.limiter.setChecked(False)
        w.preset.setCurrentIndex(2)
        self.assertFalse(w.project.effects.limiter_enabled)
        self.assertFalse(w.limiter.isChecked())
        self.assertEqual(w.project.effects.bands[0].gain, 1)

    def test_eq_spinbox_steps_up_and_down(self):
        self.import_video()
        self.window.eq_toggle.setChecked(True)
        field = self.window.bands[1][1]
        field.stepUp()
        self.assertEqual(self.window.project.effects.bands[1].gain, .5)
        field.stepDown()
        field.stepDown()
        self.assertEqual(self.window.project.effects.bands[1].gain, -.5)

    def test_effect_folding_never_changes_audio_and_switch_keeps_parameters(self):
        self.import_video()
        w = self.window
        for key, parameter, value in [("compressor_enabled", "threshold", -25),
                                      ("reverb_enabled", "decay", 2.4)]:
            panel = w.effect_sections[key]
            self.assertFalse(panel.toggle.isChecked())
            self.assertTrue(panel.body.isHidden())
            before = copy.deepcopy(w.project)
            dirty, preview_dirty = w.dirty, w.preview_dirty
            panel.arrow.click()
            self.assertFalse(panel.body.isHidden())
            self.assertFalse(panel.body.isEnabled())
            self.assertEqual(w.project, before)
            self.assertEqual((w.dirty, w.preview_dirty), (dirty, preview_dirty))
            panel.toggle.click()
            self.assertTrue(getattr(w.project.effects, key))
            self.assertTrue(panel.body.isEnabled())
            w.fx_fields[parameter].setValue(value)
            panel.arrow.click()
            self.assertTrue(panel.body.isHidden())
            self.assertTrue(getattr(w.project.effects, key))
            self.assertEqual(getattr(w.project.effects, parameter), value)
            panel.toggle.click()
            self.assertFalse(getattr(w.project.effects, key))
            self.assertEqual(getattr(w.project.effects, parameter), value)
            panel.arrow.click()
            self.assertFalse(panel.body.isEnabled())

    def test_new_import_defaults_off_and_original_presets_keep_their_behavior(self):
        self.import_video()
        w = self.window
        self.assertFalse(w.project.effects.eq_enabled)
        self.assertFalse(w.project.effects.compressor_enabled)
        self.assertFalse(w.project.effects.reverb_enabled)
        w.preset.setCurrentIndex(2)
        self.assertTrue(w.project.effects.eq_enabled)
        self.assertTrue(w.project.effects.compressor_enabled)
        self.assertTrue(w.project.effects.reverb_enabled)
        for panel in w.effect_sections.values():
            self.assertTrue(panel.toggle.isChecked())
            self.assertTrue(panel.body.isHidden())
        w.preset.setCurrentIndex(1)
        self.assertFalse(w.project.effects.compressor_enabled)
        self.assertFalse(w.project.effects.reverb_enabled)

    def test_open_existing_project_restores_enabled_effects_and_values(self):
        self.import_video()
        project = copy.deepcopy(self.window.project)
        project.effects.eq_enabled = True
        project.effects.compressor_enabled = True
        project.effects.reverb_enabled = True
        project.effects.threshold = -27
        project.effects.mix = .32
        path = self.root/"舊版專案.saxproj"
        project.save(path)
        self.window.dirty = False
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
            self.window.open_project()
        self.wait_job()
        self.assertEqual(self.window.project.effects, project.effects)
        for key, panel in self.window.effect_sections.items():
            self.assertTrue(panel.toggle.isChecked())
            self.assertTrue(panel.body.isHidden())

    def test_branding_icon_and_splash_work_in_a_packaged_resource_directory(self):
        from saxstudio.branding import StartupSplash, application_icon, asset_path
        import sys
        import shutil
        bundle = self.root/"fake-bundle"
        (bundle/"assets").mkdir(parents=True, exist_ok=True)
        for name in ("app-icon.ico", "splash-art.png"):
            shutil.copy2(asset_path(name), bundle/"assets"/name)
        with patch.object(sys, "_MEIPASS", str(bundle), create=True):
            self.assertEqual(asset_path("app-icon.ico"), bundle/"assets"/"app-icon.ico")
            icon = application_icon()
            self.assertFalse(icon.isNull())
            self.assertEqual({s.width() for s in icon.availableSizes()}, {16, 20, 24, 32, 40, 48, 64, 96, 128, 256})
            splash = StartupSplash(icon)
            splash.show()
            self.app.processEvents()
            self.assertFalse(splash.grab().isNull())
            self.assertEqual(splash.windowTitle(), "Sax Cover Studio")
            splash.close()
        self.assertTrue(self.window.windowTitle().startswith("Sax Cover Studio"))
        self.assertFalse(self.window.windowIcon().isNull())

    def test_startup_splash_hands_off_to_main_window(self):
        import subprocess
        import sys
        code = '''
from unittest.mock import patch
from tempfile import TemporaryDirectory
from saxstudio import app as program
from saxstudio import media
from saxstudio.branding import StartupSplash
from saxstudio.qt import QtWidgets, QtCore
observed = {'shown': False, 'finished': False}
show_impl, finish_impl = StartupSplash.show, StartupSplash.finish
def shown(splash):
    show_impl(splash)
    observed['shown'] = splash.isVisible()
def finished(splash, window):
    finish_impl(splash, window)
    observed['finished'] = not splash.isVisible() and window.isVisible()
original = QtWidgets.QApplication
class TestApplication(original):
    def __init__(self, args):
        super().__init__(args)
        self.poll = QtCore.QTimer(self)
        self.poll.timeout.connect(self.check_handoff)
        self.poll.start(100)
    def check_handoff(self):
        if observed['finished']:
            ok = observed['shown'] and self.applicationName() == 'Sax Cover Studio'
            print('startup lifecycle OK' if ok else 'startup lifecycle FAILED', flush=True)
            self.exit(0 if ok else 1)
with TemporaryDirectory() as config:
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    QtCore.QSettings.setPath(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope, config)
    with patch.object(QtWidgets, 'QApplication', TestApplication), patch.object(media, 'check_ffmpeg', return_value=[]), patch.object(StartupSplash, 'show', shown), patch.object(StartupSplash, 'finish', finished):
        program.main()
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn("startup lifecycle OK", result.stdout)

    def import_backing(self, path=None):
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(path or self.backing), "")):
            self.window.import_backing()
        self.wait_job()

    def test_auto_trim_keeps_backing_span_plus_margins_and_undoes(self):
        self.import_video()
        w = self.window
        self.assertFalse(w.autotrim_button.isEnabled())
        self.import_backing(self.padded_backing)
        self.assertTrue(w.autotrim_button.isEnabled())
        start, end = w.backing_range
        self.assertAlmostEqual(start, 1.0, delta=.02)
        self.assertAlmostEqual(end, 2.0, delta=.02)
        w.offset.setValue(500)
        w.pre_roll.setValue(1)
        w.post_roll.setValue(.5)
        w.auto_trim()
        self.assertEqual(len(w.project.clips), 1)
        self.assertAlmostEqual(w.project.clips[0].start, .5, delta=.03)
        self.assertAlmostEqual(w.project.clips[0].end, 3.0, delta=.03)
        w.undo()
        self.assertEqual(w.project.clips, [Clip(0, 4)])
        # Low-confidence alignment asks first; declining leaves clips alone.
        w.alignment_reliable = False
        with patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.No):
            w.auto_trim()
        self.assertEqual(w.project.clips, [Clip(0, 4)])
        # Margins are clamped to the video.
        w.alignment_reliable = None
        w.pre_roll.setValue(3)
        w.post_roll.setValue(2)
        w.auto_trim()
        self.assertAlmostEqual(w.project.clips[0].start, 0, delta=.001)
        self.assertAlmostEqual(w.project.clips[0].end, 4, delta=.001)

    def test_preset_buttons_and_restore_previous_settings(self):
        self.import_video()
        w = self.window
        self.assertEqual(w.preset.currentIndex(), 0)
        self.assertFalse(w.preset_undo.isEnabled())
        w.eq_toggle.setChecked(True)
        w.bands[0][1].setValue(-4)
        w.preset.buttons[1].click()
        self.assertEqual(w.preset.currentIndex(), 2)
        self.assertTrue(w.preset.buttons[1].isChecked())
        self.assertEqual(w.project.effects.bands[0].gain, 1)
        w.preset.buttons[2].click()
        self.assertEqual(w.project.effects.bands[0].gain, -1)
        self.assertFalse(w.preset.buttons[1].isChecked())
        w.undo_preset()
        self.assertEqual(w.project.effects.bands[0].gain, -4)
        self.assertTrue(w.project.effects.eq_enabled)
        self.assertEqual(w.preset.currentIndex(), 0)
        self.assertFalse(w.preset_undo.isEnabled())
        # A manual edit lights "自訂" again.
        w.preset.buttons[0].click()
        w.bands[2][1].setValue(2)
        self.assertEqual(w.preset.currentIndex(), 0)
        self.assertFalse(any(b.isChecked() for b in w.preset.buttons))

    def test_eq_is_a_collapsible_switch_card_and_help_popups_open(self):
        self.import_video()
        w = self.window
        eq = w.effect_sections["eq_enabled"]
        self.assertIs(eq.toggle, w.eq_toggle)
        self.assertTrue(eq.body.isHidden())
        self.assertFalse(eq.body.isEnabled())
        eq.toggle.click()
        self.assertTrue(w.project.effects.eq_enabled)
        self.assertTrue(eq.body.isEnabled())
        for key, word in [("eq_enabled", "高通"), ("compressor_enabled", "門檻"), ("reverb_enabled", "預延遲")]:
            info = w.effect_sections[key].info
            self.assertIsNotNone(info)
            before = copy.deepcopy(w.project)
            info.click()
            self.app.processEvents()
            self.assertTrue(info.popup.isVisible())
            self.assertIn(word, info.popup.findChild(QtWidgets.QLabel).text())
            info.popup.close()
            self.assertEqual(w.project, before)

    def test_resizable_layout_saves_and_resets(self):
        w = self.window
        self.assertEqual(w.h_split.count(), 2)
        self.assertEqual(w.v_split.count(), 2)
        self.assertFalse(w.h_split.childrenCollapsible())
        w.resize(1440, 980)
        self.app.processEvents()
        w.save_layout()
        settings = QtCore.QSettings("SaxStudio", "SaxStudio")
        self.assertIsNotNone(settings.value("ui/h_split"))
        w.reset_layout()
        self.assertIsNone(QtCore.QSettings("SaxStudio", "SaxStudio").value("ui/h_split"))
        left, right = w.h_split.sizes()
        self.assertGreater(left, right)

    def test_version_author_and_spin_arrow_assets(self):
        from saxstudio import AUTHOR, VERSION_LABEL
        from saxstudio.app import style_sheet
        from saxstudio.branding import StartupSplash, asset_path
        self.assertEqual(VERSION_LABEL, "Beta V0.8")
        self.assertEqual(AUTHOR, "Rex Mu | RexFactory")
        self.assertIn("Beta V0.8", self.window.windowTitle())
        sheet = style_sheet()
        self.assertNotIn("@UP@", sheet)
        for name in ("spin-up.png", "spin-up-disabled.png", "spin-down.png", "spin-down-disabled.png"):
            self.assertTrue(asset_path(name).is_file())
            self.assertIn(asset_path(name).as_posix(), sheet)
        splash = StartupSplash()
        splash.set_progress(.5, "正在建立主畫面…")
        self.assertEqual(splash.message, "正在建立主畫面…")
        self.assertFalse(splash.grab().isNull())
        splash.close()

    def make_take(self, seconds=3.0):
        rate = 48000
        x = np.zeros(int(rate*seconds), np.float32)
        x[rate:rate+4800] = .3*np.sin(2*np.pi*440*np.arange(4800)/rate)
        path = self.root/"模擬錄音.wav"
        wavfile.write(path, rate, x)
        return path

    def test_record_project_mode_panel_finish_save_reopen(self):
        from saxstudio.recorder import TakeResult
        w = self.window
        self.assertIn("尚未建立", w.mode_badge.text())
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(self.padded_backing), "")):
            w.new_record_project()
        self.wait_job()
        self.assertTrue(w.project.is_record)
        self.assertIn("錄音", w.mode_badge.text())
        self.assertIs(w.right_stack.currentWidget(), w.record_scroll)
        self.assertTrue(w.align_button.isHidden())
        self.assertFalse(w.record_offset_label.isHidden())
        self.assertIn("WAV", w.export_button.text())
        self.assertEqual(w.track_names[0].text(), "第一軌 · 錄音")
        self.assertFalse(w.play_button.isEnabled())
        self.assertFalse(w.export_button.isEnabled())
        self.assertAlmostEqual(w.timeline.override_duration, 4, delta=.05)
        take = self.make_take()
        w.finish_recording(TakeResult(str(take), 3.0, 48000, 1.25, .5))
        self.wait_job()
        p = w.project
        self.assertEqual(p.recording, str(take))
        self.assertAlmostEqual(p.duration, 3, delta=.01)
        latency = (w.current_latency() or 0) / 1000
        self.assertAlmostEqual(p.offset, 1.25 + latency, places=6)
        self.assertAlmostEqual(w.offset.value(), (1.25 + latency) * 1000, places=3)
        self.assertEqual(len(p.clips), 1)
        self.assertIsNone(w.timeline.override_duration)
        self.assertEqual(w.record_panel.states.currentIndex(), 2)
        self.assertTrue(w.play_button.isEnabled())
        # Auto trim works from the measured offset: backing audible 1-2 s.
        w.pre_roll.setValue(.5)
        w.post_roll.setValue(.25)
        w.auto_trim()
        self.assertAlmostEqual(p.clips[0].start, 1.25 + latency + 1 - .5, delta=.03)
        w.prepare_preview(False)
        self.wait_job()
        self.assertTrue(Path(w.preview_path).is_file())
        captured = {}
        def save_name(*args):
            captured["filter"] = args[3]
            return ("", "")
        with patch.object(QtWidgets.QFileDialog, "getSaveFileName", side_effect=save_name):
            w.export_dialog()
        self.assertNotIn("MP4", captured["filter"])
        path = self.root/"錄音專案.saxproj"
        with patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(str(path), "")):
            w.save_project()
        self.assertFalse(w.dirty)
        with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
            w.open_project()
        self.wait_job()
        self.assertTrue(w.project.is_record)
        self.assertEqual(w.project.recording, str(take.resolve()))
        self.assertEqual(w.record_panel.states.currentIndex(), 2)
        # A new video project switches the panel back.
        w.dirty = False
        self.import_video()
        self.assertFalse(w.project.is_record)
        self.assertIs(w.right_stack.currentWidget(), w.video_section)
        self.assertFalse(w.align_button.isHidden())

    def test_new_project_dialog_routes_to_mode(self):
        from saxstudio.record_panel import NewProjectDialog
        dialog = NewProjectDialog()
        self.assertFalse(dialog.next_button.isEnabled())
        dialog.cards["record"].click()
        self.assertEqual(dialog.choice, "record")
        self.assertTrue(dialog.cards["record"].isChecked())
        self.assertFalse(dialog.cards["video"].isChecked())
        self.assertTrue(dialog.next_button.isEnabled())
        w = self.window
        with patch("saxstudio.app.NewProjectDialog") as fake:
            fake.return_value.exec.return_value = True
            fake.return_value.exec_.return_value = True
            fake.return_value.choice = "record"
            with patch.object(w, "new_record_project") as record, patch.object(w, "import_video") as video:
                w.new_project()
                record.assert_called_once()
                video.assert_not_called()

    def test_record_panel_meter_and_progress(self):
        from saxstudio.record_panel import RecordPanel, CalibrationDialog
        panel = RecordPanel()
        panel.set_level(.1)
        self.assertIn("-20.0", panel.level_text.text())
        panel.set_level(.999)
        self.assertNotIn("破音", panel.clip_label.text())  # one hot block is not clipping
        panel.mark_clipped()
        self.assertIn("破音", panel.clip_label.text())
        panel.reset_clip()
        self.assertIn("未破音", panel.clip_label.text())
        panel.set_state("countdown")
        panel.set_countdown(3)
        panel.set_progress(1.2, -1)
        self.assertEqual(panel.rec_time.text(), "3")
        panel.set_countdown(0)
        panel.set_progress(65.25, 10)
        self.assertEqual(panel.rec_time.text(), "01:05.2")
        self.assertFalse(panel.input_combo.isEnabled())
        panel.set_latency(38.5)
        self.assertIn("38.5", panel.latency_value.text())
        dialog = CalibrationDialog(None)
        dialog.show_result(38.5, .4, 8)
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.result_ms, 38.5)

    def test_short_device_names(self):
        from saxstudio.record_panel import short_device
        self.assertEqual(short_device("Microphone Array (Intel® Smart Sound Technology for Digital Microphones)"),
                         "Microphone Array")
        self.assertEqual(short_device("Speakers (Realtek(R) Audio)"), "Speakers")
        self.assertTrue(short_device("A Very Long Interface Name Without Brackets").endswith("…"))

    def test_record_panel_settings_fold_and_punch(self):
        from saxstudio.record_panel import RecordPanel
        panel = RecordPanel()
        panel.set_settings_expanded(False)
        self.assertTrue(panel.fold_body.isHidden())
        self.assertFalse(panel.latency_warn.isHidden())
        panel.set_latency(14.6)
        self.assertIn("14.6 ms", panel.summary.text())
        self.assertTrue(panel.latency_warn.isHidden())
        self.assertNotIn("\n", panel.summary.text())
        panel.set_settings_expanded(True)
        self.assertFalse(panel.fold_body.isHidden())
        panel.set_state("punch")
        self.assertTrue(panel.fold_body.isHidden())   # collapsed while recording
        self.assertFalse(panel.input_combo.isEnabled())
        panel.set_punch_progress(2.1, 70.3, -1)
        self.assertIn("預備", panel.rec_state.text())
        panel.set_punch_progress(0, 72.5, 90)
        self.assertIn("重錄中", panel.rec_state.text())
        self.assertEqual(panel.rec_time.text(), "01:12.5")
        panel.set_done(222.5, "x.wav", 2)
        self.assertFalse(panel.fold_body.isHidden())
        self.assertIn("重錄 2 次", panel.done_label.text())
        self.assertIn("2 次", panel.undo_hint.text())
        panel.set_punch_point(72.4)
        self.assertIn("01:12.4", panel.punch_button.text())
        panel.set_done(222.5, "x.wav", 0)
        self.assertTrue(panel.undo_punch_button.isHidden())



if __name__ == "__main__":
    unittest.main()
