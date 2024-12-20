#!/usr/bin/env python3
# Copyright 2023 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest
import unittest.mock

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
# The repo's root directory.
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))

# Add the repo's root directory for clearer imports.
sys.path.insert(0, _ROOT_DIR)

import gclient_utils
import metadata.validate
import metadata.validation_result
import metadata.fields.known

# Common paths for tests.
_SOURCE_FILE_DIR = os.path.join(_THIS_DIR, "data")
_VALID_METADATA_FILEPATH = os.path.join(_THIS_DIR, "data",
                                        "README.chromium.test.multi-valid")
_INVALID_METADATA_FILEPATH = os.path.join(_THIS_DIR, "data",
                                          "README.chromium.test.multi-invalid")


class ValidateContentTest(unittest.TestCase):
    """Tests for the validate_content function."""
    def test_empty(self):
        # Validate empty content (should result in a validation error).
        results = metadata.validate.validate_content(
            content="",
            source_file_dir=_SOURCE_FILE_DIR,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_fatal())

    def test_valid(self):
        # Validate valid file content (no errors or warnings).
        results = metadata.validate.validate_content(
            content=gclient_utils.FileRead(_VALID_METADATA_FILEPATH),
            source_file_dir=_SOURCE_FILE_DIR,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(results), 0)

    def test_invalid(self):
        # Validate invalid file content (both errors and warnings).
        results = metadata.validate.validate_content(
            content=gclient_utils.FileRead(_INVALID_METADATA_FILEPATH),
            source_file_dir=_SOURCE_FILE_DIR,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(results), 11)
        error_count = 0
        warning_count = 0
        for result in results:
            if result.is_fatal():
                error_count += 1
            else:
                warning_count += 1
        self.assertEqual(error_count, 8)
        self.assertEqual(warning_count, 3)


class ValidateFileTest(unittest.TestCase):
    """Tests for the validate_file function."""
    def test_missing(self):
        # Validate a file that does not exist.
        results = metadata.validate.validate_file(
            filepath=os.path.join(_THIS_DIR, "data", "MISSING.chromium"),
            repo_root_dir=_THIS_DIR,
        )
        # There should be exactly 1 error returned.
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_fatal())

    def test_valid(self):
        # Validate a valid file (no errors or warnings).
        results = metadata.validate.validate_file(
            filepath=_VALID_METADATA_FILEPATH,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(results), 0)

    def test_invalid(self):
        # Validate an invalid file (both errors and warnings).
        results = metadata.validate.validate_file(
            filepath=_INVALID_METADATA_FILEPATH,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(results), 11)
        error_count = 0
        warning_count = 0
        for result in results:
            if result.is_fatal():
                error_count += 1
            else:
                warning_count += 1
        self.assertEqual(error_count, 8)
        self.assertEqual(warning_count, 3)


class CheckFileTest(unittest.TestCase):
    """Tests for the check_file function."""
    def test_missing(self):
        # Check a file that does not exist.
        errors, warnings = metadata.validate.check_file(
            filepath=os.path.join(_THIS_DIR, "data", "MISSING.chromium"),
            repo_root_dir=_THIS_DIR,
        )
        # TODO(aredulla): update this test once validation errors can be
        # returned as errors. Bug: b/285453019.
        # self.assertEqual(len(errors), 1)
        # self.assertEqual(len(warnings), 0)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 1)

    def test_valid(self):
        # Check file with valid content (no errors or warnings).
        errors, warnings = metadata.validate.check_file(
            filepath=_VALID_METADATA_FILEPATH,
            repo_root_dir=_THIS_DIR,
        )
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_invalid(self):
        # Check file with invalid content (both errors and warnings).
        errors, warnings = metadata.validate.check_file(
            filepath=_INVALID_METADATA_FILEPATH,
            repo_root_dir=_THIS_DIR,
        )
        # TODO(aredulla): update this test once validation errors can be
        # returned as errors. Bug: b/285453019.
        # self.assertEqual(len(errors), 7)
        # self.assertEqual(len(warnings), 2)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 11)


class ValidationResultTest(unittest.TestCase):
    """Tests ValidationResult handles strings correctly."""

    def test_ordering(self):
        ve = metadata.validation_result.ValidationError(
            "abc",
            ["message1", "message2"],
        )

        vw = metadata.validation_result.ValidationError(
            "def",
            ["message3", "message4"],
        )

        # Check errors preceeds warnings.
        self.assertLess(ve, vw)
        self.assertGreater(vw, ve)
        self.assertEqual([ve, vw], list(sorted([vw, ve])))

    def test_message_generation(self):
        ve = metadata.validation_result.ValidationError(
            "abc",
            ["message1", "message2"],
        )
        self.assertEqual(
            ("Third party metadata issue: abc message1 message2 Check "
             "//third_party/README.chromium.template for details."),
            ve.get_message())
        self.assertEqual("abc message1 message2",
                         ve.get_message(prescript='', postscript=''))

    def test_getters(self):
        ve = metadata.validation_result.ValidationError(
            "abc",
            ["message1", "message2"],
        )
        self.assertEqual("abc", ve.get_reason())
        self.assertEqual(["message1", "message2"], ve.get_additional())


class ValidationWithLineNumbers(unittest.TestCase):

    def test_reports_line_number(self):
        """Checks validate reports line number if available."""
        filepath = os.path.join(_THIS_DIR, "data",
                                "README.chromium.test.validation-line-number")
        content = gclient_utils.FileRead(filepath)
        unittest.mock.patch(
            'metadata.fields.known.LICENSE_FILE.validate_on_disk',
            return_value=metadata.validation_result.ValidationError(
                "File doesn't exist."))

        results = metadata.validate.validate_content(content,
                                                     "chromium/src/test_dir",
                                                     "chromium/src")

        for r in results:
            if r.get_reason() == 'License File is invalid.':
                self.assertEqual(r.get_lines(), [10])
            elif r.get_reason(
            ) == "Required field 'License Android Compatible' is missing.":
                # We can't add a line number to errors caused by missing fields.
                self.assertEqual(r.get_lines(), [])
            elif r.get_reason() == "Versioning fields are insufficient.":
                # We can't add a line number to errors caused by missing fields.
                self.assertEqual(r.get_lines(), [])
            elif r.get_reason(
            ) == "License has a license not in the allowlist.":
                self.assertEqual(r.get_lines(), [9])
            elif r.get_reason() == "URL is invalid.":
                self.assertEqual(r.get_lines(), [2, 3, 4])
            elif r.get_reason() == "Shipped in Chromium is invalid":
                self.assertEqual(r.get_lines(), [13])


class ValidateReciprocalLicenseTest(unittest.TestCase):
    """Tests that validate_content handles allowing reciprocal licenses correctly."""
    def test_reciprocal_licenses(self):
        # Test content with a reciprocal license (MPL-2.0).
        reciprocal_license_metadata_filepath = os.path.join(_THIS_DIR, "data",
            "README.chromium.test.reciprocal-license")
        # Without allow_reciprocal_licenses, should get a warning.
        results = metadata.validate.validate_content(
            content=gclient_utils.FileRead(reciprocal_license_metadata_filepath),
            source_file_dir=_SOURCE_FILE_DIR,
            repo_root_dir=_THIS_DIR,
            allow_reciprocal_licenses=False
        )

        license_warnings = []
        for result in results:
            if not result.is_fatal() and "License has a license not in the allowlist" in result.get_reason():
                license_warnings.append(result)

        self.assertEqual(len(license_warnings), 1, "Should warn about reciprocal license when not allowed")

        # With allow_reciprocal_licenses=True, should be no warnings.
        results = metadata.validate.validate_content(
            content=gclient_utils.FileRead(reciprocal_license_metadata_filepath),
            source_file_dir=_SOURCE_FILE_DIR,
            repo_root_dir=_THIS_DIR,
            allow_reciprocal_licenses=True
        )

        license_warnings = []
        for result in results:
            if not result.is_fatal() and "License has a license not in the allowlist" in result.get_reason():
                license_warnings.append(result)

        self.assertEqual(len(license_warnings), 0, "Should warn about reciprocal license when not allowed")

if __name__ == "__main__":
    unittest.main()
