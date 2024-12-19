#!/usr/bin/env python3
# Copyright 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# These licenses are used to verify that code imported to Android complies with
# their licensing requirements. Do not add entries to this list without approval.
# Any licenses added should be a valid SPDX Identifier. For the full list of
# identifiers; see https://spdx.org/licenses/.
# Licenses below are grouped by restrictiveness level and then alphabetically.
ALLOWED_SPDX_LICENSES = frozenset([
    # other_ignorable.
    "LZMA-SDK-9.22",
    # permissive.
    "GPL-2.0-with-classpath-exception",
    "MIT-0",
    # notice.
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-2-Clause-FreeBSD",
    "BSD-3-Clause",
    "BSD-4-Clause",
    "BSD-4-Clause-UC",
    "BSD-Source-Code",
    "BSL-1.0",
    "ICU",
    "ISC",
    "MIT",
    "MIT-Modern-Variant",
    "NCSA",
    "OFL-1.1",
    "SGI-B-2.0",
    "SunPro",
    "Unicode-3.0",
    "Unicode-DFS-2015",
    "Unicode-DFS-2016",
    "X11",
    "Zlib",
    # reciprocal. TODO(b/385020146): Only allow for opensource projects.
    "APSL-2.0",
    "MPL-1.1",
    "MPL-2.0",
])
