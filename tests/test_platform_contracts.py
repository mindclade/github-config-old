#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

from __future__ import annotations

from copy import deepcopy
from datetime import date
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACTS = load("platform_contracts", "scripts/platform_contracts.py")
ACTIVATION_TOOL = load(
    "prepare_workflow_activation", "scripts/prepare-workflow-activation.py"
)
UPGRADE = load("upgrade_workflow_pins", "scripts/upgrade-workflow-pins.py")


class PlatformContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = CONTRACTS.load_yaml(ROOT / "catalog/workflow-adoption.yaml")
        self.activation = CONTRACTS.load_yaml(
            ROOT / "catalog/governance-activation.yaml"
        )
        self.evidence = CONTRACTS.load_yaml(
            ROOT / "catalog/connected-qualification-evidence.yaml"
        )

    def test_checked_in_graph_and_blocked_evidence_are_valid(self) -> None:
        self.assertEqual(
            CONTRACTS.workflow_adoption_errors(
                self.graph, self.activation, repository_root=ROOT
            ),
            [],
        )
        self.assertEqual(
            CONTRACTS.connected_evidence_errors(
                self.evidence, self.activation, today=date(2026, 8, 23)
            ),
            [],
        )

    def test_permission_mutation_fails_closed(self) -> None:
        mutated = deepcopy(self.graph)
        mutated["workflows"]["reusable-nix-qualification"][
            "required_permissions"
        ]["contents"] = "write"
        errors = CONTRACTS.workflow_adoption_errors(mutated, self.activation)
        self.assertTrue(any("least-privilege exact" in error for error in errors))

    def test_consumer_pin_mutation_fails_closed(self) -> None:
        mutated = deepcopy(self.graph)
        mutated["workflows"]["reusable-nix-qualification"]["consumers"][1][
            "current_reference"
        ] = "0" * 40
        errors = CONTRACTS.workflow_adoption_errors(
            mutated, self.activation, repository_root=ROOT
        )
        self.assertTrue(any("reference differs" in error for error in errors))

    def test_producer_workflow_identity_mutation_fails_closed(self) -> None:
        mutated = deepcopy(self.graph)
        mutated["workflows"]["reusable-nix-qualification"][
            "implementation"
        ] = ".github/workflows/reusable-repo-hygiene.yml"
        errors = CONTRACTS.workflow_adoption_errors(mutated, self.activation)
        self.assertTrue(any("implementation path is not exact" in error for error in errors))

    def test_qualified_gate_without_evidence_fails_closed(self) -> None:
        mutated = deepcopy(self.activation)
        mutated["gates"]["v5_release_published"] = "qualified"
        errors = CONTRACTS.connected_evidence_errors(
            self.evidence, mutated, today=date(2026, 8, 23)
        )
        self.assertIn(
            "qualified gate lacks fresh connected evidence: v5_release_published",
            errors,
        )

    def test_dr_activation_and_pin_upgrade_remain_blocked(self) -> None:
        self.assertTrue(
            any(
                "v5 release is not published" in error
                for error in ACTIVATION_TOOL.activation_errors(
                    self.graph, self.evidence, self.activation
                )
            )
        )
        self.assertTrue(
            any(
                "v5 producer release is not published" in error
                for error in UPGRADE.qualified_upgrade_errors(
                    self.graph, self.evidence, self.activation
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
