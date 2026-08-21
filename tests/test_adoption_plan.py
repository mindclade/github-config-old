#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Tests for GitHub Terraform adoption safety gates."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_adoption_plan", ROOT / "scripts/validate-adoption-plan.py"
)
assert SPEC is not None and SPEC.loader is not None
ADOPTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADOPTION)


class AdoptionPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = {
            "qualification": "blocked",
            "unresolved_discovery": [{"resource_class": "state", "reason": "not read"}],
            "known_existing": [
                {
                    "kind": "repository",
                    "name": "github-config",
                    "terraform_address": 'module.repositories.github_repository.this["github-config"]',
                    "import_id": "github-config",
                }
            ],
        }
        self.address = self.inventory["known_existing"][0]["terraform_address"]

    def test_known_existing_create_is_rejected(self) -> None:
        plan = {
            "resource_changes": [
                {"address": self.address, "change": {"actions": ["create"]}}
            ]
        }
        errors = ADOPTION.plan_errors(self.inventory, plan, set())
        self.assertTrue(any("created instead of imported" in error for error in errors))

    def test_exact_import_satisfies_adoption(self) -> None:
        plan = {
            "resource_changes": [
                {
                    "address": self.address,
                    "change": {
                        "actions": ["no-op"],
                        "importing": {"id": "github-config"},
                    },
                }
            ]
        }
        self.assertEqual(ADOPTION.plan_errors(self.inventory, plan, set()), [])

    def test_wrong_import_id_is_rejected(self) -> None:
        plan = {
            "resource_changes": [
                {
                    "address": self.address,
                    "change": {
                        "actions": ["no-op"],
                        "importing": {"id": "different-repository"},
                    },
                }
            ]
        }
        self.assertTrue(
            any("expected immutable ID" in error for error in ADOPTION.plan_errors(self.inventory, plan, set()))
        )

    def test_delete_is_rejected_without_override(self) -> None:
        plan = {
            "resource_changes": [
                {"address": "module.anything", "change": {"actions": ["delete"]}}
            ]
        }
        errors = ADOPTION.plan_errors(self.inventory, plan, {self.address})
        self.assertTrue(any("destructive action" in error for error in errors))

    def test_state_address_with_wrong_immutable_id_is_rejected(self) -> None:
        plan = {
            "prior_state": {
                "values": {
                    "root_module": {
                        "child_modules": [
                            {
                                "resources": [
                                    {
                                        "address": self.address,
                                        "values": {"id": "wrong"},
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        errors = ADOPTION.plan_errors(self.inventory, plan, {self.address})
        self.assertTrue(any("state identity" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
