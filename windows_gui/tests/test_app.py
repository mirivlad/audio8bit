import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from windows_gui.app import convert_args, target_path, engine_python, child_python_env, GUI


class GuiTests(unittest.TestCase):
    def test_target(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "music.wav"
            source.write_bytes(b"audio")
            self.assertEqual(target_path(str(source), folder, "wav").name, "music_8bit.wav")

    def test_options(self):
        opts = dict(bits="8", rate="22050", transpose="-2", duty="0.25",
                    voices="nes", method="transcribe", format="wav",
                    source="auto", cache=True, **{"key-snap":True, "arrange":True, "echo":True, "dither":True})
        cmd = convert_args(r"C:\Music\fun & song.mp3", Path(r"C:\Music\result.wav"), opts)
        self.assertIn(r"C:\Music\fun & song.mp3", cmd)
        self.assertEqual(cmd[cmd.index("-V")+1], "nes")
        self.assertIn("--key-snap", cmd)
        opts["method"] = "pitch"
        with self.assertRaisesRegex(ValueError, "Транскрипция"):
            convert_args("a.mp3", Path("b.wav"), opts)

    def test_diagnostic_method_available(self):
        self.assertTrue(callable(GUI._diagnose_worker))
        self.assertTrue(callable(GUI._repair_worker))
        self.assertTrue(callable(GUI._convert_with_preflight))

    def test_utf8_child_output_even_when_parent_uses_cp1251(self):
        # Simulates the failure seen on a Russian Windows installation.
        # A Japanese output filename must not crash Python's print().
        env = child_python_env({"PATH": "example", "PYTHONIOENCODING": "cp1251"})
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8:backslashreplace")
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")
        self.assertEqual(env["PATH"], "example")
        actual = subprocess.run(
            [sys.executable, "-c", "print('Wrote C:/chiptune/博麗神社うた祭_8bit.mp3')"],
            env=child_python_env({"PYTHONIOENCODING": "cp1251"}),
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        self.assertIn("博麗神社うた祭_8bit.mp3", actual.stdout)

    def test_validation(self):
        opts = dict(bits="0", rate="22050", transpose="0", duty="0.25",
                    voices="lead", method="pitch", format="wav", source="auto")
        with self.assertRaises(ValueError):
            convert_args("a.mp3", Path("b.wav"), opts)


if __name__ == "__main__":
    unittest.main()
