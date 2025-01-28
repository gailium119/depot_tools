#!/usr/bin/env python3
# Copyright 2023 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from typing import List, Optional

import metadata.fields.field_types as field_types
import metadata.fields.util as util
import metadata.validation_result as vr

# Pattern to validate CVE IDs
_CVE_PATTERN = re.compile(r'^CVE-\d{4}-\d{4,7}$')

def is_cve_valid(value: str) -> bool:
    """Returns whether the value is a valid CVE ID."""
    return bool(_CVE_PATTERN.match(value.strip()))

class MitigatedField(field_types.FreeformTextField):
    """Field for comma-separated CVE IDs. Supports multiline values."""

    def __init__(self):
        super().__init__(name="Mitigated")

    def validate(self, value: str) -> Optional[vr.ValidationResult]:
        """Checks if the value contains valid CVE IDs."""
        if util.is_empty(value):
            return None
        # Handle potential multiline input
        invalid_cves = []
        cves = []
        for line in value.splitlines():
            if line[-1] == self.VALUE_DELIMITER:
                line = line[:-1]
            cves += [cve.strip() for cve in line.split(self.VALUE_DELIMITER)]

        for cve in cves:
            if util.is_empty(cve):
                return vr.ValidationWarning(reason=f"{self._name} has an empty value.")
            if not is_cve_valid(cve):
                invalid_cves.append(cve)

        if invalid_cves:
            return vr.ValidationWarning(
                reason=f"{self._name} contains invalid CVE IDs.",
                additional=[
                    f"Invalid CVE IDs: {util.quoted(invalid_cves)}",
                    "CVE IDs must match pattern: CVE-YYYY-NNNN"
                ])

        return None

    def narrow_type(self, value: str) -> Optional[List[str]]:
        if not value:
            return None
        return [cve.strip() for cve in value.split(self.VALUE_DELIMITER)]


        for cve in cves:
            if not cve:
                continue
            if not self._cve_pattern.match(cve):
                invalid_cves.append(cve)

        if invalid_cves:
            return vr.ValidationError(
                reason=f"{self._name} contains invalid CVE IDs.",
                additional=[
                    f"Invalid CVE IDs: {util.quoted(invalid_cves)}",
                    "CVE IDs must match pattern: CVE-YYYY-NNNN"
                ])

        return None

    def narrow_type(self, value: str) -> Optional[List[str]]:
        if not value:
            return None
        # Handle multiline and return normalized list
        value = ' '.join(line.strip() for line in value.splitlines())
        return [cve.strip() for cve in value.split(self.VALUE_DELIMITER) if cve.strip()]