#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for the read-only connected-governance auditor."""

from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_connected_governance", ROOT / "scripts/audit-connected-governance.py"
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ConnectedGovernanceTest(unittest.TestCase):
    def test_plan_app_permission_exception_is_not_hidden(self) -> None:
        contract = AUDIT.load_yaml(ROOT / "catalog/control-plane-apps.yaml")
        plan = contract["apps"]["mindclade-github-config-plan"]
        self.assertFalse(plan["permission_nonmutating"])
        self.assertEqual(
            plan["organization_permissions"]["organization_administration"],
            "write",
        )
        self.assertIn("rulesets", plan["permission_exception"])

    def test_runtime_app_permission_names_match_api(self) -> None:
        apps = AUDIT.runtime_app_contracts(
            {
                "arc": {
                    "repositories": ["monorepo"],
                    "organizationPermissions": {"selfHostedRunners": "write"},
                    "repositoryPermissions": {"pullRequests": "write", "metadata": "read"},
                }
            }
        )
        self.assertEqual(
            apps["arc"]["permissions"],
            {
                "organization_self_hosted_runners": "write",
                "pull_requests": "write",
                "metadata": "read",
            },
        )

    def test_merge_queue_scope_is_compiled_from_repository_classes(self) -> None:
        rulesets = {"merge-queue": {"classes": ["production"], "enforcement": "active"}}
        repositories = {
            "included": {"repository_class": "production"},
            "excluded": {"repository_class": "source"},
        }
        organization, repository = AUDIT.expected_rulesets(rulesets, repositories)
        self.assertEqual(organization, {})
        self.assertEqual(repository["excluded"], {})
        self.assertEqual(repository["included"]["merge-queue"]["target"], "branch")

    def test_partial_paginated_evidence_is_rejected(self) -> None:
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.object_items({"total_count": 2, "repositories": [{"name": "one"}]}, "repositories")

    def test_api_timeout_is_a_fail_fast_transport_error(self) -> None:
        with mock.patch.object(
            AUDIT.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["gh", "api"], 20),
        ):
            with self.assertRaises(AUDIT.AuditTransportError):
                AUDIT.GitHubApi().get("/orgs/mindclade")


if __name__ == "__main__":
    unittest.main()
