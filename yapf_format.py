#!/usr/bin/env vpython3
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Formats a Python file with YAPF.

YAPF requires .yapfignore and .pyproject.toml to be located in the CWD
of the YAPF execution. Otherwise, it won't find and apply the config files.

This is a simple wrapper for YAPF, but allows users to specify the path
to .yapfignore, even if it's not in the CWD.
"""
import argparse
import contextlib
import os
import shutil
import subprocess
import sys

YAPF_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'yapf',
)

USAGE = '%(prog)s [options] [files [files ...]]'
DESCRIPTION = """This script is a simple wrapper for yapf,
but allows users to specify the path to .yapfignore.
If --yapfignore is specified, .yapfignore in the current working directory
will not be used."""


@contextlib.contextmanager
def setcwd(path):
    orig = os.getcwd()
    try:
        if path:
            os.chdir(path)
        yield
    finally:
        os.chdir(orig)


def run_yapf(argv, yapfignore):
    """Runs yapf in the folder where yapfigure is located.

    Returns:
      the exit code of the yapf process. 1 if the given yapfignore is non-empty
      and invalid.
    """
    if yapfignore and not is_valid_yapfignore(yapfignore):
        return 1
    cwd = os.path.dirname(os.path.abspath(yapfignore)) if yapfignore else None
    return subprocess.run([
        shutil.which('vpython3'),
        YAPF_PATH,
    ] + argv,
                          cwd=cwd)


def print_yapf_help():
    process = subprocess.Popen([
        shutil.which('vpython3'),
        YAPF_PATH,
        '--help',
    ],
                               stdout=subprocess.PIPE)
    output, _ = process.communicate()
    print(output.decode())
    return process.returncode


def is_valid_yapfignore(path):
    if not path:
        return True
    if not os.path.exists(path):
        print(f'{path} doesn\'t exist')
        return False
    if not os.path.isfile(path):
        print(f'{path} is not a file')
        return False
    if not os.access(path, os.R_OK):
        print(f'{path}: Permission denied')
        return False
    return True


def main(argv):
    parser = argparse.ArgumentParser(usage=USAGE, description=DESCRIPTION)
    parser.add_argument('--yapfignore', help='path to .yapfignore.')
    parser.add_argument('--yapfhelp',
                        action='store_true',
                        help='show yapf help message and exit.')
    parser.add_argument('files',
                        nargs='*',
                        help='list of files to Python files to format.')
    options, _ = parser.parse_known_args()
    if options.yapfhelp:
        sys.exit(print_yapf_help())

    sys.exit(run_yapf(argv, options.yapfignore).returncode)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
