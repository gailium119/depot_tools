#!/usr/bin/env python3
# Copyright 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from typing import List, Optional, Tuple

import metadata.fields.field_types as field_types
import metadata.fields.util as util
import metadata.validation_result as vr

# List of supported vulnerability ID prefixes.
_VULN_PREFIXES = [
    "CVE",  # Common Vulnerabilities and Exposures.
    "GHSA",  # GitHub Security Advisory.
    "PYSEC",  # Python Security Advisory.
    "OSV",  # Open Source Vulnerability.
    "DSA",  # Debian Security Advisory.
]

_PREFIX_PATTERN = "|".join(_VULN_PREFIXES)
VULN_ID_PATTERN = re.compile(
    rf"({_PREFIX_PATTERN})-[a-zA-Z0-9]{{4}}-[a-zA-Z0-9:-]+")
VULN_ID_PATTERN_WITH_ANCHORS = re.compile(f"^{VULN_ID_PATTERN.pattern}$")


def validate_vuln_ids(cves: str) -> Tuple[List[str], List[str]]:
    """
    Validates a list of vulnerability identifiers and returns valid and invalid IDs.

    Supports multiple formats:
    - CVE IDs (e.g., CVE-2024-12345)
    - GitHub Security Advisories (e.g., GHSA-1234-5678-90ab)
    - Python Security Advisories (e.g., PYSEC-2024-1234)
    - Open Source Vulnerabilities (e.g., OSV-2024-1234)
    - Debian Security Advisories (e.g., DSA-1234-1)

    Args:
        vuln_ids: List of vulnerability identifiers to validate

    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    valid_cves = []
    invalid_cves = []

    for cve in cves.split(","):
        cve_stripped = cve.strip()
        if VULN_ID_PATTERN_WITH_ANCHORS.match(cve_stripped):
            valid_cves.append(cve_stripped)
        else:
            invalid_cves.append(cve)

    return valid_cves, invalid_cves


class MitigatedField(field_types.SingleLineTextField):
    """Field for comma-separated vulnerability IDs."""

    def __init__(self):
        super().__init__(name="Mitigated")

    def validate(self, value: str) -> Optional[vr.ValidationResult]:
        """Checks if the value contains valid CVE IDs."""
        if util.is_empty(value):
            return None
        _, invalid_cves = validate_vuln_ids(value)

        if invalid_cves:
            return vr.ValidationWarning(
                reason=f"{self._name} contains invalid vulnerability IDs.",
                additional=[
                    f"Invalid Vulnerability IDs: {util.quoted(invalid_cves)}",
                    "The following identifiers are supported:\n * " +
                    "\n * ".join(_VULN_PREFIXES)
                ])

        return None

    def narrow_type(self, value: str) -> Optional[List[str]]:
        if not value:
            return None
        cves, _ = validate_vuln_ids(value)
        return cves
