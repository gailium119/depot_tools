#!/usr/bin/env python3
# Copyright 2023 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
# The repo's root directory.
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))

# Add the repo's root directory for clearer imports.
sys.path.insert(0, _ROOT_DIR)

import gclient_utils
import metadata.parse
import metadata.fields.known
import metadata.fields.custom.mitigated

class ParseTest(unittest.TestCase):
    def test_parse_single(self):
        """Check parsing works for a single dependency's metadata."""
        filepath = os.path.join(_THIS_DIR, "data",
                                "README.chromium.test.single-valid")
        content = gclient_utils.FileRead(filepath)
        all_metadata = metadata.parse.parse_content(content)

        self.assertEqual(len(all_metadata), 1)
        self.assertListEqual(
            all_metadata[0].get_entries(),
            [
                ("Name", "Test-A README for Chromium metadata"),
                ("Short Name", "metadata-test-valid"),
                ("URL", "https://www.example.com/metadata,\n"
                 "     https://www.example.com/parser"),
                ("Unknown Field",
                 "Should be extracted into a field, because the preceding URL\n"
                 "               field is structured, thus terminated by another field-like\n"
                 "               line, even if the field name isn't well known to us."
                 ),
                ("Version", "1.0.12"),
                ("Date", "2020-12-03"),
                ("License", "Apache, 2.0 and MIT"),
                ("License File", "LICENSE"),
                ("Security Critical", "yes"),
                ("Shipped", "yes"),
                ("CPEPrefix", "unknown"),
                ("Description", "A test metadata file, with a\n"
                 " multi-line description."),
                ("Local Modifications", "None."),
            ],
        )

        # Check line numbers are recorded correctly.
        self.assertEqual((1, 23),
                         all_metadata[0].get_first_and_last_line_number())

    def test_parse_multiple(self):
        """Check parsing works for multiple dependencies' metadata."""
        filepath = os.path.join(_THIS_DIR, "data",
                                "README.chromium.test.multi-invalid")
        content = gclient_utils.FileRead(filepath)
        all_metadata = metadata.parse.parse_content(content)

        # Dependency metadata with no entries at all are ignored.
        self.assertEqual(len(all_metadata), 3)

        # Check entries are added according to fields being one-liners.
        self.assertListEqual(
            all_metadata[0].get_entries(),
            [
                ("Name",
                 "Test-A README for Chromium metadata (0 errors, 0 warnings)"),
                ("Short Name", "metadata-test-valid"),
                ("URL", "https://www.example.com/metadata,\n"
                 "     https://www.example.com/parser"),
                ("Version", "1.0.12"),
                ("Date", "2020-12-03"),
                ('License', 'Apache-2.0, MIT'),
                ("License File", "LICENSE"),
                ("Security Critical", "yes"),
                ("Shipped", "yes"),
                ("CPEPrefix", "unknown"),
                ("Description", "A test metadata file, with a\n"
                 " multi-line description."),
                ("Local Modifications", "None,\nEXCEPT:\n* nothing."),
            ],
        )
        self.assertEqual((1, 20),
                         all_metadata[0].get_first_and_last_line_number())

        # Check the parser handles different casing for field names, and
        # strips leading and trailing whitespace from values.
        self.assertListEqual(
            all_metadata[1].get_entries(),
            [
                ("Name",
                 "Test-B README for Chromium metadata (3 errors, 1 warning)"),
                ("SHORT NAME", "metadata-test-invalid"),
                ("URL", "file://home/drive/chromium/src/metadata"),
                ("Version", "0"),
                ("Date", "2020-12-03"),
                ("License", "MIT"),
                ("Security critical", "yes"),
                ("Shipped", "Yes"),
                ("Description", ""),
                ("Local Modifications", "None."),
            ],
        )
        self.assertEqual((24, 46),
                         all_metadata[1].get_first_and_last_line_number())

        # Check repeated fields persist in the metadata's entries.
        self.assertListEqual(
            all_metadata[2].get_entries(),
            [
                ("Name",
                 "Test-C README for Chromium metadata (4 errors, 1 warning)"),
                ("URL", "https://www.example.com/first"),
                ("URL", "https://www.example.com/second"),
                ("Version", "N/A"),
                ("Date", "2020-12-03"),
                ("License", "Custom license"),
                ("Security Critical", "yes"),
                ("Description", """Test metadata with multiple entries for one field, and
missing a mandatory field.
These are the expected errors (here for reference only):

1. Required field 'License Android Compatible' is missing.

2. Required field 'License File' is missing.

3. Required field 'Shipped' is missing.

4. Repeated fields: URL (2)

warnings:
1. License has a license not in the allowlist.
(see https://source.chromium.org/chromium/chromiu
m/tools/depot_tools/+/main:metadata/fields/custom/license_al
lowlist.py). Licenses not allowlisted: 'Custom license'."""),

            ],
        )
        self.assertEqual((51, 76),
                         all_metadata[2].get_first_and_last_line_number())

    def test_parse_multiple_local_modifications(self):
        """Check parsing works for multiple dependencies, each with different local modifications."""
        filepath = os.path.join(
            _THIS_DIR, "data", "README.chromium.test.multi-local-modifications")
        content = gclient_utils.FileRead(filepath)
        all_metadata = metadata.parse.parse_content(content)

        self.assertEqual(len(all_metadata), 4)

        self.assertListEqual(
            all_metadata[0].get_entries(),
            [
                ("Name", "Test package 1"),
                ("Local Modifications",
                 "1. Modified X file\n2. Deleted Y file"),
            ],
        )
        self.assertEqual((1, 5),
                         all_metadata[0].get_first_and_last_line_number())

        self.assertListEqual(
            all_metadata[1].get_entries(),
            [
                ("Name", "Test package 2"),
                ("Local Modifications", "None"),
            ],
        )
        self.assertEqual((9, 10),
                         all_metadata[1].get_first_and_last_line_number())

        self.assertListEqual(
            all_metadata[2].get_entries(),
            [
                ("Name", "Test package 3"),
                ("Local Modifications", "None."),
            ],
        )
        self.assertEqual((14, 24),
                         all_metadata[2].get_first_and_last_line_number())

        self.assertListEqual(
            all_metadata[3].get_entries(),
            [
                ("Name", "Test package 4"),
                ("Local Modifications", "None,\nExcept modified file X."),
            ],
        )
        self.assertEqual((28, 30),
                         all_metadata[3].get_first_and_last_line_number())

    def test_parse_per_field_line_numbers(self):
        """Check parsing marks the line numbers of each individual fields."""
        filepath = os.path.join(_THIS_DIR, "data",
                                "README.chromium.test.single-valid")
        content = gclient_utils.FileRead(filepath)
        all_metadata = metadata.parse.parse_content(content)

        self.assertEqual(len(all_metadata), 1)

        dm = all_metadata[0]
        field_spec = metadata.fields.known
        expected_line_numbers = {
            field_spec.NAME: [1],
            field_spec.SHORT_NAME: [2],
            field_spec.URL: [3, 4],
            field_spec.VERSION: [8],
            field_spec.DATE: [9],
            field_spec.LICENSE: [10],
            field_spec.LICENSE_FILE: [11],
            field_spec.SECURITY_CRITICAL: [12],
            field_spec.SHIPPED: [13],
            field_spec.CPE_PREFIX: [14],
            field_spec.DESCRIPTION: [16, 17, 18],
            field_spec.LOCAL_MODIFICATIONS: [20, 21],
        }
        self.assertEqual(dm.get_field_line_numbers(metadata.fields.known.NAME),
                         [1])

    def test_parse_mitigated(self):
        """Check parsing works for mitigated CVE entries."""
        filepath = os.path.join(_THIS_DIR, "data", "README.chromium.test.mitigated")
        content = gclient_utils.FileRead(filepath)
        all_metadata = metadata.parse.parse_content(content)

        self.assertEqual(len(all_metadata), 1)

        # Check that the CVEs are properly parsed
        self.assertListEqual(
            all_metadata[0].mitigated,
            ["CVE-2011-4061", "CVE-2024-7255", "CVE-2024-7256"]
        )

    def test_invalid_mitigated(self):
        """Check validation fails for invalid CVE IDs."""
        content = """Name: Test Package
Mitigated: CVE-2024-123, NOT-A-CVE
Description: Test package with invalid CVEs.
"""
        all_metadata = metadata.parse.parse_content(content)
        self.assertEqual(len(all_metadata), 1)

        validation_results = all_metadata[0].validate("", "", False)
        self.assertTrue(any(
            result.get_tag("field") == "Mitigated" and
            isinstance(result, metadata.validation_result.ValidationWarning)
            for result in validation_results
        ))


    def test_vulnerability_ids(self):
        # Valid IDs
        valid_ids = [
            "CVE-2024-12345",
            "CVE-2024-1234567",
            "PYSEC-2024-1234",
            "OSV-2024-1234",
            "DSA-1234-1",
            "GHSA-1234-5678-90ab",
        ]

        # Invalid IDs
        invalid_ids = [
            "CVE-123-456",
            "GHSA-123-456",
            "PYSEC-2024",           # Missing ID part.
            "NOT-A-VALID-ID",       # Bad prefix.
            "CVE_2024_12345",       # Wrong separator.
            "",                     # Empty.
            " ",                    # Just space.
        ]

        test_ids = valid_ids + invalid_ids
        valid_result, invalid_result = metadata.fields.custom.mitigated.validate_cves(",".join(test_ids))

        self.assertListEqual(sorted(valid_result), sorted(valid_ids))
        self.assertListEqual(sorted(invalid_result), sorted(invalid_ids))

if __name__ == '__main__':
    unittest.main()

if __name__ == "__main__":
    unittest.main()
