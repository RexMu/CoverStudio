import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from saxstudio.alignment import align_samples
from saxstudio.engine import LIMIT, export, impulse, render_mix
from saxstudio.media import Cancelled, active_range, binary, decode_mono, probe, run
from saxstudio.model import Clip, Project


class ProjectTests(unittest.TestCase):
    def test_edit_save_load_roundtrip(self):
        p = Project(video="演奏.mp4", duration=10, clips=[Clip(0, 10)], offset=-.325)
        p.trim(1, 9)
        self.assertTrue(p.split(4))
        del p.clips[0]
        self.assertEqual(p.output_duration, 5)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"測試.saxproj"
            p.save(path)
            loaded = Project.load(path)
            self.assertEqual(loaded.offset, -.325)
            self.assertEqual(loaded.clips, [Clip(4, 9)])
            self.assertEqual(loaded.effects.bands, p.effects.bands)

    def test_record_project_roundtrip_and_old_files_default_to_video(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"錄音專案.saxproj"
            p = Project(mode="record", recording=str(Path(d)/"take.wav"), backing=str(Path(d)/"b.mp3"),
                        duration=12, clips=[Clip(0, 12)], offset=3.0385)
            p.save(path)
            loaded = Project.load(path)
            self.assertEqual((loaded.mode, loaded.offset), ("record", 3.0385))
            self.assertTrue(loaded.is_record)
            self.assertEqual(loaded.source, str((Path(d)/"take.wav").resolve()))
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["mode"], data["recording"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(Project.load(path).mode, "video")
            data["mode"] = "camera"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                Project.load(path)

    def test_invalid_project_rejected(self):
        for p in [Project(duration=float("nan")), Project(duration=3, clips=[Clip(2, 1)]),
                  Project(duration=3, clips=[Clip(0, 2), Clip(1, 3)])]:
            with self.assertRaises(ValueError):
                p.validate()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"bad.saxproj"
            p = Project(duration=1, clips=[Clip(0, 1)])
            p.save(path)
            data = json.loads(path.read_text())
            data["version"] = 999
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                Project.load(path)
            # Missing fields or broken JSON report a readable ValueError.
            path.write_text(json.dumps({"version": 1, "video": "x.mp4"}))
            with self.assertRaises(ValueError):
                Project.load(path)
            path.write_text("{broken")
            with self.assertRaises(ValueError):
                Project.load(path)


class AutoTrimTests(unittest.TestCase):
    def test_trim_to_backing_keeps_margins_and_clamps(self):
        p = Project(duration=60, clips=[Clip(0, 10), Clip(20, 60)], offset=5)
        self.assertEqual(p.trim_to_backing(2, 40, 3, 2), (4, 47))
        self.assertEqual(p.clips, [Clip(4, 47)])
        self.assertEqual(p.trim_to_backing(0, 70, 3, 2), (2, 60))
        p.offset = -1
        self.assertEqual(p.trim_to_backing(.5, 10, 3, 2), (0, 11))
        p.offset = 100
        with self.assertRaises(ValueError):
            p.trim_to_backing(0, 10)

    def test_active_range_ignores_silence_and_inaudible_fade(self):
        rate = 8000
        t = np.arange(rate*6)/rate
        x = np.zeros_like(t)
        body = (t >= 1.5) & (t < 4)
        x[body] = .5*np.sin(2*np.pi*220*t[body])
        fade = (t >= 4) & (t < 5.5)
        # Fade-out from 0 dB down to -60 dB; audible (> -40 dB) until ~5.0 s.
        x[fade] = .5*np.sin(2*np.pi*220*t[fade])*10**(-60*(t[fade]-4)/1.5/20)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"伴奏.wav"
            wavfile.write(path, rate, x.astype(np.float32))
            start, end = active_range(path)
            self.assertAlmostEqual(start, 1.5, delta=.02)
            self.assertAlmostEqual(end, 5.0, delta=.03)
            wavfile.write(path, rate, np.zeros(rate, np.float32))
            with self.assertRaises(ValueError):
                active_range(path)


class AlignmentTests(unittest.TestCase):
    @staticmethod
    def music(rate=8000, seconds=24, seed=48):
        rng = np.random.default_rng(seed)
        x = np.zeros(rate*seconds, np.float32)
        for start in np.arange(.15, seconds-.5, .37):
            t = np.arange(int(rate*.32))/rate
            base = rng.choice([110, 147, 196, 220, 294, 330, 392, 440])
            chord = sum(np.sin(2*np.pi*base*k*t+rng.random()*6.28)/k for k in [1, 2, 3, 5])
            chord *= np.exp(-t*8)*np.minimum(t/.005, 1)*rng.uniform(.2, .8)
            begin = int(start*rate)
            x[begin:begin+len(t)] += chord
        return x

    def test_quiet_backing_microphone_coloration_positive_and_negative(self):
        rate = 8000
        backing = self.music()
        rng = np.random.default_rng(2)
        for offset in [.437, -1.253]:
            n = round(abs(offset)*rate)
            recorded = np.pad(backing, (n, 0))[:len(backing)] if offset >= 0 else np.pad(backing[n:], (0, n))
            recorded = signal.sosfilt(signal.butter(2, 2100, fs=rate, output="sos"), recorded)
            # Acoustic reflections, quiet backing, and loud instrument after the intro.
            recorded += np.pad(recorded[:-170], (170, 0))*.25
            recorded *= .04
            t = np.arange(len(recorded))/rate
            recorded += .15*np.sin(2*np.pi*523.25*t)*(t > 10)
            recorded += rng.normal(0, .001, len(recorded))
            result = align_samples(recorded, backing)
            self.assertAlmostEqual(result.offset, offset, delta=.04)
            self.assertGreater(result.confidence, .25)

    def test_unrelated_and_silent_audio(self):
        rng = np.random.default_rng(41)
        result = align_samples(rng.normal(0, .05, 8000*15), self.music(seconds=15))
        self.assertLess(result.confidence, .32)
        self.assertIn("偏低", result.message)
        with self.assertRaises(ValueError):
            align_samples(np.zeros(8000), np.ones(8000))


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sax-tests-")
        cls.root = Path(cls.temp.name)
        rate = 48000
        t = np.arange(rate*4)/rate
        raw = .12*np.sin(2*np.pi*440*t)
        wavfile.write(cls.root/"原音.wav", rate, raw.astype(np.float32))
        backing = .2*np.sin(2*np.pi*880*t)
        backing[:rate//4] = 0
        wavfile.write(cls.root/"伴奏.wav", rate, backing.astype(np.float32))
        cls.video = cls.root/"演奏 測試.mp4"
        run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4",
             "-i", str(cls.root/"原音.wav"), "-c:v", "libx264", "-threads", "2", "-c:a", "aac", "-shortest", str(cls.video)])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def project(self):
        p = Project(video=str(self.video), backing=str(self.root/"伴奏.wav"), duration=4,
                    clips=[Clip(0, 4)], video_muted=True, backing_db=0, offset=.5)
        p.effects.eq_enabled = p.effects.compressor_enabled = p.effects.reverb_enabled = False
        p.effects.limiter_enabled = False
        return p

    def test_shift_mix_and_gain(self):
        p = self.project()
        out = self.root/"mixed.wav"
        render_mix(p, out)
        rate, data = wavfile.read(out)
        self.assertEqual(rate, 48000)
        self.assertEqual(data.shape, (48000*4, 2))
        self.assertLess(np.max(abs(data[:int(rate*.74)])), .001)
        self.assertGreater(np.max(abs(data[int(rate*.8):rate])), .1)
        p.backing_db = -6
        render_mix(p, self.root/"quiet.wav")
        _, quiet = wavfile.read(self.root/"quiet.wav")
        self.assertAlmostEqual(np.max(abs(quiet))/np.max(abs(data)), 10**(-6/20), places=3)
        p.offset = -.5
        p.backing_db = 0
        render_mix(p, self.root/"early.wav")
        _, early = wavfile.read(self.root/"early.wav")
        self.assertGreater(np.max(abs(early[:rate//10])), .1)

    def test_extra_track_follows_backing_and_pans(self):
        from saxstudio.model import Track
        rate = 48000
        # Track 2: a 1 s burst at 1.0 s on its own timeline, where the backing
        # starts at 0.3 s. With the project offset 0.5 it lands at 1.2 s.
        burst = np.zeros(rate * 3, np.float32)
        burst[rate:2 * rate] = .25
        wavfile.write(self.root/"第二軌.wav", rate, burst)
        p = Project(mode="record", recording=str(self.root/"原音.wav"), backing=str(self.root/"伴奏.wav"),
                    duration=4, clips=[Clip(0, 4)], video_muted=True, backing_muted=True, offset=.5)
        p.effects.limiter_enabled = False
        p.tracks.append(Track(name="Tenor", recording=str(self.root/"第二軌.wav"), duration=3,
                              backing_offset=.3, pan=1.0))
        out = self.root/"multi.wav"
        render_mix(p, out)
        _, data = wavfile.read(out)
        self.assertLess(np.max(abs(data[:int(rate*1.15)])), .001)
        self.assertGreater(np.max(abs(data[int(rate*1.25):int(rate*2.1), 1])), .15)
        self.assertLess(np.max(abs(data[:, 0])), .001)      # panned hard right
        p.tracks[0].muted = True
        render_mix(p, out)
        _, data = wavfile.read(out)
        self.assertLess(np.max(abs(data)), .001)

    def test_nonoverlapping_backing_is_silent(self):
        p = self.project()
        for offset in [-10, 10]:
            p.offset = offset
            out = self.root/f"outside{offset}.wav"
            render_mix(p, out)
            _, data = wavfile.read(out)
            self.assertEqual(len(data), 48000*4)
            self.assertLess(np.max(abs(data)), .00001)

    def test_all_effects_and_limiter(self):
        p = self.project()
        p.video_muted = False
        p.effects.eq_enabled = p.effects.compressor_enabled = p.effects.reverb_enabled = True
        p.effects.limiter_enabled = True
        p.effects.bands[2].gain = 5
        p.video_db = p.backing_db = 12
        render_mix(p, self.root/"effects.wav")
        _, data = wavfile.read(self.root/"effects.wav")
        self.assertTrue(np.isfinite(data).all())
        self.assertGreater(np.max(abs(data)), .05)
        self.assertLessEqual(np.max(abs(data)), LIMIT + .001)

    def test_eq_attenuates_selected_frequency(self):
        p = self.project()
        p.video_muted, p.backing_muted = False, True
        render_mix(p, self.root/"dry.wav")
        p.effects.eq_enabled = True
        p.effects.bands[0].frequency, p.effects.bands[0].gain = 440, -12
        p.effects.highpass = 0
        render_mix(p, self.root/"eq.wav")
        dry = decode_mono(self.root/"dry.wav", 48000)[48000:96000]
        wet = decode_mono(self.root/"eq.wav", 48000)[48000:96000]
        self.assertAlmostEqual(np.std(wet)/np.std(dry), 10**(-12/20), delta=.03)

    def test_effects_do_not_touch_backing_track(self):
        p = self.project()
        p.video_muted, p.backing_muted = True, False
        render_mix(p, self.root/"backing-dry.wav")
        p.effects.eq_enabled = p.effects.compressor_enabled = True
        p.effects.bands[2].frequency, p.effects.bands[2].gain = 880, -12
        p.effects.threshold, p.effects.ratio = -40, 10
        render_mix(p, self.root/"backing-fx.wav")
        _, dry = wavfile.read(self.root/"backing-dry.wav")
        _, fx = wavfile.read(self.root/"backing-fx.wav")
        self.assertLess(np.max(abs(dry-fx)), 1e-6)

    def test_compression_reduces_above_threshold_signal(self):
        p = self.project()
        p.video_muted, p.backing_muted = False, True
        render_mix(p, self.root/"uncompressed.wav")
        p.effects.compressor_enabled = True
        p.effects.threshold, p.effects.ratio = -35, 5
        render_mix(p, self.root/"compressed.wav")
        dry = decode_mono(self.root/"uncompressed.wav", 48000)[48000:96000]
        compressed = decode_mono(self.root/"compressed.wav", 48000)[48000:96000]
        self.assertLess(np.std(compressed), np.std(dry)*.5)
        self.assertGreater(np.std(compressed), 0)

    def test_reverb_produces_stereo_tail_after_predelay(self):
        samples = np.zeros(48000, np.float32)
        samples[4800] = .2
        path = self.root/"click.wav"
        wavfile.write(path, 48000, samples)
        p = self.project()
        p.video = str(path)
        p.backing = ""
        p.video_muted = False
        p.duration, p.clips = 1, [Clip(0, 1)]
        p.effects.reverb_enabled = True
        p.effects.mix, p.effects.predelay = .5, 50
        render_mix(p, self.root/"reverberated.wav")
        _, data = wavfile.read(self.root/"reverberated.wav")
        # FFmpeg's mono-to-stereo equal-power rematrix is -3 dB per channel.
        self.assertAlmostEqual(float(data[4800, 0]), .1/np.sqrt(2), places=3)
        self.assertLess(np.max(abs(data[4801:7200])), .0001)
        self.assertGreater(np.max(abs(data[7200:12000])), .001)
        self.assertGreater(np.max(abs(data[:, 0]-data[:, 1])), .0001)

    def test_synchronized_middle_delete_mp4_wav_mp3(self):
        p = self.project()
        p.clips = [Clip(.5, 1.5), Clip(2.5, 3.5)]
        for ext in ("mp4", "wav", "mp3"):
            out = self.root/f"剪輯輸出.{ext}"
            export(p, out)
            info = probe(out)
            self.assertAlmostEqual(info["duration"], 2, delta=.07)
            self.assertIsNotNone(info["audio"])
            if ext == "mp4":
                self.assertEqual(info["video"]["codec_name"], "h264")
            samples = decode_mono(out, 48000)
            self.assertLess(np.std(samples[:int(.20*48000)]), .01)
            self.assertGreater(np.std(samples[int(.4*48000):int(.8*48000)]), .08)
            self.assertGreater(np.std(samples[int(1.1*48000):int(1.8*48000)]), .08)
            if ext == "mp4":
                def frame(path, time):
                    raw = run([binary("ffmpeg"), "-v", "error", "-ss", str(time), "-i", str(path),
                               "-frames:v", "1", "-vf", "scale=64:36", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
                    return np.frombuffer(raw, np.uint8).astype(float)
                for out_time, source_time in [(0, .5), (1, 2.5)]:
                    actual = frame(out, out_time)
                    expected = frame(self.video, source_time)
                    self.assertLess(np.mean(abs(actual-expected)), 5)

    def test_variable_frame_rate_video_exports_constant_rate(self):
        vfr = self.root/"可變影格率.mp4"
        run([binary("ffmpeg"), "-v", "error", "-y", "-i", str(self.video), "-vf",
             "select=if(lt(t\\,2)\\,1\\,not(mod(n\\,3)))", "-fps_mode", "vfr", "-c:v", "libx264",
             "-threads", "2", "-c:a", "copy", str(vfr)])
        self.assertNotEqual(probe(vfr)["video"]["avg_frame_rate"], "30/1")
        p = self.project()
        p.video = str(vfr)
        p.clips = [Clip(.5, 1.5), Clip(2.5, 3.5)]
        out = self.root/"固定影格率.mp4"
        export(p, out)
        info = probe(out)
        self.assertEqual(info["video"]["avg_frame_rate"], "30/1")
        self.assertAlmostEqual(info["duration"], 2, delta=.07)

    def test_export_protects_sources_and_cancellation(self):
        p = self.project()
        with self.assertRaises(ValueError):
            export(p, self.video)
        out = self.root/"existing.wav"
        out.write_bytes(b"existing output")
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            export(p, out, cancel)
        self.assertEqual(out.read_bytes(), b"existing output")

    def test_cut_stays_in_sync_when_video_starts_after_audio(self):
        # Video stream starts 0.3 s after the container/audio start; a cut that
        # begins mid-file must keep the flash and the click together.
        ff = binary("ffmpeg")
        flash = self.root/"flash.mp4"
        run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=black:s=160x90:r=30:d=4,geq=lum=if(between(T\\,1.5\\,1.533)\\,255\\,0):cb=128:cr=128",
             "-c:v", "libx264", "-threads", "2", str(flash)])
        click = np.zeros(48000*5, np.float32)
        click[int(1.8*48000):int(1.8*48000)+480] = .8
        wavfile.write(self.root/"click.wav", 48000, click)
        source = self.root/"起始偏移.mp4"
        run([ff, "-v", "error", "-y", "-itsoffset", "0.3", "-i", str(flash), "-i", str(self.root/"click.wav"),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-t", "4.3", str(source)])
        info = probe(source)
        self.assertAlmostEqual(float(info["video"]["start_time"]) - info["start"], .3, delta=.01)
        p = self.project()
        p.video, p.backing, p.duration = str(source), "", info["duration"]
        p.video_muted = False
        p.clips = [Clip(1.0, 2.5)]
        out = self.root/"同步剪輯.mp4"
        export(p, out)
        audio_time = np.argmax(np.abs(decode_mono(out, 48000)) > .2)/48000
        raw = run([ff, "-v", "error", "-i", str(out), "-vf", "scale=8:8,format=gray", "-f", "rawvideo", "pipe:1"])
        video_time = np.argmax(np.frombuffer(raw, np.uint8).reshape(-1, 64).mean(1) > 128)/30
        self.assertAlmostEqual(audio_time, .5, delta=.02)
        self.assertAlmostEqual(video_time, .5, delta=.04)

    def test_record_mode_renders_recording_and_refuses_mp4(self):
        take = self.root/"錄音.wav"
        rate = 48000
        x = np.zeros(rate*3, np.float32)
        x[rate:rate+4800] = .3*np.sin(2*np.pi*440*np.arange(4800)/rate)
        wavfile.write(take, rate, x)
        p = Project(mode="record", recording=str(take), backing=str(self.root/"伴奏.wav"), duration=3,
                    clips=[Clip(0, 3)], backing_muted=True, offset=1.5)
        p.effects.limiter_enabled = False
        self.assertEqual(p.source, str(take))
        out = self.root/"錄音混音.wav"
        render_mix(p, out)
        _, data = wavfile.read(out)
        self.assertEqual(len(data), rate*3)
        self.assertLess(np.max(abs(data[:rate-10])), .001)
        self.assertGreater(np.max(abs(data[rate:rate+4800])), .1)
        export(p, self.root/"錄音輸出.mp3")
        with self.assertRaises(ValueError):
            export(p, self.root/"錄音輸出.mp4")
        with self.assertRaises(ValueError):
            export(p, take)

    def test_room_response_predelay_and_decay(self):
        out = self.root/"ir.wav"
        impulse(out, 1.6, 20)
        rate, data = wavfile.read(out)
        self.assertEqual(data.shape[1], 2)
        self.assertEqual(np.max(abs(data[:960])), 0)
        self.assertGreater(np.std(data[960:5760]), np.std(data[-4800:])*100)


class PunchModelTest(unittest.TestCase):
    def test_segments_and_save_round_trip(self):
        from saxstudio.model import Clip, Project, Punch, PunchUndo
        p = Project(mode="record", duration=200, clips=[Clip(0, 200)])
        p.punches = [Punch(72, 1), Punch(125, 2)]
        p.punch_undo = [PunchUndo("a.wav", 200, [Clip(0, 200)]), PunchUndo("b.wav", 201)]
        self.assertEqual(p.take_segments(), [(0.0, 72, 0), (72, 125, 1), (125, 200, 2)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x.saxproj"
            p.save(path)
            q = Project.load(path)
        self.assertEqual(q.punches, p.punches)
        self.assertEqual(q.punch_undo[0].clips, [Clip(0, 200)])
        p.punches.append(Punch(50, 3))
        self.assertEqual(p.take_segments(), [(0.0, 50, 0), (50, 200, 3)])

    def test_old_project_files_have_no_punches(self):
        from saxstudio.model import Project
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.saxproj"
            Project().save(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("punches"), data.pop("punch_undo")
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(Project.load(path).punches, [])


class StorageTests(unittest.TestCase):
    def test_names_folders_and_moving_a_project(self):
        from datetime import datetime
        from saxstudio import storage
        from saxstudio.model import Clip, Project, Punch, PunchUndo
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            when = datetime(2026, 10, 31, 20, 4)
            first = storage.take_path(base, "D:/伴奏/月亮代表我的心.mp3", when=when)
            self.assertEqual(first.relative_to(base).as_posix(), "2026-10-31/月亮代表我的心-20-04.wav")
            first.write_bytes(b"1")
            self.assertEqual(storage.take_path(base, "x/月亮代表我的心.mp3", when=when).name,
                             "月亮代表我的心-20-04 (2).wav")
            raw = storage.take_path(base, "a*b?.mp3", kind="重錄", number=1, when=when)
            self.assertEqual(raw.relative_to(base).as_posix(), "2026-10-31/重錄片段/a_b_-20-04-重錄1.wav")
            raw.write_bytes(b"r")
            old = storage.take_path(base, "a.mp3", when=when)
            old.write_bytes(b"o")
            p = Project(mode="record", recording=str(first), duration=1, clips=[Clip(0, 1)],
                        punches=[Punch(.5, 1, str(raw))], punch_undo=[PunchUndo(str(old), 1)])
            target = storage.multitrack_folder(base, "月亮代表我的心.mp3", when)
            self.assertEqual(target.name, "月亮代表我的心-多軌專案")
            self.assertEqual(storage.move_project_files(p, target), [])
            self.assertEqual(Path(p.recording).parent, target)
            self.assertEqual(Path(p.punches[0].take).parent, target / storage.PUNCH_FOLDER)
            self.assertTrue(Path(p.punch_undo[0].recording).is_file())
            self.assertEqual(p.folder, str(target))
            self.assertFalse(first.exists())

    def test_platform_messages(self):
        from saxstudio.recorder import clip_help_text, mic_failed_text
        self.assertNotIn("Windows", mic_failed_text("darwin"))
        self.assertNotIn("Windows", clip_help_text("darwin"))
        self.assertIn("Windows", mic_failed_text("win32"))


if __name__ == "__main__":
    unittest.main()
