#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Validate governance ownership of the applied bootstrap account handoff."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from terraform_contracts import (
    TerraformContractError,
    validate_bootstrap_account_handoff_ci_variable_contract,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCHEMA_ID = (
    "https://schemas.mindclade.internal/infrastructure/"
    "bootstrap-account-handoff.schema.json"
)
EXPECTED_SCHEMA_SHA256 = (
    "79615285b9bf25461bf483cbc0164a79204119343e421b6ecaf061101eb93e03"
)
EXPECTED_FIELDS = {
    "schema_version",
    "bootstrap_contract_version",
    "bootstrap_source_commit",
    "platform_contract_sha256",
    "state_location",
    "state_buckets",
    "service_accounts",
}


def contract_errors(root: Path = ROOT) -> list[str]:
    """Return stable, non-secret contract errors for local and CI use."""

    errors: list[str] = []
    try:
        schema_bytes = (
            root / "contracts/bootstrap-account-handoff.schema.json"
        ).read_bytes()
        schema = json.loads(schema_bytes)
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError):
        return ["[ACCOUNT-HANDOFF-CONTRACT] handoff schema is unavailable"]

    if (
        hashlib.sha256(schema_bytes).hexdigest() != EXPECTED_SCHEMA_SHA256
        or schema.get("$id") != EXPECTED_SCHEMA_ID
        or schema.get("additionalProperties") is not False
        or set(schema.get("required", [])) != EXPECTED_FIELDS
        or schema.get("properties", {}).get("schema_version", {}).get("const") != 1
        or schema.get("properties", {})
        .get("bootstrap_contract_version", {})
        .get("const")
        != "1.5.0"
    ):
        errors.append(
            "[ACCOUNT-HANDOFF-CONTRACT] handoff schema authority or field inventory differs"
        )

    try:
        catalog = yaml.safe_load(
            (root / "catalog/ci-variables.yaml").read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError):
        errors.append("[ACCOUNT-HANDOFF-CATALOG] CI-variable catalog is unreadable")
    else:
        if not isinstance(catalog, dict):
            errors.append("[ACCOUNT-HANDOFF-CATALOG] CI-variable catalog is not an object")
        elif "BOOTSTRAP_ACCOUNT_HANDOFF_JSON" in catalog.get(
            "infrastructure-live", {}
        ):
            errors.append(
                "[ACCOUNT-HANDOFF-CATALOG] handoff must not be a free-form catalog input"
            )

    try:
        validate_bootstrap_account_handoff_ci_variable_contract(root)
    except TerraformContractError:
        errors.append(
            "[ACCOUNT-HANDOFF-TERRAFORM] protected repository-variable binding differs"
        )
    return errors


def main() -> int:
    errors = contract_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("bootstrap account handoff governance contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
