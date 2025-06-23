#!/usr/bin/env python3
# Copyright 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
""" This script is used to parse the DEPS file and print the result.
"""

import os
import sys
import gclient_eval


def main(args):
    target_deps_path = args[1]
    if not os.path.exists(target_deps_path):
        print(f'target_deps_path {target_deps_path} does not exist')
        return 1
    with open(target_deps_path, 'r') as f:
        content = f.read()
        result = gclient_eval.Parse(content, target_deps_path, None, None)
        print(f'result {result}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.stderr.write('interrupted\n')
        sys.exit(1)