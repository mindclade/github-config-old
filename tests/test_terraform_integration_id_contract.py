#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Regression tests for the GitHub Actions integration-id Terraform contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "terraform_integration_id_contracts",
    ROOT / "scripts/terraform_contracts.py",
)
assert SPEC is not None and SPEC.loader is not None
TERRAFORM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TERRAFORM
SPEC.loader.exec_module(TERRAFORM)


class GitHubActionsIntegrationIdContractTest(unittest.TestCase):
    def test_current_literal_is_accepted(self) -> None:
        TERRAFORM.validate_github_actions_integration_id(ROOT)

    def test_nonliteral_or_wrong_values_are_rejected(self) -> None:
        source = (ROOT / "modules/rulesets/locals.tf").read_text(encoding="utf-8")
        for replacement in (
            '"15368"',
            "15368.0",
            'tonumber("15368")',
            "15369",
            "local.expected_integration_id # github_actions_integration_id = 15368",
        ):
            with self.subTest(replacement=replacement):
                mutated, replacements = re.subn(
                    r"github_actions_integration_id\s*=\s*15368",
                    f"github_actions_integration_id = {replacement}",
                    source,
                    count=1,
                )
                self.assertEqual(replacements, 1)
                with tempfile.TemporaryDirectory() as directory:
                    temporary_root = Path(directory)
                    target = temporary_root / "modules/rulesets/locals.tf"
                    target.parent.mkdir(parents=True)
                    target.write_text(mutated, encoding="utf-8")
                    with self.assertRaisesRegex(
                        TERRAFORM.TerraformContractError,
                        "must be the literal integer 15368",
                    ):
                        TERRAFORM.validate_github_actions_integration_id(temporary_root)


if __name__ == "__main__":
    unittest.main()
