#!/usr/bin/env python3
# Copyright (c) 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import sys
import signal
import subprocess


def register_build_id(local_dev_server_path, build_id):
    subprocess.run([
        local_dev_server_path, '--register-build-id', build_id, '--builder-pid',
        str(os.getpid())
    ])


def print_wait_command(local_dev_server_path, build_id):
    print(
        'Build server might still be running some tasks in the background. '
        'Run this command to wait for pending build server tasks:',
        file=sys.stderr)
    cmd = [os.path.relpath(local_dev_server_path), '--wait-for-build', build_id]
    print(' '.join(cmd), file=sys.stderr)


def start_fast_local_dev_server(build_id, output_dir):
    print('+++ Detected android_static_analysis="build_server" +++',
          file=sys.stderr)
    print('build_id:', build_id, file=sys.stderr)

    src_dir = os.path.abspath(output_dir)
    while os.path.basename(src_dir) != 'src':
        src_dir = os.path.dirname(src_dir)
    local_dev_server_path = os.path.join(
        src_dir, 'build/android/fast_local_dev_server.py')

    print('Starting build server in the background.', file=sys.stderr)
    subprocess.Popen([local_dev_server_path, '--exit-on-idle', '--quiet'],
                     start_new_session=True)
    original_sigint_handler = signal.getsignal(signal.SIGINT)

    def _kill_handler(signum, frame):
        # Cancel the pending build tasks if user CTRL+c early.
        print('Canceling pending build_server tasks', file=sys.stderr)
        subprocess.run([local_dev_server_path, '--cancel-build', build_id])
        original_sigint_handler(signum, frame)

    signal.signal(signal.SIGINT, _kill_handler)

    # Tell the build server about us.
    register_build_id(local_dev_server_path, build_id)
    return local_dev_server_path


@contextlib.contextmanager
def build_server_context(build_id, out_dir, use_android_build_server=False):
    if not use_android_build_server:
        yield
        return
    canceled_build = False
    SetTtyEnv()
    server_path = start_fast_local_dev_server(build_id, out_dir)
    try:
        yield
    except KeyboardInterrupt:
        canceled_build = True
        raise
    finally:
        if not canceled_build:
            print_wait_command(server_path, build_id)


def SetTtyEnv():
    stdout_name = os.readlink('/proc/self/fd/1')
    os.environ.setdefault("AUTONINJA_STDOUT_NAME", stdout_name)
