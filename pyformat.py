#!/usr/bin/env vpython3
# Copyright (c) 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""pyformat runs YAPF with Chromium specific format configs."""

# File name for yapf style config files.
YAPF_CONFIG_FILENAME = '.style.yapf'


def _FindYapfConfigFile(fpath, yapf_config_cache, top_dir=None):
    """Checks if a yapf file is in any parent directory of fpath until top_dir.

    Recursively checks parent directories to find yapf file and if no yapf file
    is found returns None. Uses yapf_config_cache as a cache for previously found
    configs.
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

    yapf is supposed to handle the ignoring of files listed in .yapfignore itself,
    but this functionality appears to break when explicitly passing files to
    yapf for formatting. According to
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
        patterns: An iterable of strings containing fnmatch patterns to filter on.

    Returns:
        A list of strings containing all the elements of |filepaths| that did not
        match any of the patterns in |patterns|.
    """
    # Not inlined so that tests can use the same implementation.
    return [
        f for f in filepaths
        if not any(fnmatch.fnmatch(f, p) for p in patterns)
    ]


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
