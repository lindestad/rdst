from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import fetch_glofas_smoke as smoke


class FetchGlofasSmokeTests(unittest.TestCase):
    def test_build_request_uses_minimal_glofas_fields(self) -> None:
        request = smoke.build_request("2023", "6", "1")

        self.assertEqual(request["system_version"], ["version_4_0"])
        self.assertEqual(request["hydrological_model"], ["lisflood"])
        self.assertEqual(request["variable"], ["river_discharge_in_the_last_24_hours"])
        self.assertEqual(request["hyear"], ["2023"])
        self.assertEqual(request["hmonth"], ["06"])
        self.assertEqual(request["hday"], ["01"])
        self.assertEqual(request["data_format"], "grib2")
        self.assertEqual(request["download_format"], "unarchived")

    def test_load_dotenv_keeps_existing_environment_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "EWDS_API_URL=https://from-file.example/api\n"
                "EWDS_API_KEY=from-file\n"
                "IGNORED_WITHOUT_EQUALS\n"
                "# COMMENTED=value\n",
                encoding="utf-8",
            )

            old_url = os.environ.get("EWDS_API_URL")
            old_key = os.environ.get("EWDS_API_KEY")
            try:
                os.environ["EWDS_API_URL"] = "https://already-set.example/api"
                os.environ.pop("EWDS_API_KEY", None)

                smoke.load_dotenv(path)

                self.assertEqual(os.environ["EWDS_API_URL"], "https://already-set.example/api")
                self.assertEqual(os.environ["EWDS_API_KEY"], "from-file")
            finally:
                restore_env("EWDS_API_URL", old_url)
                restore_env("EWDS_API_KEY", old_key)

    def test_resolve_output_path_keeps_absolute_targets(self) -> None:
        repo_root = Path("C:/repo")
        absolute = Path(tempfile.gettempdir()) / "glofas-smoke.grib2"

        self.assertEqual(smoke.resolve_output_path(repo_root, str(absolute)), absolute)
        self.assertEqual(
            smoke.resolve_output_path(repo_root, "horizon/nrsm/data/raw/file.grib2"),
            repo_root / "horizon/nrsm/data/raw/file.grib2",
        )


def restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
