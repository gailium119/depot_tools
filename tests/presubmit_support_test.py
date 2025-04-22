#!/usr/bin/env python3
# Copyright 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import io
import os.path
import sys
import unittest
from unittest import mock

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import gclient_utils
import presubmit_support
import subprocess2
from testing_support import fake_repos


class PresubmitSupportTest(unittest.TestCase):
    def test_environ(self):
        self.assertIsNone(os.environ.get('PRESUBMIT_FOO_ENV', None))
        kv = {'PRESUBMIT_FOO_ENV': 'FOOBAR'}
        with presubmit_support.setup_environ(kv):
            self.assertEqual(os.environ.get('PRESUBMIT_FOO_ENV', None),
                             'FOOBAR')
        self.assertIsNone(os.environ.get('PRESUBMIT_FOO_ENV', None))


class ProvidedDiffChangeFakeRepo(fake_repos.FakeReposBase):

    NB_GIT_REPOS = 1

    def populateGit(self):
        self._commit_git(
            'repo_1', {
                'to_be_modified': 'please change me\n',
                'to_be_deleted': 'delete\nme\n',
                'somewhere/else': 'not a top level file!\n',
            })
        self._commit_git(
            'repo_1', {
                'to_be_modified': 'changed me!\n',
                'to_be_deleted': None,
                'somewhere/else': 'still not a top level file!\n',
                'added': 'a new file\n',
            })


class ProvidedDiffChangeTest(fake_repos.FakeReposTestBase):

    FAKE_REPOS_CLASS = ProvidedDiffChangeFakeRepo

    def setUp(self):
        super(ProvidedDiffChangeTest, self).setUp()
        self.enabled = self.FAKE_REPOS.set_up_git()
        if not self.enabled:
            self.skipTest('git fake repos not available')
        self.repo = os.path.join(self.FAKE_REPOS.git_base, 'repo_1')
        diff = subprocess2.check_output(['git', 'show'],
                                        cwd=self.repo).decode('utf-8')
        self.change = self._create_change(diff)

    def _create_change(self, diff):
        with gclient_utils.temporary_file() as tmp:
            gclient_utils.FileWrite(tmp, diff)
            options = mock.Mock(root=self.repo,
                                all_files=False,
                                generate_diff=False,
                                description='description',
                                files=None,
                                diff_file=tmp)
            change = presubmit_support._parse_change(None, options)
            assert isinstance(change, presubmit_support.ProvidedDiffChange)
            return change

    def _get_affected_file_from_name(self, change, name):
        for file in change._affected_files:
            if file.LocalPath() == os.path.normpath(name):
                return file
        self.fail(f'No file named {name}')

    def _test(self, name, old, new):
        affected_file = self._get_affected_file_from_name(self.change, name)
        self.assertEqual(affected_file.OldContents(), old)
        self.assertEqual(affected_file.NewContents(), new)

    def test_old_contents_of_added_file_returns_empty(self):
        self._test('added', [], ['a new file'])

    def test_old_contents_of_deleted_file_returns_whole_file(self):
        self._test('to_be_deleted', ['delete', 'me'], [])

    def test_old_contents_of_modified_file(self):
        self._test('to_be_modified', ['please change me'], ['changed me!'])

    def test_old_contents_of_file_with_nested_dirs(self):
        self._test('somewhere/else', ['not a top level file!'],
                   ['still not a top level file!'])

    def test_unix_local_paths(self):
        if sys.platform == 'win32':
            self.assertIn(r'somewhere\else', self.change.LocalPaths())
        else:
            self.assertIn('somewhere/else', self.change.LocalPaths())
        self.assertIn('somewhere/else', self.change.UnixLocalPaths())


class TestGenerateDiff(fake_repos.FakeReposTestBase):
    """ Tests for --generate_diff.

    The option is used to generate diffs of given files against the upstream
    server as base.
    """
    FAKE_REPOS_CLASS = ProvidedDiffChangeFakeRepo

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.FAKE_REPOS.git_base, 'repo_1')
        self.parser = mock.Mock()
        self.parser.error.side_effect = SystemExit

    def test_with_diff_file(self):
        """Tests that only either --generate_diff or --diff_file is allowed."""
        options = mock.Mock(root=self.repo,
                            all_files=False,
                            generate_diff=True,
                            description='description',
                            files=None,
                            diff_file="patch.diff")
        with self.assertRaises(SystemExit):
            presubmit_support._parse_change(self.parser, options)

        self.parser.error.assert_called_once_with(
            '<diff_file> cannot be specified when <generate_diff> is set.', )

    @mock.patch('presubmit_diff.create_diffs')
    def test_with_all_files(self, create_diffs):
        """Ensures --generate_diff is noop if --all_files is specified."""
        options = mock.Mock(root=self.repo,
                            all_files=True,
                            generate_diff=True,
                            description='description',
                            files=None,
                            source_controlled_only=False,
                            diff_file=None)
        changes = presubmit_support._parse_change(self.parser, options)
        self.assertEqual(changes.AllFiles(),
                         ['added', 'somewhere/else', 'to_be_modified'])
        create_diffs.assert_not_called()

    @mock.patch('presubmit_diff.fetch_content')
    def test_with_files(self, fetch_content):
        """Tests --generate_diff with files, which should call create_diffs()."""
        # fetch_content would return the old content of a given file.
        # In this test case, the mocked file is a newly added file.
        # hence, empty content.
        fetch_content.side_effect = ['']
        options = mock.Mock(root=self.repo,
                            all_files=False,
                            gerrit_url='https://chromium.googlesource.com',
                            generate_diff=True,
                            description='description',
                            files=['added'],
                            source_controlled_only=False,
                            diff_file=None)
        change = presubmit_support._parse_change(self.parser, options)
        affected_files = change.AffectedFiles()
        self.assertEqual(len(affected_files), 1)
        self.assertEqual(affected_files[0].LocalPath(), 'added')


class TestParseDiff(unittest.TestCase):
    """A suite of tests related to diff parsing and processing."""

    def _test_diff_to_change_files(self, diff, expected):
        with gclient_utils.temporary_file() as tmp:
            gclient_utils.FileWrite(tmp, diff, mode='w+')
            content, change_files = presubmit_support._process_diff_file(tmp)
            self.assertCountEqual(content, diff)
            self.assertCountEqual(change_files, expected)

    def test_diff_to_change_files_raises_on_empty_diff_header(self):
        diff = """
diff --git a/foo b/foo

"""
        with self.assertRaises(presubmit_support.PresubmitFailure):
            self._test_diff_to_change_files(diff=diff, expected=[])

    def test_diff_to_change_files_simple_add(self):
        diff = """
diff --git a/foo b/foo
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+add
"""
        self._test_diff_to_change_files(diff=diff, expected=[('A', 'foo')])

    def test_diff_to_change_files_simple_delete(self):
        diff = """
diff --git a/foo b/foo
deleted file mode 100644
index f675c2a..0000000
--- a/foo
+++ /dev/null
@@ -1,1 +0,0 @@
-delete
"""
        self._test_diff_to_change_files(diff=diff, expected=[('D', 'foo')])

    def test_diff_to_change_files_simple_modification(self):
        diff = """
diff --git a/foo b/foo
index d7ba659f..b7957f3 100644
--- a/foo
+++ b/foo
@@ -29,7 +29,7 @@
other
random
text
-  foo1
+  foo2
other
random
text
"""
        self._test_diff_to_change_files(diff=diff, expected=[('M', 'foo')])

    def test_diff_to_change_files_multiple_changes(self):
        diff = """
diff --git a/foo b/foo
index d7ba659f..b7957f3 100644
--- a/foo
+++ b/foo
@@ -29,7 +29,7 @@
other
random
text
-  foo1
+  foo2
other
random
text
diff --git a/bar b/bar
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ b/bar
@@ -0,0 +1 @@
+add
diff --git a/baz b/baz
deleted file mode 100644
index f675c2a..0000000
--- a/baz
+++ /dev/null
@@ -1,1 +0,0 @@
-delete
"""
        self._test_diff_to_change_files(diff=diff,
                                        expected=[('M', 'foo'), ('A', 'bar'),
                                                  ('D', 'baz')])

    def test_parse_unified_diff_with_valid_diff(self):
        diff = """
diff --git a/foo b/foo
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+add
"""
        res = presubmit_support._parse_unified_diff(diff)
        self.assertCountEqual(
            res, {
                'foo':
                """
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ b/foo
@@ -0,0 +1 @@
+add
"""
            })

    def test_parse_unified_diff_with_valid_diff_noprefix(self):
        diff = """
diff --git foo foo
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ foo
@@ -0,0 +1 @@
+add
"""
        res = presubmit_support._parse_unified_diff(diff)
        self.assertCountEqual(
            res, {
                'foo':
                """
new file mode 100644
index 0000000..9daeafb
--- /dev/null
+++ foo
@@ -0,0 +1 @@
+add
"""
            })

    def test_parse_unified_diff_with_invalid_diff(self):
        diff = """
diff --git a/ffoo b/foo
"""
        with self.assertRaises(presubmit_support.PresubmitFailure):
            presubmit_support._parse_unified_diff(diff)

    def test_diffs_to_change_files_with_empty_diff(self):
        res = presubmit_support._diffs_to_change_files({'file': ''})
        self.assertEqual(res, [('M', 'file')])


class PresubmitResultLocationTest(unittest.TestCase):

    def test_invalid_missing_filepath(self):
        with self.assertRaisesRegex(ValueError, 'file path is required'):
            presubmit_support._PresubmitResultLocation(file_path='').validate()

    def test_invalid_abs_filepath_except_for_commit_msg(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='/foo')
        with self.assertRaisesRegex(ValueError,
                                    'file path must be relative path'):
            loc.validate()
        loc = presubmit_support._PresubmitResultLocation(
            file_path='/COMMIT_MSG')
        try:
            loc.validate()
        except ValueError:
            self.fail("validate should not fail for /COMMIT_MSG path")

    def test_invalid_end_line_without_start_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         end_line=5)
        with self.assertRaisesRegex(ValueError, 'end_line must be empty'):
            loc.validate()

    def test_invalid_start_col_without_start_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_col=5)
        with self.assertRaisesRegex(ValueError, 'start_col must be empty'):
            loc.validate()

    def test_invalid_end_col_without_start_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         end_col=5)
        with self.assertRaisesRegex(ValueError, 'end_col must be empty'):
            loc.validate()

    def test_invalid_negative_start_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=-1)
        with self.assertRaisesRegex(ValueError,
                                    'start_line MUST not be negative'):
            loc.validate()

    def test_invalid_non_positive_end_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=1,
                                                         end_line=0)
        with self.assertRaisesRegex(ValueError, 'end_line must be positive'):
            loc.validate()

    def test_invalid_negative_start_col(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=1,
                                                         end_line=1,
                                                         start_col=-1)
        with self.assertRaisesRegex(ValueError,
                                    'start_col MUST not be negative'):
            loc.validate()

    def test_invalid_negative_end_col(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=1,
                                                         end_line=1,
                                                         end_col=-1)
        with self.assertRaisesRegex(ValueError, 'end_col MUST not be negative'):
            loc.validate()

    def test_invalid_start_after_end_line(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=6,
                                                         end_line=5)
        with self.assertRaisesRegex(ValueError, 'must not be after'):
            loc.validate()

    def test_invalid_start_after_end_col(self):
        loc = presubmit_support._PresubmitResultLocation(file_path='foo',
                                                         start_line=5,
                                                         start_col=11,
                                                         end_line=5,
                                                         end_col=10)
        with self.assertRaisesRegex(ValueError, 'must not be after'):
            loc.validate()


class PresubmitResultTest(unittest.TestCase):

    def test_handle_message_only(self):
        result = presubmit_support._PresubmitResult('Simple message')
        out = io.StringIO()
        result.handle(out)
        self.assertEqual(out.getvalue(), 'Simple message\n')

    def test_handle_full_args(self):
        result = presubmit_support._PresubmitResult(
            'This is a message',
            items=['item1', 'item2'],
            long_text='Long text here.',
            locations=[
                presubmit_support._PresubmitResultLocation(
                    file_path=presubmit_support._PresubmitResultLocation.
                    COMMIT_MSG_PATH),
                presubmit_support._PresubmitResultLocation(
                    file_path='file1',
                    start_line=10,
                    end_line=10,
                ),
                presubmit_support._PresubmitResultLocation(
                    file_path='file2',
                    start_line=11,
                    end_line=15,
                ),
                presubmit_support._PresubmitResultLocation(
                    file_path='file3',
                    start_line=5,
                    start_col=0,
                    end_line=8,
                    end_col=5,
                )
            ])
        out = io.StringIO()
        result.handle(out)
        expected = ('This is a message\n'
                    '  item1\n'
                    '  item2\n'
                    'Found in:\n'
                    '  - Commit Message\n'
                    '  - file1 [Ln 10]\n'
                    '  - file2 [Ln 11 - 15]\n'
                    '  - file3 [Ln 5, Col 0 - Ln 8, Col 5]\n'
                    '\n***************\n'
                    'Long text here.\n'
                    '***************\n')
        self.assertEqual(out.getvalue(), expected)

    def test_json_format(self):
        loc1 = presubmit_support._PresubmitResultLocation(file_path='file1',
                                                          start_line=1,
                                                          end_line=1)
        loc2 = presubmit_support._PresubmitResultLocation(file_path='file2',
                                                          start_line=5,
                                                          start_col=2,
                                                          end_line=6,
                                                          end_col=10)
        result = presubmit_support._PresubmitResult('This is a message',
                                                    items=['item1', 'item2'],
                                                    long_text='Long text here.',
                                                    locations=[loc1, loc2])
        expected = {
            'message':
            'This is a message',
            'items': ['item1', 'item2'],
            'locations': [
                {
                    'file_path': 'file1',
                    'start_line': 1,
                    'start_col': 0,
                    'end_line': 1,
                    'end_col': 0
                },
                {
                    'file_path': 'file2',
                    'start_line': 5,
                    'start_col': 2,
                    'end_line': 6,
                    'end_col': 10
                },
            ],
            'long_text':
            'Long text here.',
            'fatal':
            False,
        }
        self.assertEqual(result.json_format(), expected)

if __name__ == "__main__":
    unittest.main()
