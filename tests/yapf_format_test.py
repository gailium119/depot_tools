#!/usr/bin/env vpython3
# coding=utf-8
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gclient_paths_test
import yapf_format


class MockCompletedProcess:

    def __init__(self, returncode):
        self.returncode = returncode


class YapfFormatTest(gclient_paths_test.TestBase):

    def setUp(self):
        super().setUp()

        self.is_valid_yapfignore = mock.patch('yapf_format.is_valid_yapfignore',
                                              return_value=True).start()
        self.subprocess_run = mock.patch(
            'subprocess.run', return_value=MockCompletedProcess(0)).start()

    def testRunYapfWithYapfignore(self):
        """Verifies that it runs the YAPF where yapf_format.py exists."""
        file = os.path.join(self.getcwd(), 'build', 'PRESUBMIT.py')
        ignore_path = os.path.join(self.getcwd(), 'config', '.yapfignore')
        yapf_format.run_yapf([file, '--opt1'], ignore_path)
        self.subprocess_run.assert_called_with(
            [
                mock.ANY,  # vpython3
                os.path.join(os.path.dirname(yapf_format.__file__), 'yapf'),
                file,
                '--opt1',
            ],
            cwd=os.path.dirname(ignore_path))

    def testRunYapfWithoutYapfignore(self):
        """Verifies that it runs the YAPF where yapf_format.py exists."""
        file = os.path.join(self.getcwd(), 'build', 'PRESUBMIT.py')
        ignore_path = ""
        yapf_format.run_yapf([file, '--opt1'], ignore_path)
        self.subprocess_run.assert_called_with(
            [
                mock.ANY,  # vpython3
                os.path.join(os.path.dirname(yapf_format.__file__), 'yapf'),
                file,
                '--opt1',
            ],
            cwd=None)

    def testRunYapfWithInvalidYapfignore(self):
        """Verifies that run_yapf fails if given an invalid yapfignore."""
        file = os.path.join(self.getcwd(), 'build', 'PRESUBMIT.py')
        ignore_path = 'doesn\'t matter'
        self.is_valid_yapfignore.return_value = False
        yapf_format.run_yapf([file, '--opt1'], ignore_path)
        self.subprocess_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
