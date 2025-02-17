#!/usr/bin/env vpython3
# coding=utf-8
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for cl_format.py"""

import logging
import os
import shutil
import sys
import tempfile
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metrics_utils
# We have to disable monitoring before importing git_cl.
metrics_utils.COLLECT_METRICS = False

import cl_format
import clang_format
import gclient_utils
import subprocess2

# TODO: Should fix these warnings.
# pylint: disable=line-too-long


def callError(code=1, cmd='', cwd='', stdout=b'', stderr=b''):
    return subprocess2.CalledProcessError(code, cmd, cwd, stdout, stderr)


CERR1 = callError(1)


class CMDFormatTestCase(unittest.TestCase):

    def setUp(self):
        super(CMDFormatTestCase, self).setUp()
        mock.patch('cl_format.RunCommand').start()
        mock.patch('clang_format.FindClangFormatToolInChromiumTree').start()
        mock.patch('clang_format.FindClangFormatScriptInChromiumTree').start()
        self._top_dir = tempfile.mkdtemp()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        shutil.rmtree(self._top_dir)
        super(CMDFormatTestCase, self).tearDown()

    def _make_temp_file(self, fname, contents):
        gclient_utils.FileWrite(os.path.join(self._top_dir, fname),
                                ('\n'.join(contents)))

    def _make_yapfignore(self, contents):
        self._make_temp_file('.yapfignore', contents)

    def _check_yapf_filtering(self, files, expected):
        self.assertEqual(
            expected,
            cl_format._FilterYapfIgnoredFiles(
                files, cl_format._GetYapfIgnorePatterns(self._top_dir)))

    def _run_command_mock(self, return_value):

        def f(*args, **kwargs):
            if 'stdin' in kwargs:
                self.assertIsInstance(kwargs['stdin'], bytes)
            return return_value

        return f

    def testClangFormatDiffFull(self):
        self._make_temp_file('test.cc', ['// test'])
        diff_file = [os.path.join(self._top_dir, 'test.cc')]
        mock_opts = mock.Mock(full=True, dry_run=True, diff=False)

        # Diff
        cl_format.RunCommand.side_effect = self._run_command_mock('  // test')
        return_value = cl_format._RunClangFormatDiff(mock_opts, diff_file,
                                                     self._top_dir, 'HEAD')
        self.assertEqual(2, return_value)

        # No diff
        cl_format.RunCommand.side_effect = self._run_command_mock('// test')
        return_value = cl_format._RunClangFormatDiff(mock_opts, diff_file,
                                                     self._top_dir, 'HEAD')
        self.assertEqual(0, return_value)

    def testClangFormatDiff(self):
        # A valid file is required, so use this test.
        clang_format.FindClangFormatToolInChromiumTree.return_value = __file__
        mock_opts = mock.Mock(full=False, dry_run=True, diff=False)

        # Diff
        cl_format.RunCommand.side_effect = self._run_command_mock('error')
        return_value = cl_format._RunClangFormatDiff(mock_opts, ['.'],
                                                     self._top_dir, 'HEAD')
        self.assertEqual(2, return_value)

        # No diff
        cl_format.RunCommand.side_effect = self._run_command_mock('')
        return_value = cl_format._RunClangFormatDiff(mock_opts, ['.'],
                                                     self._top_dir, 'HEAD')
        self.assertEqual(0, return_value)

    def testYapfignoreExplicit(self):
        self._make_yapfignore(['foo/bar.py', 'foo/bar/baz.py'])
        files = [
            'bar.py',
            'foo/bar.py',
            'foo/baz.py',
            'foo/bar/baz.py',
            'foo/bar/foobar.py',
        ]
        expected = [
            'bar.py',
            'foo/baz.py',
            'foo/bar/foobar.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreSingleWildcards(self):
        self._make_yapfignore(['*bar.py', 'foo*', 'baz*.py'])
        files = [
            'bar.py',  # Matched by *bar.py.
            'bar.txt',
            'foobar.py',  # Matched by *bar.py, foo*.
            'foobar.txt',  # Matched by foo*.
            'bazbar.py',  # Matched by *bar.py, baz*.py.
            'bazbar.txt',
            'foo/baz.txt',  # Matched by foo*.
            'bar/bar.py',  # Matched by *bar.py.
            'baz/foo.py',  # Matched by baz*.py, foo*.
            'baz/foo.txt',
        ]
        expected = [
            'bar.txt',
            'bazbar.txt',
            'baz/foo.txt',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreMultiplewildcards(self):
        self._make_yapfignore(['*bar*', '*foo*baz.txt'])
        files = [
            'bar.py',  # Matched by *bar*.
            'bar.txt',  # Matched by *bar*.
            'abar.py',  # Matched by *bar*.
            'foobaz.txt',  # Matched by *foo*baz.txt.
            'foobaz.py',
            'afoobaz.txt',  # Matched by *foo*baz.txt.
        ]
        expected = [
            'foobaz.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreComments(self):
        self._make_yapfignore(['test.py', '#test2.py'])
        files = [
            'test.py',
            'test2.py',
        ]
        expected = [
            'test2.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfHandleUtf8(self):
        self._make_yapfignore(['test.py', 'test_🌐.py'])
        files = [
            'test.py',
            'test_🌐.py',
            'test2.py',
        ]
        expected = [
            'test2.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreBlankLines(self):
        self._make_yapfignore(['test.py', '', '', 'test2.py'])
        files = [
            'test.py',
            'test2.py',
            'test3.py',
        ]
        expected = [
            'test3.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreWhitespace(self):
        self._make_yapfignore([' test.py '])
        files = [
            'test.py',
            'test2.py',
        ]
        expected = [
            'test2.py',
        ]
        self._check_yapf_filtering(files, expected)

    def testYapfignoreNoFiles(self):
        self._make_yapfignore(['test.py'])
        self._check_yapf_filtering([], [])

    def testYapfignoreMissingYapfignore(self):
        files = [
            'test.py',
        ]
        expected = [
            'test.py',
        ]
        self._check_yapf_filtering(files, expected)

    @mock.patch('gclient_paths.GetPrimarySolutionPath')
    def testRunMetricsXMLFormatSkipIfPresubmit(self, find_top_dir):
        """Verifies that it skips the formatting if opts.presubmit is True."""
        find_top_dir.return_value = self._top_dir
        mock_opts = mock.Mock(full=True,
                              dry_run=True,
                              diff=False,
                              presubmit=True)
        files = [
            os.path.join(self._top_dir, 'tools', 'metrics', 'ukm', 'ukm.xml'),
        ]
        return_value = cl_format._RunMetricsXMLFormat(mock_opts, files,
                                                      self._top_dir, 'HEAD')
        cl_format.RunCommand.assert_not_called()
        self.assertEqual(0, return_value)

    @mock.patch('gclient_paths.GetPrimarySolutionPath')
    def testRunMetricsFormatWithUkm(self, find_top_dir):
        """Checks if the command line arguments do not contain the input path.
        """
        find_top_dir.return_value = self._top_dir
        mock_opts = mock.Mock(full=True,
                              dry_run=False,
                              diff=False,
                              presubmit=False)
        files = [
            os.path.join(self._top_dir, 'tools', 'metrics', 'ukm', 'ukm.xml'),
        ]
        cl_format._RunMetricsXMLFormat(mock_opts, files, self._top_dir, 'HEAD')
        cl_format.RunCommand.assert_called_with([
            mock.ANY,
            os.path.join(self._top_dir, 'tools', 'metrics', 'ukm',
                         'pretty_print.py'),
            '--non-interactive',
        ],
                                                 cwd=self._top_dir)

    @mock.patch('gclient_paths.GetPrimarySolutionPath')
    def testRunMetricsFormatWithHistograms(self, find_top_dir):
        """Checks if the command line arguments contain the input file paths."""
        find_top_dir.return_value = self._top_dir
        mock_opts = mock.Mock(full=True,
                              dry_run=False,
                              diff=False,
                              presubmit=False)
        files = [
            os.path.join(self._top_dir, 'tools', 'metrics', 'histograms',
                         'enums.xml'),
            os.path.join(self._top_dir, 'tools', 'metrics', 'histograms',
                         'test_data', 'enums.xml'),
        ]
        cl_format._RunMetricsXMLFormat(mock_opts, files, self._top_dir, 'HEAD')

        pretty_print_path = os.path.join(self._top_dir, 'tools', 'metrics',
                                         'histograms', 'pretty_print.py')
        cl_format.RunCommand.assert_has_calls([
            mock.call(
                [mock.ANY, pretty_print_path, '--non-interactive', files[0]],
                cwd=self._top_dir),
            mock.call(
                [mock.ANY, pretty_print_path, '--non-interactive', files[1]],
                cwd=self._top_dir),
        ])

    @mock.patch('subprocess2.call')
    def testLUCICfgFormatWorks(self, mock_call):
        """Checks if lucicfg is given then input file path."""
        mock_opts = mock.Mock(dry_run=False)
        files = ['test/main.star']
        mock_call.return_value = 0
        ret = cl_format._RunLUCICfgFormat(mock_opts, files, self._top_dir,
                                          'HEAD')
        mock_call.assert_called_with([
            mock.ANY,
            'fmt',
            'test/main.star',
        ])
        self.assertEqual(ret, 0)

    @mock.patch('subprocess2.call')
    def testLUCICfgFormatWithDryRun(self, mock_call):
        """Tests the command with --dry-run."""
        mock_opts = mock.Mock(dry_run=True)
        files = ['test/main.star']
        cl_format._RunLUCICfgFormat(mock_opts, files, self._top_dir, 'HEAD')
        mock_call.assert_called_with([
            mock.ANY,
            'fmt',
            '--dry-run',
            'test/main.star',
        ])

    @mock.patch('subprocess2.call')
    def testLUCICfgFormatWithDryRunReturnCode(self, mock_call):
        """Tests that it returns 2 for non-zero exit codes."""
        mock_opts = mock.Mock(dry_run=True)
        files = ['test/main.star']
        run = cl_format._RunLUCICfgFormat

        mock_call.return_value = 0
        self.assertEqual(run(mock_opts, files, self._top_dir, 'HEAD'), 0)
        mock_call.return_value = 1
        self.assertEqual(run(mock_opts, files, self._top_dir, 'HEAD'), 2)
        mock_call.return_value = 2
        self.assertEqual(run(mock_opts, files, self._top_dir, 'HEAD'), 2)
        mock_call.return_value = 255
        self.assertEqual(run(mock_opts, files, self._top_dir, 'HEAD'), 2)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG if '-v' in sys.argv else logging.ERROR)
    unittest.main()
