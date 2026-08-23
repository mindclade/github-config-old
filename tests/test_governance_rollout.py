#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for exact governance rollout phases."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "governance_rollout", ROOT / "scripts/governance-rollout.py"
)
assert SPEC is not None and SPEC.loader is not None
ROLLOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROLLOUT)


class GovernanceRolloutTest(unittest.TestCase):
    EVIDENCE_EXPECTATIONS = {
        "positive_pull_request": ("pull_request", "success"),
        "positive_merge_group": ("merge_group", "success"),
        "intentional_negative_merge_group": ("merge_group", "failure"),
        "permanent_ruleset_audit": ("workflow_dispatch", "success"),
    }

    def setUp(self) -> None:
        self.readiness = yaml.safe_load(
            (ROOT / "catalog/merge-queue-readiness.yaml").read_text(
                encoding="utf-8"
            )
        )

    def contract(self, repository: str) -> dict[str, object]:
        return next(
            item
            for item in self.readiness["rollout_order"]
            if item["repository"] == repository
        )

    def evidence(
        self, repository: str, field: str, index: int
    ) -> dict[str, object]:
        event_name, conclusion = self.EVIDENCE_EXPECTATIONS[field]
        run_repository = (
            "github-config" if field == "permanent_ruleset_audit" else repository
        )
        digit = format(index, "x")
        return {
            "run_url": (
                f"https://github.com/mindclade/{run_repository}/actions/runs/{index}"
            ),
            "head_sha": digit * 40,
            "base_sha": format(index + 4, "x") * 40,
            "subject_repository": repository,
            "evidence_role": field,
            "event_name": event_name,
            "conclusion": conclusion,
            "observed_at": f"2026-08-23T12:00:0{index}Z",
            "reviewer": "independent-reviewer",
            "restricted_snapshot_uri": (
                f"gs://restricted/queue/{repository}-{field}.json#{index}"
            ),
            "sha256": "sha256:" + digit * 64,
        }

    def set_canary_active(self, repository: str) -> None:
        self.contract(repository)["status"] = "canary_active"

    def set_canary_passed(self, repository: str) -> None:
        contract = self.contract(repository)
        contract["status"] = "canary_passed"
        contract["blocker"] = None
        for index, field in enumerate(ROLLOUT.MERGE_QUEUE_EVIDENCE_FIELDS[:3], 1):
            contract["evidence"][field] = self.evidence(repository, field, index)

    def set_qualified(self, repository: str) -> None:
        contract = self.contract(repository)
        contract["status"] = "qualified"
        contract["blocker"] = None
        for index, field in enumerate(ROLLOUT.MERGE_QUEUE_EVIDENCE_FIELDS, 1):
            contract["evidence"][field] = self.evidence(repository, field, index)

    def test_normal_holds_every_unqualified_queue_and_check_in_evaluate(self) -> None:
        bundle = ROLLOUT.bundle_for_rollout("normal", readiness=self.readiness)
        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"],
            {repository: "evaluate" for repository in ROLLOUT.ROLLOUT_REPOSITORIES},
        )
        expected_rulesets = {
            ruleset
            for repository in ROLLOUT.ROLLOUT_REPOSITORIES
            for ruleset in ROLLOUT.REPOSITORY_RULESETS[repository]
        }
        self.assertEqual(
            set(bundle["ruleset_enforcement_overrides"]), expected_rulesets
        )
        self.assertEqual(set(bundle["ruleset_enforcement_overrides"].values()), {"evaluate"})
        self.assertEqual(bundle["merge_queue_canary_required_checks"], {})

    def test_first_adoption_is_evaluate_only(self) -> None:
        bundle = ROLLOUT.bundle_for_rollout(
            "adopt-evaluate", readiness=self.readiness
        )
        self.assertTrue(
            set(ROLLOUT.ACTIVE_BRANCH_RULESETS).issubset(
                bundle["ruleset_enforcement_overrides"]
            )
        )
        self.assertEqual(set(bundle["ruleset_enforcement_overrides"].values()), {"evaluate"})
        self.assertEqual(
            set(bundle["merge_queue_repository_enforcement_overrides"].values()),
            {"evaluate"},
        )

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
        bundle = ROLLOUT.bundle_for_rollout(
            "promote-core", readiness=self.readiness
        )
        active = {
            name
            for name, value in bundle["ruleset_enforcement_overrides"].items()
            if value == "active"
        }
        self.assertEqual(active, {"baseline-all", "protected-paths"})
        self.assertEqual(
            set(bundle["merge_queue_repository_enforcement_overrides"].values()),
            {"evaluate"},
        )

    def test_canary_activates_one_queue_with_only_temporary_exact_checks(self) -> None:
        self.set_canary_active("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout(
            "merge-queue",
            repository="mindclade-internal-monorepo",
            stage="canary",
            readiness=self.readiness,
        )
        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"][
                "mindclade-internal-monorepo"
            ],
            "active",
        )
        self.assertEqual(
            bundle["merge_queue_canary_required_checks"],
            {
                "mindclade-internal-monorepo": list(
                    ROLLOUT.REPOSITORY_CONTEXTS["mindclade-internal-monorepo"]
                )
            },
        )
        self.assertEqual(
            {
                bundle["ruleset_enforcement_overrides"][name]
                for name in ROLLOUT.REPOSITORY_RULESETS[
                    "mindclade-internal-monorepo"
                ]
            },
            {"evaluate"},
        )

    def test_normal_preserves_active_canary_before_evidence_is_complete(self) -> None:
        self.set_canary_active("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout("normal", readiness=self.readiness)

        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"][
                "mindclade-internal-monorepo"
            ],
            "active",
        )
        self.assertIn(
            "mindclade-internal-monorepo",
            bundle["merge_queue_canary_required_checks"],
        )

    def test_promote_retains_canary_checks_and_activates_permanent_rules(self) -> None:
        self.set_canary_passed("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout(
            "merge-queue",
            repository="mindclade-internal-monorepo",
            stage="promote",
            readiness=self.readiness,
        )
        self.assertIn(
            "mindclade-internal-monorepo",
            bundle["merge_queue_canary_required_checks"],
        )
        self.assertEqual(
            {
                bundle["ruleset_enforcement_overrides"][name]
                for name in ROLLOUT.REPOSITORY_RULESETS[
                    "mindclade-internal-monorepo"
                ]
            },
            {"active"},
        )

    def test_normal_preserves_canary_after_evidence_is_committed(self) -> None:
        self.set_canary_passed("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout("normal", readiness=self.readiness)
        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"][
                "mindclade-internal-monorepo"
            ],
            "active",
        )
        self.assertIn(
            "mindclade-internal-monorepo",
            bundle["merge_queue_canary_required_checks"],
        )
        self.assertEqual(
            {
                bundle["ruleset_enforcement_overrides"][name]
                for name in ROLLOUT.REPOSITORY_RULESETS[
                    "mindclade-internal-monorepo"
                ]
            },
            {"evaluate"},
        )

    def test_finalize_removes_temporary_checks_only_after_qualification(self) -> None:
        self.set_qualified("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout(
            "merge-queue",
            repository="mindclade-internal-monorepo",
            stage="finalize",
            readiness=self.readiness,
        )
        self.assertEqual(bundle["merge_queue_canary_required_checks"], {})
        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"][
                "mindclade-internal-monorepo"
            ],
            "active",
        )

    def test_rollback_deactivates_queue_and_checks_without_weakening_other_repositories(self) -> None:
        self.set_canary_passed("mindclade-internal-monorepo")
        bundle = ROLLOUT.bundle_for_rollout(
            "merge-queue",
            repository="mindclade-internal-monorepo",
            stage="rollback",
            readiness=self.readiness,
        )

        self.assertEqual(
            bundle["merge_queue_repository_enforcement_overrides"][
                "mindclade-internal-monorepo"
            ],
            "evaluate",
        )
        self.assertNotIn(
            "mindclade-internal-monorepo",
            bundle["merge_queue_canary_required_checks"],
        )
        self.assertEqual(
            {
                bundle["ruleset_enforcement_overrides"][name]
                for name in ROLLOUT.REPOSITORY_RULESETS[
                    "mindclade-internal-monorepo"
                ]
            },
            {"evaluate"},
        )

    def test_later_repository_cannot_advance_before_predecessor(self) -> None:
        self.set_canary_active("gitops")
        with self.assertRaisesRegex(ValueError, "only the first unqualified"):
            ROLLOUT.bundle_for_rollout(
                "merge-queue",
                repository="gitops",
                stage="canary",
                readiness=self.readiness,
            )

    def test_stage_must_match_catalog_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires status canary_passed"):
            ROLLOUT.bundle_for_rollout(
                "merge-queue",
                repository="mindclade-internal-monorepo",
                stage="promote",
                readiness=self.readiness,
            )

    def test_non_queue_phase_rejects_queue_arguments(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid only for phase merge-queue"):
            ROLLOUT.bundle_for_rollout(
                "normal",
                repository="mindclade-internal-monorepo",
                stage="canary",
                readiness=self.readiness,
            )

    def test_legacy_phases_cannot_deactivate_an_advanced_queue(self) -> None:
        self.set_canary_active("mindclade-internal-monorepo")
        for phase in ("adopt-evaluate", "promote-core"):
            with self.subTest(phase=phase):
                with self.assertRaisesRegex(ValueError, "cannot run after"):
                    ROLLOUT.bundle_for_rollout(
                        phase, readiness=self.readiness
                    )

    def test_explicit_empty_readiness_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid merge-queue readiness schema"):
            ROLLOUT.bundle_for_rollout("normal", readiness={})

    def test_unknown_phase_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown rollout phase"):
            ROLLOUT.bundle_for_rollout(
                "activate-everything", readiness=deepcopy(self.readiness)
            )


if __name__ == "__main__":
    unittest.main()
