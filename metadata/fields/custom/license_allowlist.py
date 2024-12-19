#!/usr/bin/env python3
# Copyright 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# These licenses are used to verify that code imported to Android complies with
# their licensing requirements. Do not add entries to this list without approval.
# Any licenses added should be a valid SPDX Identifier. For the full list of
# identifiers; see https://spdx.org/licenses/
ALLOWED_SPDX_LICENSES = frozenset([
    "APSL-2.0",
    "GPL-2.0-with-classpath-exception",
    "MIT-0",
    "MPL-1.1",
    "MPL-2.0",
    # Notice licenses.
    "Apache-2.0",
    "Apache-with-LLVM-Exception",
    "Apache-with-Runtime-Exception",
    "Artistic-2.0",
    "BSD-2-Clause",
    "BSD-2-Clause-Flex",
    "BSD-2-Clause-FreeBSD",
    "BSD-3-Clause",
    "BSD-4-Clause",
    "BSD-4-Clause-UC",
    "BSD-4-Clause-Wasabi",
    "BSD-Source-Code",
    "BSL-1.0",
    "Bitstream",
    "CC-BY-3.0",
    "CC-BY-4.0",
    "CERN",
    "Caffe",
    "FTL",
    "GNU-All-permissive-Copying-License",
    "HPND",
    "HPND-sell-variant",
    "IBM-DHCP",
    "ICU",
    "IJG",
    "ISC",
    "JSON",
    "JsonCPP",
    "Khronos",
    "Libpng",
    "Libpng-2.0",
    "LicenseRef-base64",
    "LicenseRef-takuya-ooura",
    "MIT",
    "MIT-Modern-Variant",
    "MS-PL",
    "NAIST-2003",
    "NCSA",
    "OFL-1.1",
    "OpenSSL",
    "SGI-B-2.0",
    "SSLeay",
    "SunPro",
    "Unicode-3.0",
    "Unicode-DFS-2015",
    "Unicode-DFS-2016",
    "WebM-Project-Patent",
    "X11",
    "X11-Lucent",
    "Zlib",
<<<<<<< PATCH SET (40d522 Adding 'Notice' Licenses to 'ALLOWED_SPDX_LICENSES')
    "cURL",
    "dso",
    "getopt",
    "libtiff",
    "pffft",
    "zxing",
=======
<<<<<<< PATCH SET (86722b Restructuring 'ALLOWED_SPDX_LICENSES' to show which licenses)
=======
    # Public Domain variants.
    "ISC",
    "ICU",
    "LZMA-SDK-9.22",
    "SunPro",
    "BSL-1.0",
>>>>>>> BASE      (ac7bfd Roll recipe dependencies (trivial).)
>>>>>>> BASE      (078de2 Restructuring 'ALLOWED_SPDX_LICENSES' to show which licenses)
])
