#!/usr/bin/env vpython3
# Copyright (c) 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utiilities for format commands."""

import fnmatch
import os
import multiprocessing
import re
import subprocess2
import sys

from typing import NoReturn

import clang_format
import gclient_paths
import gclient_utils
import google_java_format
import metrics_xml_format
import rustfmt
import shutil
import swift_format

# File name for yapf style config files.
YAPF_CONFIG_FILENAME = '.style.yapf'


# TODO(b/386840832): refactor
def DieWithError(message, change_desc=None) -> NoReturn:
    if change_desc:
        SaveDescriptionBackup(change_desc)
        print('\n ** Content of CL description **\n' + '=' * 72 + '\n' +
              change_desc.description + '\n' + '=' * 72 + '\n')

    print(message, file=sys.stderr)
    sys.exit(1)


# TODO(b/386840832): remove
def SaveDescriptionBackup(change_desc):
    backup_path = os.path.join(DEPOT_TOOLS, DESCRIPTION_BACKUP_FILE)
    print('\nsaving CL description to %s\n' % backup_path)
    with open(backup_path, 'wb') as backup_file:
        backup_file.write(change_desc.description.encode('utf-8'))


# TODO(b/386840832): refactor
def RunCommand(args, error_ok=False, error_message=None, shell=False, **kwargs):
    try:
        stdout = subprocess2.check_output(args, shell=shell, **kwargs)
        return stdout.decode('utf-8', 'replace')
    except subprocess2.CalledProcessError as e:
        logging.debug('Failed running %s', args)
        if not error_ok:
            message = error_message or e.stdout.decode('utf-8', 'replace') or ''
            DieWithError('Command "%s" failed.\n%s' % (' '.join(args), message))
        out = e.stdout.decode('utf-8', 'replace')
        if e.stderr:
            out += e.stderr.decode('utf-8', 'replace')
        return out


# TODO(b/386840832): remove
def RunGit(args, **kwargs):
    """Returns stdout."""
    return RunCommand(['git'] + args, **kwargs)


# TODO(b/386840832): remove
def RunGitDiffCmd(diff_type,
                  upstream_commit,
                  files,
                  allow_prefix=False,
                  **kwargs):
    """Generates and runs diff command."""
    # Generate diff for the current branch's changes.
    diff_cmd = ['-c', 'core.quotePath=false', 'diff', '--no-ext-diff']

    if allow_prefix:
        # explicitly setting --src-prefix and --dst-prefix is necessary in the
        # case that diff.noprefix is set in the user's git config.
        diff_cmd += ['--src-prefix=a/', '--dst-prefix=b/']
    else:
        diff_cmd += ['--no-prefix']

    diff_cmd += diff_type
    diff_cmd += [upstream_commit, '--']

    if not files:
        return RunGit(diff_cmd, **kwargs)

    for file in files:
        if file != '-' and not os.path.isdir(file) and not os.path.isfile(file):
            DieWithError('Argument "%s" is not a file or a directory' % file)

    output = ''
    for files_batch in _SplitArgsByCmdLineLimit(files):
        output += RunGit(diff_cmd + files_batch, **kwargs)

    return output


def _RunClangFormatDiff(opts, clang_diff_files, top_dir, upstream_commit):
    """Runs clang-format-diff and sets a return value if necessary."""
    # Set to 2 to signal to CheckPatchFormatted() that this patch isn't
    # formatted. This is used to block during the presubmit.
    return_value = 0

    # Locate the clang-format binary in the checkout
    try:
        clang_format_tool = clang_format.FindClangFormatToolInChromiumTree()
    except clang_format.NotFoundError as e:
        DieWithError(e)

    if opts.full:
        cmd = [clang_format_tool]
        if not opts.dry_run and not opts.diff:
            cmd.append('-i')
        if opts.dry_run:
            for diff_file in clang_diff_files:
                with open(diff_file, 'r') as myfile:
                    code = myfile.read().replace('\r\n', '\n')
                    stdout = RunCommand(cmd + [diff_file], cwd=top_dir)
                    stdout = stdout.replace('\r\n', '\n')
                    if opts.diff:
                        sys.stdout.write(stdout)
                    if code != stdout:
                        return_value = 2
        else:
            stdout = RunCommand(cmd + clang_diff_files, cwd=top_dir)
            if opts.diff:
                sys.stdout.write(stdout)
    else:
        try:
            script = clang_format.FindClangFormatScriptInChromiumTree(
                'clang-format-diff.py')
        except clang_format.NotFoundError as e:
            DieWithError(e)

        cmd = ['vpython3', script, '-p0']
        if not opts.dry_run and not opts.diff:
            cmd.append('-i')

        diff_output = RunGitDiffCmd(['-U0'], upstream_commit, clang_diff_files)

        env = os.environ.copy()
        env['PATH'] = (str(os.path.dirname(clang_format_tool)) + os.pathsep +
                       env['PATH'])
        # If `clang-format-diff.py` is run without `-i` and the diff is
        # non-empty, it returns an error code of 1. This will cause `RunCommand`
        # to die with an error if `error_ok` is not set.
        stdout = RunCommand(cmd,
                            error_ok=True,
                            stdin=diff_output.encode(),
                            cwd=top_dir,
                            env=env,
                            shell=sys.platform.startswith('win32'))
        if opts.diff:
            sys.stdout.write(stdout)
        if opts.dry_run and len(stdout) > 0:
            return_value = 2

    return return_value


def _RunGoogleJavaFormat(opts, paths, top_dir, upstream_commit):
    """Runs google-java-format and sets a return value if necessary."""
    tool = google_java_format.FindGoogleJavaFormat()
    if tool is None:
        # Fail silently. It could be we are on an old chromium revision, or that
        # it is a non-chromium project. https://crbug.com/1491627
        print('google-java-format not found, skipping java formatting.')
        return 0

    base_cmd = [tool, '--aosp']
    if not opts.diff:
        if opts.dry_run:
            base_cmd += ['--dry-run']
        else:
            base_cmd += ['--replace']

    changed_lines_only = not opts.full
    if changed_lines_only:
        # Format two lines around each changed line so that the correct amount
        # of blank lines will be added between symbols.
        line_diffs = _ComputeFormatDiffLineRanges(paths,
                                                  upstream_commit,
                                                  expand=2)

    def _RunFormat(cmd, path, range_args, **kwds):
        stdout = RunCommand(cmd + range_args + [path], **kwds)

        if changed_lines_only:
            # google-java-format will not remove unused imports because they
            # do not fall within the changed lines. Run the command again to
            # remove them.
            if opts.diff:
                stdout = RunCommand(cmd + ['--fix-imports-only', '-'],
                                    stdin=stdout.encode(),
                                    **kwds)
            else:
                stdout += RunCommand(cmd + ['--fix-imports-only', path], **kwds)

        # If --diff is passed, google-java-format will output formatted content.
        # Diff it with the existing file in the checkout and output the result.
        if opts.diff:
            stdout = RunGitDiffCmd(['-U3'],
                                   '--no-index', [path, '-'],
                                   stdin=stdout.encode(),
                                   **kwds)
        return stdout

    results = []
    kwds = {'error_ok': True, 'cwd': top_dir}
    with multiprocessing.pool.ThreadPool() as pool:
        for path in paths:
            cmd = base_cmd.copy()
            range_args = []
            if changed_lines_only:
                ranges = line_diffs.get(path)
                if not ranges:
                    # E.g. There were only deleted lines.
                    continue
                range_args = ['--lines={}:{}'.format(a, b) for a, b in ranges]

            results.append(
                pool.apply_async(RunFormat,
                                 args=[cmd, path, range_args],
                                 kwds=kwds))

        return_value = 0
        for result in results:
            stdout = result.get()
            if stdout:
                if opts.diff:
                    sys.stdout.write('Requires formatting: ' + stdout)
                else:
                    return_value = 2

        return return_value


def _RunRustFmt(opts, rust_diff_files, top_dir, upstream_commit):
    """Runs rustfmt.  Just like _RunClangFormatDiff returns 2 to indicate that
    presubmit checks have failed (and returns 0 otherwise)."""
    # Locate the rustfmt binary.
    try:
        rustfmt_tool = rustfmt.FindRustfmtToolInChromiumTree()
    except rustfmt.NotFoundError as e:
        DieWithError(e)

    chromium_src_path = gclient_paths.GetPrimarySolutionPath()
    rustfmt_toml_path = os.path.join(chromium_src_path, '.rustfmt.toml')

    # TODO(crbug.com/1440869): Support formatting only the changed lines
    # if `opts.full or settings.GetFormatFullByDefault()` is False.
    cmd = [rustfmt_tool, f'--config-path={rustfmt_toml_path}']
    if opts.dry_run:
        cmd.append('--check')
    cmd += rust_diff_files
    rustfmt_exitcode = subprocess2.call(cmd)

    if opts.presubmit and rustfmt_exitcode != 0:
        return 2

    return 0


def _RunSwiftFormat(opts, swift_diff_files, top_dir, upstream_commit):
    """Runs swift-format.  Just like _RunClangFormatDiff returns 2 to indicate
    that presubmit checks have failed (and returns 0 otherwise)."""
    if sys.platform != 'darwin':
        DieWithError('swift-format is only supported on macOS.')
    # Locate the swift-format binary.
    try:
        swift_format_tool = swift_format.FindSwiftFormatToolInChromiumTree()
    except swift_format.NotFoundError as e:
        DieWithError(e)

    cmd = [swift_format_tool]
    if opts.dry_run:
        cmd += ['lint', '-s']
    else:
        cmd += ['format', '-i']
    cmd += swift_diff_files
    swift_format_exitcode = subprocess2.call(cmd)

    if opts.presubmit and swift_format_exitcode != 0:
        return 2

    return 0


def _RunYapf(opts, paths, top_dir, upstream_commit):
    depot_tools_path = os.path.dirname(os.path.abspath(__file__))
    yapf_tool = os.path.join(depot_tools_path, 'yapf')

    # Used for caching.
    yapf_configs = {}
    for p in paths:
        # Find the yapf style config for the current file, defaults to depot
        # tools default.
        _FindYapfConfigFile(p, yapf_configs, top_dir)

    # Turn on python formatting by default if a yapf config is specified.
    # This breaks in the case of this repo though since the specified
    # style file is also the global default.
    if opts.python is None:
        paths = [
            p for p in paths
            if _FindYapfConfigFile(p, yapf_configs, top_dir) is not None
        ]

    # Note: yapf still seems to fix indentation of the entire file
    # even if line ranges are specified.
    # See https://github.com/google/yapf/issues/499
    if not opts.full and paths:
        line_diffs = _ComputeFormatDiffLineRanges(paths, upstream_commit)

    yapfignore_patterns = _GetYapfIgnorePatterns(top_dir)
    paths = _FilterYapfIgnoredFiles(paths, yapfignore_patterns)

    return_value = 0
    for path in paths:
        yapf_style = _FindYapfConfigFile(path, yapf_configs, top_dir)
        # Default to pep8 if not .style.yapf is found.
        if not yapf_style:
            yapf_style = 'pep8'

        cmd = ['vpython3', yapf_tool, '--style', yapf_style, path]

        if not opts.full:
            ranges = line_diffs.get(path)
            if not ranges:
                continue
            # Only run yapf over changed line ranges.
            for diff_start, diff_end in ranges:
                cmd += ['-l', '{}-{}'.format(diff_start, diff_end)]

        if opts.diff or opts.dry_run:
            cmd += ['--diff']
            # Will return non-zero exit code if non-empty diff.
            stdout = RunCommand(cmd,
                                error_ok=True,
                                stderr=subprocess2.PIPE,
                                cwd=top_dir,
                                shell=sys.platform.startswith('win32'))
            if opts.diff:
                sys.stdout.write(stdout)
            elif len(stdout) > 0:
                return_value = 2
        else:
            cmd += ['-i']
            RunCommand(cmd, cwd=top_dir, shell=sys.platform.startswith('win32'))
    return return_value


def _RunGnFormat(opts, paths, top_dir, upstream_commit):
    cmd = ['gn', 'format']
    if opts.dry_run or opts.diff:
        cmd.append('--dry-run')
    return_value = 0
    for path in paths:
        gn_ret = subprocess2.call(cmd + [path],
                                  shell=sys.platform.startswith('win'),
                                  cwd=top_dir)
        if opts.dry_run and gn_ret == 2:
            return_value = 2  # Not formatted.
        elif opts.diff and gn_ret == 2:
            # TODO this should compute and print the actual diff.
            print('This change has GN build file diff for ' + path)
        elif gn_ret != 0:
            # For non-dry run cases (and non-2 return values for dry-run), a
            # nonzero error code indicates a failure, probably because the
            # file doesn't parse.
            DieWithError('gn format failed on ' + path +
                         '\nTry running `gn format` on this file manually.')
    return return_value


def _RunMojomFormat(opts, paths, top_dir, upstream_commit):
    primary_solution_path = gclient_paths.GetPrimarySolutionPath()
    if not primary_solution_path:
        DieWithError('Could not find the primary solution path (e.g. '
                     'the chromium checkout)')
    mojom_format_path = os.path.join(primary_solution_path, 'mojo', 'public',
                                     'tools', 'mojom', 'mojom_format.py')
    if not os.path.exists(mojom_format_path):
        DieWithError('Could not find mojom formater at '
                     f'"{mojom_format_path}"')

    cmd = ['vpython3', mojom_format_path]
    if opts.dry_run:
        cmd.append('--dry-run')
    cmd.extend(paths)

    ret = subprocess2.call(cmd)
    if opts.dry_run and ret != 0:
        return 2

    return ret


def _RunMetricsXMLFormat(opts, paths, top_dir, upstream_commit):
    # Skip the metrics formatting from the global presubmit hook. These files
    # have a separate presubmit hook that issues an error if the files need
    # formatting, whereas the top-level presubmit script merely issues a
    # warning. Formatting these files is somewhat slow, so it's important not to
    # duplicate the work.
    if opts.presubmit:
        return 0

    return_value = 0
    for path in paths:
        pretty_print_tool = metrics_xml_format.FindMetricsXMLFormatterTool(path)
        if not pretty_print_tool:
            continue

        cmd = [shutil.which('vpython3'), pretty_print_tool, '--non-interactive']
        # If the XML file is histograms.xml or enums.xml, add the xml path
        # to the command as histograms/pretty_print.py now needs a relative
        # path argument after splitting the histograms into multiple
        # directories. For example, in tools/metrics/ukm, pretty-print could
        # be run using: $ python pretty_print.py But in
        # tools/metrics/histogrmas, pretty-print should be run with an
        # additional relative path argument, like: $ python pretty_print.py
        # metadata/UMA/histograms.xml $ python pretty_print.py enums.xml
        metricsDir = metrics_xml_format.GetMetricsDir(top_dir, path)
        histogramsDir = os.path.join(top_dir, 'tools', 'metrics', 'histograms')
        if metricsDir == histogramsDir:
            cmd.append(path)
        if opts.dry_run or opts.diff:
            cmd.append('--diff')

        stdout = RunCommand(cmd, cwd=top_dir)
        if opts.diff:
            sys.stdout.write(stdout)
        if opts.dry_run and stdout:
            return_value = 2  # Not formatted.
    return return_value


def _RunLUCICfgFormat(opts, paths, top_dir, upstream_commit):
    depot_tools_path = os.path.dirname(os.path.abspath(__file__))
    lucicfg = os.path.join(depot_tools_path, 'lucicfg')
    if sys.platform == 'win32':
        lucicfg += '.bat'

    cmd = [lucicfg, 'fmt']
    if opts.dry_run:
        cmd.append('--dry-run')
    cmd.extend(paths)

    ret = subprocess2.call(cmd)
    if opts.dry_run and ret != 0:
        return 2

    return ret


def _ComputeFormatDiffLineRanges(files, upstream_commit, expand=0):
    """Gets the changed line ranges for each file since upstream_commit.

    Parses a git diff on provided files and returns a dict that maps a file name
    to an ordered list of range tuples in the form (start_line, count).
    Ranges are in the same format as a git diff.

    Args:
        files: List of paths to diff.
        upstream_commit: Commit to diff against to find changed lines.
        expand: Expand diff ranges by this many lines before & after.

    Returns:
        A dict of path->[(start_line, end_line), ...]
    """
    # If files is empty then diff_output will be a full diff.
    if len(files) == 0:
        return {}

    # Take the git diff and find the line ranges where there are changes.
    diff_output = RunGitDiffCmd(['-U0'],
                                upstream_commit,
                                files,
                                allow_prefix=True)

    pattern = r'(?:^diff --git a/(?:.*) b/(.*))|(?:^@@.*\+(.*) @@)'
    # 2 capture groups
    # 0 == fname of diff file
    # 1 == 'diff_start,diff_count' or 'diff_start'
    # will match each of
    # diff --git a/foo.foo b/foo.py
    # @@ -12,2 +14,3 @@
    # @@ -12,2 +17 @@
    # running re.findall on the above string with pattern will give
    # [('foo.py', ''), ('', '14,3'), ('', '17')]

    curr_file = None
    line_diffs = {}
    for match in re.findall(pattern, diff_output, flags=re.MULTILINE):
        if match[0] != '':
            # Will match the second filename in diff --git a/a.py b/b.py.
            curr_file = match[0]
            line_diffs[curr_file] = []
            prev_end = 1
        else:
            # Matches +14,3
            if ',' in match[1]:
                diff_start, diff_count = match[1].split(',')
            else:
                # Single line changes are of the form +12 instead of +12,1.
                diff_start = match[1]
                diff_count = 1

            # if the original lines were removed without replacements,
            # the diff count is 0. Then, no formatting is necessary.
            if diff_count == 0:
                continue

            diff_start = int(diff_start)
            diff_count = int(diff_count)
            # diff_count contains the diff_start line, and the line numbers
            # given to formatter args are inclusive. For example, in
            # google-java-format "--lines 5:10" includes 5th-10th lines.
            diff_end = diff_start + diff_count - 1 + expand
            diff_start = max(prev_end + 1, diff_start - expand)
            if diff_start <= diff_end:
                prev_end = diff_end
                line_diffs[curr_file].append((diff_start, diff_end))

    return line_diffs


def _FindYapfConfigFile(fpath, yapf_config_cache, top_dir=None):
    """Checks if a yapf file is in any parent directory of fpath until top_dir.

    Recursively checks parent directories to find yapf file and if no yapf file
    is found returns None. Uses yapf_config_cache as a cache for previously
    found configs.
    """
    fpath = os.path.abspath(fpath)
    # Return result if we've already computed it.
    if fpath in yapf_config_cache:
        return yapf_config_cache[fpath]

    parent_dir = os.path.dirname(fpath)
    if os.path.isfile(fpath):
        ret = _FindYapfConfigFile(parent_dir, yapf_config_cache, top_dir)
    else:
        # Otherwise fpath is a directory
        yapf_file = os.path.join(fpath, YAPF_CONFIG_FILENAME)
        if os.path.isfile(yapf_file):
            ret = yapf_file
        elif fpath in (top_dir, parent_dir):
            # If we're at the top level directory, or if we're at root
            # there is no provided style.
            ret = None
        else:
            # Otherwise recurse on the current directory.
            ret = _FindYapfConfigFile(parent_dir, yapf_config_cache, top_dir)
    yapf_config_cache[fpath] = ret
    return ret


def _GetYapfIgnorePatterns(top_dir):
    """Returns all patterns in the .yapfignore file.

    yapf is supposed to handle the ignoring of files listed in .yapfignore
    itself, but this functionality appears to break when explicitly passing
    files to yapf for formatting. According to
    https://github.com/google/yapf/blob/HEAD/README.rst#excluding-files-from-formatting-yapfignore,
    the .yapfignore file should be in the directory that yapf is invoked from,
    which we assume to be the top level directory in this case.

    Args:
        top_dir: The top level directory for the repository being formatted.

    Returns:
        A set of all fnmatch patterns to be ignored.
    """
    yapfignore_file = os.path.join(top_dir, '.yapfignore')
    ignore_patterns = set()
    if not os.path.exists(yapfignore_file):
        return ignore_patterns

    for line in gclient_utils.FileRead(yapfignore_file).split('\n'):
        stripped_line = line.strip()
        # Comments and blank lines should be ignored.
        if stripped_line.startswith('#') or stripped_line == '':
            continue
        ignore_patterns.add(stripped_line)
    return ignore_patterns


def _FilterYapfIgnoredFiles(filepaths, patterns):
    """Filters out any filepaths that match any of the given patterns.

    Args:
        filepaths: An iterable of strings containing filepaths to filter.
        patterns: An iterable of strings containing fnmatch patterns to filter
          on.

    Returns:
        A list of strings containing all the elements of |filepaths| that did
        not match any of the patterns in |patterns|.
    """
    # Not inlined so that tests can use the same implementation.
    return [
        f for f in filepaths
        if not any(fnmatch.fnmatch(f, p) for p in patterns)
    ]


def _SplitArgsByCmdLineLimit(args):
    """Splits a list of arguments into shorter lists that fit within the command
    line limit."""
    # The maximum command line length is 32768 characters on Windows and 2097152
    # characters on other platforms. Use a lower limit to be safe.
    command_line_limit = 30000 if sys.platform.startswith('win32') else 2000000

    batch_args = []
    batch_length = 0
    for arg in args:
        # Add 1 to account for the space between arguments.
        arg_length = len(arg) + 1
        # If the current argument is too long to fit in a single command line,
        # split it into smaller parts.
        if batch_length + arg_length > command_line_limit and batch_args:
            yield batch_args
            batch_args = []
            batch_length = 0

        batch_args.append(arg)
        batch_length += arg_length

    if batch_args:
        yield batch_args
