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
        QtCore.QSettings("SaxStudio", "SaxStudio").remove("ui/edits_expanded")
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

    def test_edit_panel_collapsed_by_default_and_summarizes_cuts(self):
        self.import_video()
        w = self.window
        self.assertTrue(w.edits_body.isHidden())
        self.assertIn("未剪輯", w.edits_summary.text())
        w.seek(2)
        w.split()
        # Splitting from the shortcut opens the panel without changing the saved default.
        self.assertFalse(w.edits_body.isHidden())
        self.assertIn("2 段", w.edits_summary.text())
        self.assertFalse(QtCore.QSettings("SaxStudio", "SaxStudio").value("ui/edits_expanded", False) in (True, "true"))
        w.edits_toggle.setChecked(False)
        self.assertTrue(w.edits_body.isHidden())
        self.assertIn("已剪輯", w.edits_summary.text())

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
        self.assertFalse(w.edits_body.isHidden())
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
        self.assertEqual(VERSION_LABEL, "Beta V0.2")
        self.assertEqual(AUTHOR, "Rex Mu | RexFactory")
        self.assertIn("Beta V0.2", self.window.windowTitle())
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


if __name__ == "__main__":
    unittest.main()
