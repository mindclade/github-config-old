#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for connected-plan change classification."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "classify_plan_change", ROOT / "scripts/classify-plan-change.py"
)
assert SPEC is not None and SPEC.loader is not None
CLASSIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLASSIFIER)


class ClassifyPlanChangeTest(unittest.TestCase):
    def test_docs_only_change_skips_connected_plan(self) -> None:
        self.assertFalse(
            CLASSIFIER.requires_connected_plan(["README.md", "docs/adoption.md"])
        )

    def test_terraform_catalog_and_gate_changes_require_plan(self) -> None:
        for path in (
            "main.tf",
            "modules/rulesets/required-checks-tf.tf",
            ".terraform.lock.hcl",
            "catalog/rulesets.yaml",
            "idp/mappings.yaml",
            ".github/workflows/plan.yml",
            "scripts/classify-plan-change.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(CLASSIFIER.requires_connected_plan([path]))

    def test_draft_closed_and_converted_events_skip_without_diff(self) -> None:
        with mock.patch.object(CLASSIFIER, "changed_paths") as changed:
            self.assertFalse(
                CLASSIFIER.decide("pull_request", "synchronize", "", "", draft=True)
            )
            self.assertFalse(CLASSIFIER.decide("pull_request", "closed", "", ""))
            self.assertFalse(
                CLASSIFIER.decide("pull_request", "converted_to_draft", "", "")
            )
            changed.assert_not_called()

    def test_ready_pull_request_uses_changed_paths(self) -> None:
        with mock.patch.object(
            CLASSIFIER, "changed_paths", return_value=["catalog/rulesets.yaml"]
        ):
            self.assertTrue(
                CLASSIFIER.decide(
                    "pull_request", "ready_for_review", "a" * 40, "b" * 40
                )
            )

    def test_non_pull_request_is_fail_closed_to_connected_plan(self) -> None:
        self.assertTrue(CLASSIFIER.decide("workflow_dispatch", "", "", ""))

    def test_invalid_sha_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "full lowercase commit SHAs"):
            CLASSIFIER.changed_paths("main", "b" * 40)


if __name__ == "__main__":
    unittest.main()
