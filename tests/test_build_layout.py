"""Read-only build path tests plus a synthetic source-artifact overwrite guard."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "scripts/lib/common.sh"


@unittest.skipUnless(shutil.which("bash") and shutil.which("realpath"), "Linux shell tools required")
class BuildLayoutTests(unittest.TestCase):
    def run_common(self, destination=None):
        environment = dict(os.environ)
        environment.pop("DEVKIT2023_ARTIFACT_ROOT", None)
        if destination is not None:
            environment["DEVKIT2023_ARTIFACT_ROOT"] = str(destination)
        return subprocess.run(
            ["bash", "-c", 'source "$1"; printf "%s\\n" "$ARTIFACT_ROOT"', "test", str(COMMON)],
            env=environment, text=True, capture_output=True,
        )

    def test_default_outside_source(self):
        result = self.run_common()
        self.assertEqual(result.returncode, 0, result.stderr)
        path = Path(result.stdout.strip())
        self.assertEqual(path.parent, Path('/var/tmp'))
        self.assertTrue(path.name.startswith('DevKit2023CustomLinux-artifacts-'))
        self.assertFalse(path.is_relative_to(ROOT))

    def test_explicit_external_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new-artifacts"
            result = self.run_common(destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()), destination.resolve())
            self.assertFalse(destination.exists())

    def test_source_directory_rejected(self):
        self.assertNotEqual(self.run_common(ROOT).returncode, 0)

    def test_source_subdirectory_rejected(self):
        self.assertNotEqual(self.run_common(ROOT / "output").returncode, 0)

    def test_relative_destination_rejected(self):
        self.assertNotEqual(self.run_common("relative-output").returncode, 0)

    def test_broad_destination_rejected(self):
        for directory in ("/", "/tmp", "/opt", "/home", str(Path.home())):
            with self.subTest(directory=directory):
                self.assertNotEqual(self.run_common(directory).returncode, 0)

    def test_symlink_into_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "alias"
            alias.symlink_to(ROOT, target_is_directory=True)
            self.assertNotEqual(self.run_common(alias / "output").returncode, 0)

    def test_existing_source_archive_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "artifacts"
            archive = destination / "source/DevKit2023CustomLinux-1.0.0-source.tar.gz"
            archive.parent.mkdir(parents=True)
            sentinel = b"synthetic prior artifact"
            archive.write_bytes(sentinel)
            result = subprocess.run(["bash", str(ROOT / "scripts/package-source.sh")],
                                    env={**os.environ, "DEVKIT2023_ARTIFACT_ROOT": str(destination)},
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Source artifact already exists", result.stderr)
            self.assertEqual(archive.read_bytes(), sentinel)


if __name__ == "__main__":
    unittest.main()
