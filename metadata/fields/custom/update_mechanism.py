#!/usr/bin/env python3
# Copyright 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from typing import Optional, Tuple

import metadata.fields.field_types as field_types
import metadata.fields.util as util
import metadata.validation_result as vr

# The regex for validating the structure of the Update-Mechanism field.
# It captures three groups:
# 1. The primary mechanism (e.g., "Autoroll", "Manual", "Static").
# 2. An optional secondary part, preceded by a dot (e.g., ".HardFork").
# 3. An optional comment/bug link in parentheses (e.g., "(crbug.com/12345)").
UPDATE_MECHANISM_REGEX = re.compile(
    r"^([^.\s(]+)(?:\.([^\s(]+))?(?:\s*\(([^)]+)\))?$")

# A set of the fully-qualified, allowed mechanism values.
ALLOWED_MECHANISMS = {
    "Autoroll",
    "Manual",
    "Static",
    "Static.HardFork",
}


def parse_update_mechanism(value: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses the Update-Mechanism field value using a regular expression.

    Args:
        value: The string value of the Update-Mechanism field.

    Returns:
        A tuple (full_mechanism, comment).
        If the value's structure is valid, the captured parts are returned.
        `full_mechanism` is the combined primary and secondary parts. `comment` can be None.
        If the structure is invalid, both elements of the tuple are None.
    """
    match = UPDATE_MECHANISM_REGEX.match(value.strip())
    if not match:
        return None, None

    mechanism, sub_mechanism, comment = match.groups()

    # Construct the full mechanism string, e.g., "Static.HardFork"
    full_mechanism = mechanism
    if sub_mechanism:
        full_mechanism = f"{mechanism}.{sub_mechanism}"

    return full_mechanism, comment


class UpdateMechanismField(field_types.SingleLineTextField):
    """
    Field for 'Update-Mechanism: <Value>'.
    The format is Primary[.SubsetSpecifier] [(crbug.com/BUG_ID)].
    """

    def __init__(self):
        super().__init__(name="Update Mechanism")

    def validate(self, value: str) -> Optional[vr.ValidationResult]:
        """
        Checks if the value is a valid Update-Mechanism entry, including the
        logic for when a bug link is required or disallowed.
        """
        if util.is_empty(value):
            return vr.ValidationError(
                reason=f"{self._name} field cannot be empty.",
                additional=[
                    f"Must be one of {util.quoted(sorted(ALLOWED_MECHANISMS))}.",
                    "Example: 'Autoroll' or 'Manual (crbug.com/12345)'"
                ])

        mechanism, bug_link = parse_update_mechanism(value)

        # First, check if the value matches the general format.
        if mechanism is None:
            return vr.ValidationError(
                reason=f"Invalid format for {self._name} field.",
                additional=[
                    "Expected format: Mechanism[.SubMechanism] [(bug)]",
                    f"Allowed mechanisms: {util.quoted(sorted(ALLOWED_MECHANISMS))}.",
                    "Example: 'Static.HardFork (crbug.com/12345)'",
                ])

        # Second, check if the mechanism is a known, allowed value.
        if mechanism not in ALLOWED_MECHANISMS:
            return vr.ValidationError(
                reason=f"Invalid mechanism '{mechanism}'.",
                additional=[
                    f"Must be one of {util.quoted(sorted(ALLOWED_MECHANISMS))}.",
                ])

        # For all other valid mechanisms, a bug is required.
        elif mechanism != "Autoroll" and bug_link is None:
            return vr.ValidationError(
                reason=f"A bug link is required for '{mechanism}'.",
                additional=[
                    "Please add a bug link in parentheses.",
                    f"Example: '{mechanism}  (crbug.com/12345)'"
                ])

        # The bug link must be for the public tracker.
        elif mechanism != "Autoroll" and 'crbug.com/' not in bug_link:
            return vr.ValidationError(
                reason="Bug links must be of the form crbug.com/111111.",
                additional=[
                    "Please add a bug link using 'crbug.com/' in parentheses.",
                    f"Example: '{mechanism}  (crbug.com/12345)'"
                ])

        return None

    def narrow_type(self, value: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Parses the field value into its components if it is valid.

        Returns:
            A tuple of (full_mechanism, optional_comment) if valid, otherwise None.
        """
        if util.is_empty(value) or self.validate(value):
            # If the value is empty or fails validation, it cannot be narrowed.
            return None

        mechanism, bug_link = parse_update_mechanism(value)
        return mechanism, bug_link
