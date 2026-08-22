#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for exact governance rollout phases."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "governance_rollout", ROOT / "scripts/governance-rollout.py"
)
assert SPEC is not None and SPEC.loader is not None
ROLLOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROLLOUT)


class GovernanceRolloutTest(unittest.TestCase):
    def test_normal_uses_resting_catalog(self) -> None:
        self.assertEqual(ROLLOUT.overrides_for_phase("normal"), {})

    def test_first_adoption_is_evaluate_only(self) -> None:
        overrides = ROLLOUT.overrides_for_phase("adopt-evaluate")
        self.assertEqual(set(overrides), set(ROLLOUT.ACTIVE_BRANCH_RULESETS))
        self.assertEqual(set(overrides.values()), {"evaluate"})

    def test_phase_inventory_matches_active_branch_catalog(self) -> None:
        rulesets = yaml.safe_load(
            (ROOT / "catalog/rulesets.yaml").read_text(encoding="utf-8")
        )
        tag_or_push = {"push-blocklist", "release-tag-creation", "tag-protection"}
        expected = {
            name
            for name, config in rulesets.items()
            if config.get("enforcement") == "active" and name not in tag_or_push
        }
        self.assertEqual(set(ROLLOUT.ACTIVE_BRANCH_RULESETS), expected)

    def test_core_promotion_activates_only_baseline_and_protected_paths(self) -> None:
        overrides = ROLLOUT.overrides_for_phase("promote-core")
        self.assertEqual(
            {name for name, value in overrides.items() if value == "active"},
            {"baseline-all", "protected-paths"},
        )
        self.assertEqual(
            {name for name, value in overrides.items() if value == "evaluate"},
            set(ROLLOUT.ACTIVE_BRANCH_RULESETS) - ROLLOUT.CORE_RULESETS,
        )

    def test_unknown_phase_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown rollout phase"):
            ROLLOUT.overrides_for_phase("activate-everything")


if __name__ == "__main__":
    unittest.main()
