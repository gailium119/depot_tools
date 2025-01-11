#!/usr/bin/env python3
# Copyright 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# These licenses are used to verify that code imported to Android complies with
# their licensing requirements. Do not add entries to this list without approval.
# Any licenses added should be a valid SPDX Identifier. For the full list of
# identifiers; see https://spdx.org/licenses/.
# Licenses below are grouped by their classification (restrictiveness level) and then alphabetically.
#
# The classifications are based on the license classifier tool available at:
# https://github.com/google/licenseclassifier/blob/main/license_type.go
# Unfortunately, this open source version is no longer maintained.
# We use the following classifications, ordered by restrictiveness level:
# * other_ignorable, unencumbered, permissive, notice, reciprocal, restricted, by_exception_only
#
# REVIEW INSTRUCTIONS FOR ATLs (and a guide to contributing to this file):
# 1. Paste the contents of the license to be classified into
#   https://opensource.corp.google.com/license/analyze. This will provide the ID
#   and the classification. Command line alternatives are documented at
#   go/license-classifier, but work on entire files only.
#   1.1 'notice' or less restrictive are allowed ✅.
#   1.2 'reciprocal' are allowed, but only in open source projects e.g. Chromium.
#       See OPEN_SOURCE_SPDX_LICENSES below.
#   1.3 >='restricted' are handled on a case-by-case basis and require individual approval
#       from opensource-licensing@google.com and the ATLs.
#
# 2. Check spdx.org/licenses to see if the license has an SPDX identifier.
#   2.1 If it does: Use this value instead of the license classifier output,
#       and add it to ALLOWED_SPDX_LICENSES.
#   2.2 If does not: Add the id provided by the license classifier
#       to EXTENDED_LICENSE_CLASSIFIERS.
#
# 3. Ensure that it is added under the correct classification
#   e.g. '# notice', and then sorted alphabetically asscending.
#
# 4. Any questions? Contact opensource-licensing@google.com.
ALLOWED_SPDX_LICENSES = frozenset([
    # other_ignorable.
    # go/keep-sorted start
    "LZMA-SDK-9.22",
    # go/keep-sorted end
    # unencumbered.
    # go/keep-sorted start
    "blessing",
    "CC0-1.0",
    "Unlicense",
    # go/keep-sorted end
    # permissive.
    # go/keep-sorted start
    "GPL-2.0-with-autoconf-exception",
    "GPL-2.0-with-classpath-exception",
    "GPL-3.0-with-autoconf-exception",
    "MIT-0",
    # go/keep-sorted end
    # notice.
    # go/keep-sorted start
    "AML",
    "Apache-2.0",
    "Artistic-2.0",
    "Beerware",
    "BSD-2-Clause-FreeBSD",
    "BSD-2-Clause",
    "BSD-3-Clause-Attribution",
    "BSD-3-Clause",
    "BSD-4-Clause-UC",
    "BSD-4-Clause",
    "BSD-4.3TAHOE",
    "BSD-Source-Code",
    "BSL-1.0",
    "CC-BY-3.0",
    "CC-BY-4.0",
    "FTL",
    "HPND-sell-variant",
    "HPND",
    "ICU",
    "IJG",
    "ISC",
    "JSON",
    "Libpng",
    "libtiff",
    "MIT-Modern-Variant",
    "MIT",
    "MS-PL",
    "NAIST-2003",
    "NCSA",
    "OFL-1.1",
    "OpenSSL",
    "SGI-B-2.0",
    "SunPro",
    "Unicode-3.0",
    "Unicode-DFS-2015",
    "Unicode-DFS-2016",
    "X11",
    "Zlib",
    # go/keep-sorted end
])

# These are licenses that are not in the SPDX license list, but are identified
# by the license classifier.
EXTENDED_LICENSE_CLASSIFIERS = frozenset([
    # unencumbered.
    # go/keep-sorted start
    "AhemFont",
    "Android-SDK",
    "LZMA",
    "public-domain-md5",
    "SPL-SQRT-FLOOR",
    # go/keep-sorted end
    # permissive.
    # go/keep-sorted start
    "LicenseRef-AMSFonts-2.2",
    "test_fonts",
    # go/keep-sorted end
    # notice.
    # go/keep-sorted start
    "Apache-with-LLVM-Exception",
    "Apache-with-Runtime-Exception",
    "Bitstream",
    "BSD-2-Clause-Flex",
    "BSD-3-Clause-OpenMPI",
    "BSD-4-Clause-Wasabi",
    "Caffe",
    "CERN",
    "cURL",
    "dso",
    "Entenssa",
    "FFT2D",
    "getopt",
    "GIF-Encoder",
    "GNU-All-permissive-Copying-License",
    "IBM-DHCP",
    "JsonCPP",
    "Khronos",
    "Libpng-2.0",
    "LicenseRef-base64",
    "LicenseRef-OpenGLUT",
    "LicenseRef-takuya-ooura",
    "pffft",
    "Punycode",
    "SSLeay",
    "WebM-Project-Patent",
    "X11-Lucent",
    "zxing",
    # go/keep-sorted end
])

# These licenses are only allowed in open source projects due to their
# reciprocal requirements.
OPEN_SOURCE_SPDX_LICENSES = frozenset([
    # reciprocal.
    # go/keep-sorted start
    "APSL-2.0",
    "CDDL-1.0",
    "CDDL-1.1",
    "CPL-1.0",
    "EPL-1.0",
    "MPL-1.1",
    "MPL-2.0",
    # go/keep-sorted end
])

# TODO(b/388620886): Implement warning when changing _to_ these licenses
# (but not every time the README.chromium file is modified).
WITH_PERMISSION_ONLY = frozenset([
    # restricted.
    # go/keep-sorted start
    "CC-BY-SA-3.0",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL-2.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "NPL-1.1",
    # go/keep-sorted end
    # by_exception_only.
    # go/keep-sorted start
    "Commercial",
    "LicenseRef-Play-Core-SDK-TOS",
    "LicenseRef-Unity-Companion-License-1.3",
    "Opus-Patent-BSD-3-Clause",
    "UnRAR",
    # go/keep-sorted end
])

# TODO(b/388620886): Implement warning when changing _to_ these licenses
# (but not every time the README.chromium file is modified).
WITH_PERMISSION_ONLY = frozenset([
    # restricted.
    "CC-BY-SA-3.0",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL-2.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "NPL-1.1",
    # by_exception_only.
    "Commercial",
    "LicenseRef-Play-Core-SDK-TOS",
    "LicenseRef-Unity-Companion-License-1.3",
    "Opus-Patent-BSD-3-Clause",
    "UnRAR",
])

ALLOWED_LICENSES = ALLOWED_SPDX_LICENSES | EXTENDED_LICENSE_CLASSIFIERS
ALLOWED_OPEN_SOURCE_LICENSES = ALLOWED_LICENSES | OPEN_SOURCE_SPDX_LICENSES
