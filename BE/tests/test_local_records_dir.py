from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import resolve_local_records_dir


class TestLocalRecordsDirAutoCreate(unittest.TestCase):
    def test_creates_default_folder_when_env_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "FE_AutoTC"
            project_root.mkdir()
            resolved = Path(resolve_local_records_dir("", project_root))
            self.assertEqual(resolved, (project_root / "AutoTC_Records").resolve())
            self.assertTrue(resolved.is_dir())

    def test_creates_custom_relative_folder_on_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "FE_AutoTC"
            project_root.mkdir()
            resolved = Path(resolve_local_records_dir("./MyRecords/Output", project_root))
            self.assertEqual(resolved, (project_root / "MyRecords" / "Output").resolve())
            self.assertTrue(resolved.is_dir())

    def test_falls_back_and_creates_default_when_configured_path_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "FE_AutoTC"
            project_root.mkdir()
            real_mkdir = Path.mkdir

            def flaky_mkdir(self_path: Path, *args, **kwargs):
                if "UnavailableDrive" in str(self_path):
                    raise OSError("Drive not found")
                return real_mkdir(self_path, *args, **kwargs)

            with patch.object(Path, "mkdir", autospec=True, side_effect=flaky_mkdir):
                resolved = Path(resolve_local_records_dir("UnavailableDrive/AutoTC_Records", project_root))

            self.assertEqual(resolved, (project_root / "AutoTC_Records").resolve())
            self.assertTrue(resolved.is_dir())


if __name__ == "__main__":
    unittest.main()
