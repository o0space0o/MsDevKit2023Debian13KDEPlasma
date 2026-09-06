"""Synthetic regression tests. No Windows files or device identities needed."""
import pathlib
import os
import runpy
import subprocess
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(os.environ.get("DEVKIT2023_VALIDATOR", pathlib.Path(__file__).resolve().parents[1] / "overlay/usr/local/libexec/devkit2023customlinux-validate-windows-driver"))
VALIDATOR = runpy.run_path(str(SOURCE))
PARSE = VALIDATOR["parse_catalog_members"]
END = "Signature Index: 0  (Primary Signature)\n"
DIGEST = "a" * 64
MEMBER = f"\tFile name: test.mbn\n\tHash algorithm: SHA256\n\tMessage digest: {DIGEST}\n\n"


class CatalogParserTests(unittest.TestCase):
    def test_timestamp_after_table_is_not_a_member(self):
        output = "Catalog members:\n" + MEMBER + END + (
            "Signer's certificate:\n\tSubject: test\n\n"
            "Countersignatures:\n\tTimestamp time: test\n"
            "\tHash Algorithm: sha256\n\tIssuer: test\n\n"
            "Signature verification: ok\nSucceeded\n"
        )
        self.assertEqual(PARSE(output), {"test.mbn": [DIGEST]})

    def test_unsigned_timestamp_not_required(self):
        self.assertEqual(PARSE("Catalog members:\n" + MEMBER + END), {"test.mbn": [DIGEST]})

    def test_attributes_can_be_digest_first(self):
        member = f"\tHash algorithm: SHA256\n\tMessage digest: {DIGEST}\n\tFile name: test.mbn\n\n"
        self.assertEqual(PARSE("Catalog members:\n" + member + END), {"test.mbn": [DIGEST]})

    def test_boundary_checks_unfinished_member(self):
        with self.assertRaisesRegex(ValueError, "malformed catalog member block"):
            PARSE("Catalog members:\n\tFile name: broken.mbn\n\tHash algorithm: SHA256\n" + END)

    def test_named_digestless_records_are_not_hash_evidence(self):
        digestless = "\tFile name: 2:10.0\n\tFile name: alternate.so\n\n"
        self.assertEqual(PARSE("Catalog members:\n" + digestless + MEMBER + END), {"test.mbn": [DIGEST]})

    def test_required_digestless_record_is_not_accepted(self):
        digestless = "\tFile name: required.mbn\n\n"
        result = PARSE("Catalog members:\n" + digestless + MEMBER + END)
        member_check = VALIDATOR["require_catalog_member"]
        with patch.dict(member_check.__globals__, {"sha256_file": lambda _: DIGEST}):
            with self.assertRaises(ValueError):
                member_check(result, pathlib.Path("required.mbn"), "required.mbn")

    def test_unrelated_legacy_and_path_records_are_not_hash_evidence(self):
        sha1 = MEMBER.replace("SHA256", "SHA1").replace(DIGEST, "a" * 40).replace("test.mbn", "old.mbn")
        path = MEMBER.replace("test.mbn", "subdir/other.mbn")
        result = PARSE("Catalog members:\n" + sha1 + path + MEMBER + END)
        self.assertEqual(result, {"test.mbn": [DIGEST]})

    def test_sha1_only_required_member_not_accepted(self):
        sha1 = MEMBER.replace("SHA256", "SHA1").replace(DIGEST, "a" * 40).replace("test.mbn", "required.mbn")
        result = PARSE("Catalog members:\n" + sha1 + MEMBER + END)
        member_check = VALIDATOR["require_catalog_member"]
        with patch.dict(member_check.__globals__, {"sha256_file": lambda _: DIGEST}):
            with self.assertRaises(ValueError):
                member_check(result, pathlib.Path("required.mbn"), "required.mbn")

    def test_malformed_digest_length_rejected(self):
        with self.assertRaisesRegex(ValueError, "malformed catalog member digest"):
            PARSE("Catalog members:\n" + MEMBER.replace(DIGEST, "a" * 40) + END)

    def test_incomplete_member_before_blank_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "malformed catalog member block"):
            PARSE("Catalog members:\n\tHash algorithm: SHA256\n\n" + MEMBER + END)

    def test_missing_table_rejected(self):
        with self.assertRaises(ValueError):
            PARSE(END + MEMBER)

    def test_missing_boundary_rejected(self):
        with self.assertRaises(ValueError):
            PARSE("Catalog members:\n" + MEMBER)

    def test_duplicate_table_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PARSE("Catalog members:\n" + MEMBER + "Catalog members:\n" + END)

    def test_signature_report_cannot_add_members(self):
        spoof = MEMBER.replace("test.mbn", "extra.mbn")
        self.assertEqual(PARSE("Catalog members:\n" + MEMBER + END + spoof), {"test.mbn": [DIGEST]})

    def test_duplicate_member_remains_ambiguous(self):
        result = PARSE("Catalog members:\n" + MEMBER + MEMBER + END)
        self.assertEqual(result["test.mbn"], [DIGEST, DIGEST])
        member_check = VALIDATOR["require_catalog_member"]
        with patch.dict(member_check.__globals__, {"sha256_file": lambda _: DIGEST}):
            with self.assertRaisesRegex(ValueError, "absent or ambiguous"):
                member_check(result, pathlib.Path("test.mbn"), "test.mbn")

    def test_wrong_hash_rejected(self):
        member_check = VALIDATOR["require_catalog_member"]
        with patch.dict(member_check.__globals__, {"sha256_file": lambda _: "b" * 64}):
            with self.assertRaisesRegex(ValueError, "absent or ambiguous"):
                member_check({"test.mbn": [DIGEST]}, pathlib.Path("test.mbn"), "test.mbn")

    def test_failed_signature_never_parsed(self):
        verify = VALIDATOR["authenticate_catalog"]
        failed = subprocess.CompletedProcess([], 1, "Catalog members:\n" + MEMBER + END, "bad signature")
        with patch.object(verify.__globals__["subprocess"], "run", return_value=failed):
            with self.assertRaisesRegex(ValueError, "catalog authentication failed"):
                verify(pathlib.Path("test.cat"), pathlib.Path("public-roots.pem"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
