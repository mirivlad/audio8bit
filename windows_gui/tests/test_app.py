import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from windows_gui.app import convert_args, target_path, engine_python, GUI


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

    def test_validation(self):
        opts = dict(bits="0", rate="22050", transpose="0", duty="0.25",
                    voices="lead", method="pitch", format="wav", source="auto")
        with self.assertRaises(ValueError):
            convert_args("a.mp3", Path("b.wav"), opts)


if __name__ == "__main__":
    unittest.main()
