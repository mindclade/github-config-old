#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for the read-only connected-governance auditor."""

from __future__ import annotations

import importlib.util
import subprocess
import unittest
from datetime import date
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

    def test_release_tag_ruleset_composition_is_audited_exactly(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            {
                "bypass_actors": [
                    {
                        "actor_id": 42,
                        "actor_type": "Team",
                        "bypass_mode": "always",
                    }
                ],
                "conditions": {
                    "ref_name": {"exclude": [], "include": ["refs/tags/v*"]},
                    "repository_name": {"exclude": [], "include": ["~ALL"]},
                },
                "rules": [{"type": "creation"}],
            },
            {
                "bypass_actors": [],
                "conditions": {
                    "ref_name": {"exclude": [], "include": ["refs/tags/v*"]},
                    "repository_name": {"exclude": [], "include": ["~ALL"]},
                },
                "rules": [
                    {"type": "update"},
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                    {
                        "type": "tag_name_pattern",
                        "parameters": {
                            "name": "semver-only",
                            "negate": False,
                            "operator": "regex",
                            "pattern": "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$",
                        },
                    },
                ],
            },
        ]
        AUDIT.audit_release_tag_rulesets(
            api,
            "mindclade",
            [
                {"id": 1, "name": "release-tag-creation"},
                {"id": 2, "name": "tag-protection"},
            ],
            {"release": 42},
            errors,
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            [call.args[0] for call in api.get.call_args_list],
            ["/orgs/mindclade/rulesets/1", "/orgs/mindclade/rulesets/2"],
        )

    def test_release_tag_ruleset_rejects_an_unexpected_bypass_actor(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            {
                "bypass_actors": [
                    {
                        "actor_id": 7,
                        "actor_type": "OrganizationAdmin",
                        "bypass_mode": "always",
                    }
                ],
                "conditions": {
                    "ref_name": {"exclude": [], "include": ["refs/tags/v*"]},
                    "repository_name": {"exclude": [], "include": ["~ALL"]},
                },
                "rules": [{"type": "creation"}],
            },
            {
                "bypass_actors": [],
                "conditions": {
                    "ref_name": {"exclude": [], "include": ["refs/tags/v*"]},
                    "repository_name": {"exclude": [], "include": ["~ALL"]},
                },
                "rules": [
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                    {
                        "parameters": {
                            "name": "semver-only",
                            "negate": False,
                            "operator": "regex",
                            "pattern": "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$",
                        },
                        "type": "tag_name_pattern",
                    },
                    {"type": "update"},
                ],
            },
        ]
        AUDIT.audit_release_tag_rulesets(
            api,
            "mindclade",
            [
                {"id": 1, "name": "release-tag-creation"},
                {"id": 2, "name": "tag-protection"},
            ],
            {"release": 42},
            errors,
        )
        self.assertTrue(
            any("release-tag-creation bypass actors" in error for error in errors)
        )

    def test_partial_paginated_evidence_is_rejected(self) -> None:
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.object_items({"total_count": 2, "repositories": [{"name": "one"}]}, "repositories")

    def test_release_tag_inventory_accepts_only_semver(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            [
                {"name": "v3.0.0"},
                {"name": "v5.0.0-rc.1"},
            ],
            [{"name": "rescue/pre-rebase"}],
        ]

        inventory = AUDIT.audit_repository_tags(
            api,
            "mindclade",
            {"alpha": {}, "beta": {}},
            errors,
        )

        self.assertEqual(
            inventory,
            {
                "alpha": ["v3.0.0", "v5.0.0-rc.1"],
                "beta": ["rescue/pre-rebase"],
            },
        )
        self.assertEqual(
            errors,
            [
                "beta: non-SemVer tag 'rescue/pre-rebase' is forbidden; integrate or "
                "remove rescue, reconcile, backup, and temporary refs"
            ],
        )

    def test_exact_unexpired_rescue_tag_exception_is_accepted(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            [{"name": "rescue/uncommitted-work-20260820"}],
            {"object": {"sha": "2ad2af73670fa993fd00c2208a30bd84a5fe8f88"}},
        ]
        exceptions = {
            "tag_refs": [
                {
                    "repository": "monorepo",
                    "ref": "refs/tags/rescue/uncommitted-work-20260820",
                    "object_sha": "2ad2af73670fa993fd00c2208a30bd84a5fe8f88",
                    "expires_on": "2026-09-21",
                }
            ]
        }

        AUDIT.audit_repository_tags(
            api,
            "mindclade",
            {"monorepo": {}},
            errors,
            exceptions,
            date(2026, 8, 22),
        )
        self.assertEqual(errors, [])

    def test_rescue_tag_exception_rejects_movement_and_expiry(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            [{"name": "rescue/uncommitted-work-20260820"}],
            {"object": {"sha": "f" * 40}},
        ]
        exceptions = {
            "tag_refs": [
                {
                    "repository": "monorepo",
                    "ref": "refs/tags/rescue/uncommitted-work-20260820",
                    "object_sha": "2ad2af73670fa993fd00c2208a30bd84a5fe8f88",
                    "expires_on": "2026-09-21",
                }
            ]
        }

        AUDIT.audit_repository_tags(
            api,
            "mindclade",
            {"monorepo": {}},
            errors,
            exceptions,
            date(2026, 9, 22),
        )
        self.assertTrue(any("expired on 2026-09-21" in error for error in errors))
        self.assertTrue(any("temporary tag" in error and "object" in error for error in errors))

    def test_declared_rescue_tag_must_remain_observable_until_disposed(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.return_value = []
        exceptions = {
            "tag_refs": [
                {
                    "repository": "monorepo",
                    "ref": "refs/tags/rescue/required",
                    "object_sha": "a" * 40,
                    "expires_on": "2026-09-21",
                }
            ]
        }
        AUDIT.audit_repository_tags(
            api,
            "mindclade",
            {"monorepo": {}},
            errors,
            exceptions,
            date(2026, 8, 22),
        )
        self.assertEqual(
            errors,
            ["temporary tag exception was not observed: monorepo refs/tags/rescue/required"],
        )

    def test_release_tag_inventory_paginates_without_truncation(self) -> None:
        api = mock.Mock()
        api.get.side_effect = [
            [{"name": f"v1.0.{patch}"} for patch in range(100)],
            [{"name": "v2.0.0"}],
        ]
        inventory = AUDIT.audit_repository_tags(
            api, "mindclade", {"alpha": {}}, []
        )
        self.assertEqual(len(inventory["alpha"]), 101)
        self.assertEqual(
            [call.args[0] for call in api.get.call_args_list],
            [
                "/repos/mindclade/alpha/tags?per_page=100&page=1",
                "/repos/mindclade/alpha/tags?per_page=100&page=2",
            ],
        )

    def test_release_tag_inventory_rejects_a_repeated_page(self) -> None:
        api = mock.Mock()
        first_page = [{"name": f"v1.0.{patch}"} for patch in range(100)]
        api.get.side_effect = [first_page, first_page]
        with self.assertRaisesRegex(AUDIT.AuditError, "repeated tag"):
            AUDIT.audit_repository_tags(api, "mindclade", {"alpha": {}}, [])

    def test_api_timeout_is_a_fail_fast_transport_error(self) -> None:
        with mock.patch.object(
            AUDIT.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["gh", "api"], 20),
        ):
            with self.assertRaises(AUDIT.AuditTransportError):
                AUDIT.GitHubApi().get("/orgs/mindclade")

    def test_platform_managed_copilot_environment_must_remain_empty(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            {"total_count": 1, "environments": [{"name": "copilot"}]},
            {
                "name": "copilot",
                "protection_rules": [],
                "wait_timer": 0,
                "prevent_self_review": False,
            },
            {"total_count": 0, "secrets": []},
            {"total_count": 0, "variables": []},
        ]
        exceptions = {
            "repository_environments": [
                {
                    "repository": "alpha",
                    "name": "copilot",
                    "allowed_protection_rules": 0,
                    "allowed_secrets": 0,
                    "allowed_variables": 0,
                }
            ]
        }
        AUDIT.audit_environments(
            api,
            "mindclade",
            {"alpha": {"environments": []}},
            {},
            {},
            errors,
            exceptions,
        )
        self.assertEqual(errors, [])

    def test_platform_managed_copilot_environment_rejects_authority(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.side_effect = [
            {"total_count": 1, "environments": [{"name": "copilot"}]},
            {
                "name": "copilot",
                "protection_rules": [{"type": "required_reviewers"}],
                "wait_timer": 0,
                "prevent_self_review": False,
            },
            {"total_count": 1, "secrets": [{"name": "TOKEN"}]},
            {"total_count": 0, "variables": []},
        ]
        exceptions = {
            "repository_environments": [
                {
                    "repository": "alpha",
                    "name": "copilot",
                    "allowed_protection_rules": 0,
                    "allowed_secrets": 0,
                    "allowed_variables": 0,
                }
            ]
        }
        AUDIT.audit_environments(
            api,
            "mindclade",
            {"alpha": {"environments": []}},
            {},
            {},
            errors,
            exceptions,
        )
        self.assertTrue(any("platform protection rules" in error for error in errors))
        self.assertTrue(any("platform secrets" in error for error in errors))


    def test_member_repository_ceiling_is_audited(self) -> None:
        errors: list[str] = []
        api = mock.Mock()
        api.get.return_value = {
            "login": "mindclade",
            "default_repository_permission": "none",
            "members_can_create_repositories": False,
            "members_can_create_public_repositories": False,
            "members_can_create_private_repositories": False,
            "members_can_create_internal_repositories": False,
            "members_can_fork_private_repositories": False,
            "members_can_delete_repositories": True,
            "members_can_change_repo_visibility": True,
            "members_can_create_pages": False,
            "members_can_create_public_pages": False,
            "members_can_create_private_pages": False,
            "web_commit_signoff_required": True,
        }
        AUDIT.audit_organization(api, "mindclade", None, errors)
        self.assertEqual(
            errors,
            [
                "organization members_can_delete_repositories: expected False, got True",
                "organization members_can_change_repo_visibility: expected False, got True",
            ],
        )


if __name__ == "__main__":
    unittest.main()
