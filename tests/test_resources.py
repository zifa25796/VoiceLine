import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


class ResourceTests(unittest.TestCase):
    def test_data_override_keeps_bundled_intro_available(self):
        config = Path(__file__).resolve().parents[1] / "src" / "voice_line" / "config.py"
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"VOICELINE_DATA_DIR": directory}):
                settings = runpy.run_path(str(config))
            self.assertEqual(Path(settings["DB_PATH"]), Path(directory) / "voice_line.db")
            intro = Path(settings["INTRO_PATH"])
            self.assertTrue(intro.is_file())
            self.assertEqual(intro.parent.name, "assets")
            self.assertNotIn(Path(directory), intro.parents)
