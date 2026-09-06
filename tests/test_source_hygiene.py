"""Synthetic source/packaging tests; never read target data or physical disks."""
import io
import json
from pathlib import Path
import runpy
import tarfile
import tempfile
import unittest

CHECKER = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/check-source.py"))


class SourceHygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = {"schema": 1, "components": [{"id": "test", "title": "Test", "purpose": "Synthetic fixture",
                     "status": "test", "files": ["config/project-map.json", "docs/FILE-INDEX.md", "README.md"]}]}
        self.write("README.md", "# Test\n")
        self.refresh()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def refresh(self):
        self.write("config/project-map.json", json.dumps(self.data))
        self.write("docs/FILE-INDEX.md", CHECKER["render_index"](self.data))

    def errors(self):
        return "\n".join(CHECKER["check"](self.root))

    def test_clean_fixture(self):
        self.assertEqual(self.errors(), "")

    def test_unregistered_file(self):
        self.write("forgotten.txt", "experiment")
        self.assertIn("unregistered file", self.errors())

    def test_output_directory_rejected(self):
        self.write("output/test.txt", "generated")
        self.assertIn("unregistered directory: output", self.errors())

    def test_build_cache_not_packaged(self):
        self.write("build/generated.txt", "cache")
        self.assertEqual(self.errors(), "")
        self.assertNotIn("build/generated.txt", CHECKER["inventory"](self.root)[1])

    def test_iso_folder_is_never_source_input(self):
        self.write('ISO/local.iso', 'synthetic private image')
        self.assertEqual(self.errors(), '')
        self.assertNotIn('ISO/local.iso', CHECKER['inventory'](self.root)[1])

    def test_only_named_public_pdf_is_allowed(self):
        name = 'docs/DevKit2023CustomLinux-Guide.pdf'
        self.data['components'][0]['files'].append(name)
        self.write(name, '%PDF-synthetic')
        self.refresh()
        self.assertEqual(self.errors(), '')
        self.write('docs/upload.pdf', '%PDF-private')
        self.assertIn('payload type', self.errors())

    def test_git_excludes_iso_and_preserves_pdf_bytes(self):
        project = CHECKER['ROOT']
        ignored = (project / '.gitignore').read_text(encoding='utf-8').splitlines()
        attributes = (project / '.gitattributes').read_text(encoding='utf-8').splitlines()
        self.assertIn('/ISO/', ignored)
        self.assertIn('*.iso', ignored)
        self.assertIn('*.pdf binary', attributes)

    def test_private_mac(self):
        self.write("README.md", ":".join(["12", "34", "56", "78", "90", "ab"]))
        self.assertIn("fixed device/profile", self.errors())

    def test_private_profile(self):
        self.write("README.md", "C:" + "/" + "Users" + "/synthetic-owner/file")
        self.assertIn("fixed device/profile", self.errors())

    def test_binary(self):
        self.write("README.md", "header\0binary")
        self.assertIn("binary or fixed", self.errors())

    def test_forbidden_payload_even_if_mapped(self):
        self.data["components"][0]["files"].append("firmware.mbn")
        self.write("firmware.mbn", "synthetic")
        self.refresh()
        self.assertIn("payload type", self.errors())

    def test_missing_file(self):
        (self.root / "README.md").unlink()
        self.assertIn("missing file", self.errors())

    def test_stale_index(self):
        self.write("docs/FILE-INDEX.md", "outdated")
        self.assertIn("index is stale", self.errors())

    def test_broken_link(self):
        self.write("README.md", "[gone](gone.md)")
        self.assertIn("broken/outside", self.errors())

    def test_external_link_not_fetched(self):
        self.write("README.md", "[example](https://example.invalid/no-network)")
        self.assertEqual(self.errors(), "")

    def test_duplicate_entry(self):
        self.data["components"][0]["files"].append("README.md")
        self.refresh()
        with self.assertRaisesRegex(ValueError, "duplicate inventory"):
            CHECKER["inventory"](self.root)

    def test_traversal_entry(self):
        self.data["components"][0]["files"].append("../outside")
        self.refresh()
        with self.assertRaisesRegex(ValueError, "unsafe inventory"):
            CHECKER["inventory"](self.root)

    def test_service_missing_executable(self):
        name = "overlay/etc/systemd/system/test.service"
        self.data["components"][0]["files"].append(name)
        self.write(name, "[Service]\nExecStart=/usr/local/libexec/missing\n")
        self.refresh()
        self.assertIn("missing local service", self.errors())

    def test_source_python_syntax(self):
        self.data["components"][0]["files"].append("bad.py")
        self.write("bad.py", "def invalid(")
        self.refresh()
        self.assertIn("Python syntax", self.errors())

    def test_prepared_service_requires_local_executable(self):
        name = 'profiles/prepared/overlay/etc/systemd/system/test.service'
        self.data['components'][0]['files'].append(name)
        self.write(name, '[Service]\nExecStart=/usr/local/libexec/prepared-test\n')
        self.refresh()
        self.assertIn('missing local service', self.errors())
        helper = 'profiles/prepared/overlay/usr/local/libexec/prepared-test'
        self.data['components'][0]['files'].append(helper)
        self.write(helper, '#!/bin/sh\nexit 0\n')
        self.refresh()
        self.assertEqual(self.errors(), '')

    def test_archive_bytes_inventory_and_modes(self):
        expected = CHECKER["inventory"](self.root)[1]
        archive = self.root / "fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for name in expected:
                content = (self.root / name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(content), 0o644
                stream.addfile(member, io.BytesIO(content))
        self.assertEqual(CHECKER["inspect_archive"](self.root, archive, expected), [])
        self.write("README.md", "changed")
        self.assertIn("archive content mismatch", "\n".join(CHECKER["inspect_archive"](self.root, archive, expected)))


if __name__ == "__main__":
    unittest.main()
