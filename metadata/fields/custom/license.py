#!/usr/bin/env python3
# Copyright 2023 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import sys
from typing import List, Tuple, Optional

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
# The repo's root directory.
_ROOT_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))

# Add the repo's root directory for clearer imports.
sys.path.insert(0, _ROOT_DIR)

import metadata.fields.field_types as field_types
import metadata.fields.util as util
import metadata.validation_result as vr
from metadata.fields.custom.license_allowlist import ALLOWED_SPDX_LICENSES,ALLOWED_OPEN_SOURCE_LICENSES


def process_license_value(value: str,
                          atomic_delimiter: str,
                          allow_reciprocal_licenses: bool = False) -> List[Tuple[str, bool]]:
    """Process a license field value, which may list multiple licenses.

    Args:
        value: the value to process, which may include both verbose and
               atomic delimiters, e.g. "Apache, 2.0 and MIT and custom"
        atomic_delimiter: the delimiter to use as a final step; values
                          will not be further split after using this
                          delimiter.
        allow_reciprocal_licenses: whether to allow reciprocal licenses.
                            This should only be True for open source projects.

    Returns: a list of the constituent licenses within the given value,
             and whether the constituent license is on the allowlist.
             e.g. [("Apache, 2.0", True), ("MIT", True),
                   ("custom", False)]
    """
    # Check if the value is on the allowlist as-is, and thus does not
    # require further processing.
    if is_license_allowlisted(value, allow_reciprocal_licenses=allow_reciprocal_licenses):
        return [(value, True)]

    breakdown = []
    # Split using the standard value delimiter. This results in
    # atomic values; there is no further splitting possible.
    for atomic_value in value.split(atomic_delimiter):
        atomic_value = atomic_value.strip()
        breakdown.append(
            (atomic_value, is_license_allowlisted(
                atomic_value,
                allow_reciprocal_licenses=allow_reciprocal_licenses,
            ))
        )

    return breakdown


def is_license_allowlisted(value: str, allow_reciprocal_licenses: bool = False) -> bool:
    """Returns whether the value is in the allowlist for license
    types.
    """
    if allow_reciprocal_licenses:
        return value in ALLOWED_OPEN_SOURCE_LICENSES
    return value in ALLOWED_SPDX_LICENSES


class LicenseField(field_types.SingleLineTextField):
  """Custom field for the package's license type(s).

    e.g. Apache 2.0, MIT, BSD, Public Domain.
    """
  def __init__(self):
    super().__init__(name="License")

  def validate(self, value: str,
               allow_reciprocal_licenses: bool = False) -> Optional[vr.ValidationResult]:
    """Checks the given value consists of recognized license types.

        Note: this field supports multiple values.
        """
    not_allowlisted = []
    licenses = process_license_value(value,
          atomic_delimiter=self.VALUE_DELIMITER,
          allow_reciprocal_licenses=allow_reciprocal_licenses,
    )
    for license, allowed in licenses:
      if util.is_empty(license):
        return vr.ValidationError(
                    reason=f"{self._name} has an empty value.")
      if not allowed:
        not_allowlisted.append(license)

    if not_allowlisted:
      return vr.ValidationWarning(
                reason=f"{self._name} has a license not in the allowlist."
                " (see https://source.chromium.org/chromium/chromium/tools/depot_tools/+/main:metadata/fields/custom/license_allowlist.py).",
                additional=[
                    "Licenses not allowlisted: "
                    f"{util.quoted(not_allowlisted)}.",
                ])

    return None

  def narrow_type(self, value: str) -> Optional[List[str]]:
    if not value:
      # Empty License field is equivalent to "not declared".
      return None

    parts = value.split(self.VALUE_DELIMITER)
    return list(filter(bool, map(lambda str: str.strip(), parts)))
