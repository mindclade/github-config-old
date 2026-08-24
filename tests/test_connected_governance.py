#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Unit tests for the read-only connected-governance auditor."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "audit_connected_governance", ROOT / "scripts/audit-connected-governance.py"
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ConnectedGovernanceTest(unittest.TestCase):
    TEAM_IDS = {"platform": 101, "security": 202}

    def normal_rollout_bundle(self) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/governance-rollout.py"),
                "--phase",
                "normal",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        return json.loads(result.stdout)

    def incident_response_bypass(self) -> list[dict[str, object]]:
        return [
            {
                "actor_id": self.TEAM_IDS[name],
                "actor_type": "Team",
                "bypass_mode": "pull_request",
            }
            for name in ("platform", "security")
        ]

    def permanent_ruleset_fixtures(
        self,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        inventory: list[dict[str, object]] = []
        details: list[dict[str, object]] = []
        for ruleset_id, (name, contexts) in enumerate(
            AUDIT.MERGE_QUEUE_REQUIRED_STATUS_CHECK_CONTEXTS.items(), start=1
        ):
            inventory.append({"id": ruleset_id, "name": name})
            details.append(
                {
                    "bypass_actors": self.incident_response_bypass(),
                    "conditions": AUDIT._permanent_ruleset_conditions(rulesets[name]),
                    "rules": [AUDIT._required_status_checks_rule(contexts)],
                }
            )
        return inventory, details

    def merge_queue_detail(self, contexts: list[str]) -> dict[str, object]:
        return {
            "bypass_actors": self.incident_response_bypass(),
            "conditions": {
                "ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}
            },
            "rules": [
                AUDIT._required_status_checks_rule(contexts),
                {
                    "parameters": {
                        "check_response_timeout_minutes": 120,
                        "grouping_strategy": "ALLGREEN",
                        "max_entries_to_build": 1,
                        "max_entries_to_merge": 1,
                        "merge_method": "SQUASH",
                        "min_entries_to_merge": 1,
                        "min_entries_to_merge_wait_minutes": 0,
                    },
                    "type": "merge_queue",
                },
            ],
        }

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

    def test_release_governance_reader_contract_is_exact_and_read_only(self) -> None:
        document = AUDIT.load_yaml(ROOT / "catalog/github-apps.yaml")
        source = document["mindclade-release-governance-reader"]
        self.assertEqual(
            source["repositories"], [".github", "mindclade-internal-monorepo"]
        )
        self.assertFalse(source["webhookActive"])
        self.assertEqual(source["events"], [])
        apps = AUDIT.runtime_app_contracts(document)
        self.assertEqual(
            apps["mindclade-release-governance-reader"],
            {
                "repositories": [".github", "mindclade-internal-monorepo"],
                "permissions": {
                    "actions": "read",
                    "administration": "read",
                    "contents": "read",
                    "members": "read",
                    "metadata": "read",
                },
                "events": [],
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

    def test_compiler_bundle_drives_effective_org_and_repository_enforcement(self) -> None:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        repositories = AUDIT.load_yaml(ROOT / "catalog/repositories.yaml")
        bundle = self.normal_rollout_bundle()
        bundle["ruleset_enforcement_overrides"]["required-checks-go"] = "active"
        bundle["merge_queue_repository_enforcement_overrides"][
            "mindclade-internal-monorepo"
        ] = "active"
        bundle = AUDIT.validate_rollout_bundle(bundle, rulesets, repositories)

        organization, repository = AUDIT.expected_rulesets(
            rulesets, repositories, bundle
        )

        self.assertEqual(
            organization["required-checks-go"]["enforcement"], "active"
        )
        self.assertEqual(
            repository["mindclade-internal-monorepo"]["merge-queue"][
                "enforcement"
            ],
            "active",
        )
        self.assertEqual(
            repository["gitops"]["merge-queue"]["enforcement"], "evaluate"
        )

    def test_global_disabled_merge_queue_dominates_repository_override(self) -> None:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        repositories = AUDIT.load_yaml(ROOT / "catalog/repositories.yaml")
        bundle = self.normal_rollout_bundle()
        bundle["ruleset_enforcement_overrides"]["merge-queue"] = "disabled"
        bundle["merge_queue_repository_enforcement_overrides"][
            "mindclade-internal-monorepo"
        ] = "active"
        bundle = AUDIT.validate_rollout_bundle(bundle, rulesets, repositories)

        _, repository = AUDIT.expected_rulesets(rulesets, repositories, bundle)

        self.assertEqual(
            {
                expected["merge-queue"]["enforcement"]
                for expected in repository.values()
                if "merge-queue" in expected
            },
            {"disabled"},
        )

    def test_rollout_bundle_rejects_partial_repository_enforcement(self) -> None:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        repositories = AUDIT.load_yaml(ROOT / "catalog/repositories.yaml")
        bundle = self.normal_rollout_bundle()
        bundle["merge_queue_repository_enforcement_overrides"].pop("gitops")

        with self.assertRaisesRegex(
            AUDIT.AuditError, "must name exactly"
        ):
            AUDIT.validate_rollout_bundle(bundle, rulesets, repositories)

    def test_rollout_bundle_rejects_nonexact_canary_contexts(self) -> None:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        repositories = AUDIT.load_yaml(ROOT / "catalog/repositories.yaml")
        bundle = deepcopy(self.normal_rollout_bundle())
        repository = "mindclade-internal-monorepo"
        bundle["merge_queue_repository_enforcement_overrides"][repository] = "active"
        bundle["merge_queue_canary_required_checks"][repository] = ["bazel / verdict"]

        with self.assertRaisesRegex(AUDIT.AuditError, "contexts.*not exact"):
            AUDIT.validate_rollout_bundle(bundle, rulesets, repositories)

    def test_rollout_bundle_rejects_nonstring_enforcement_without_crashing(self) -> None:
        rulesets = AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml")
        repositories = AUDIT.load_yaml(ROOT / "catalog/repositories.yaml")
        bundle = self.normal_rollout_bundle()
        bundle["ruleset_enforcement_overrides"]["required-checks-go"] = []

        with self.assertRaisesRegex(AUDIT.AuditError, "invalid ruleset enforcement"):
            AUDIT.validate_rollout_bundle(bundle, rulesets, repositories)

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
                            "name": "stable-semver-only",
                            "negate": False,
                            "operator": "regex",
                            "pattern": "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$",
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

    def test_rollout_permanent_ruleset_details_are_audited_exactly(self) -> None:
        inventory, details = self.permanent_ruleset_fixtures()
        api = mock.Mock()
        api.get.side_effect = details
        errors: list[str] = []

        AUDIT.audit_rollout_permanent_rulesets(
            api,
            "mindclade",
            inventory,
            AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml"),
            self.TEAM_IDS,
            errors,
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            [call.args[0] for call in api.get.call_args_list],
            [
                f"/orgs/mindclade/rulesets/{ruleset_id}"
                for ruleset_id in range(1, len(inventory) + 1)
            ],
        )

    def test_rollout_permanent_ruleset_rejects_wrong_actions_integration(self) -> None:
        inventory, details = self.permanent_ruleset_fixtures()
        details[0]["rules"][0]["parameters"]["required_status_checks"][0][
            "integration_id"
        ] = 999
        api = mock.Mock()
        api.get.side_effect = details
        errors: list[str] = []

        AUDIT.audit_rollout_permanent_rulesets(
            api,
            "mindclade",
            inventory,
            AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml"),
            self.TEAM_IDS,
            errors,
        )

        self.assertTrue(any("required-checks-go rules" in error for error in errors))

    def test_rollout_permanent_ruleset_rejects_scope_bypass_and_policy_mutations(
        self,
    ) -> None:
        def wrong_condition(details: list[dict[str, object]]) -> None:
            details[0]["conditions"]["repository_property"]["include"][0][
                "property_values"
            ] = ["go"]

        def wrong_bypass(details: list[dict[str, object]]) -> None:
            details[0]["bypass_actors"][0]["bypass_mode"] = "always"

        def wrong_strict_policy(details: list[dict[str, object]]) -> None:
            details[0]["rules"][0]["parameters"][
                "strict_required_status_checks_policy"
            ] = False

        for expected_label, mutation in (
            ("conditions", wrong_condition),
            ("bypass actors", wrong_bypass),
            ("rules", wrong_strict_policy),
        ):
            with self.subTest(expected_label=expected_label, mutation=mutation.__name__):
                inventory, details = self.permanent_ruleset_fixtures()
                mutation(details)
                api = mock.Mock()
                api.get.side_effect = details
                errors: list[str] = []

                AUDIT.audit_rollout_permanent_rulesets(
                    api,
                    "mindclade",
                    inventory,
                    AUDIT.load_yaml(ROOT / "catalog/rulesets.yaml"),
                    self.TEAM_IDS,
                    errors,
                )

                self.assertTrue(
                    any(expected_label in error for error in errors), errors
                )

    def test_merge_queue_detail_is_audited_exactly(self) -> None:
        contexts = list(AUDIT.ROLLOUT_CONTEXTS["mindclade-internal-monorepo"])
        api = mock.Mock()
        api.get.return_value = self.merge_queue_detail(contexts)
        errors: list[str] = []

        AUDIT.audit_merge_queue_ruleset(
            api,
            "mindclade",
            "mindclade-internal-monorepo",
            [{"id": 71, "name": "merge-queue"}],
            self.TEAM_IDS,
            contexts,
            errors,
        )

        self.assertEqual(errors, [])
        api.get.assert_called_once_with(
            "/repos/mindclade/mindclade-internal-monorepo/rulesets/71"
        )

    def test_merge_queue_detail_rejects_scope_bypass_and_rule_mutations(self) -> None:
        contexts = list(AUDIT.ROLLOUT_CONTEXTS["mindclade-internal-monorepo"])

        def wrong_condition(detail: dict[str, object]) -> None:
            detail["conditions"]["ref_name"]["include"] = ["refs/heads/main"]

        def wrong_bypass(detail: dict[str, object]) -> None:
            detail["bypass_actors"][0]["bypass_mode"] = "always"

        def wrong_integration(detail: dict[str, object]) -> None:
            detail["rules"][0]["parameters"]["required_status_checks"][0][
                "integration_id"
            ] = 999

        def wrong_queue_size(detail: dict[str, object]) -> None:
            detail["rules"][1]["parameters"]["max_entries_to_build"] = 2

        for expected_label, mutation in (
            ("conditions", wrong_condition),
            ("bypass actors", wrong_bypass),
            ("rules", wrong_integration),
            ("rules", wrong_queue_size),
        ):
            with self.subTest(expected_label=expected_label, mutation=mutation.__name__):
                detail = self.merge_queue_detail(contexts)
                mutation(detail)
                api = mock.Mock()
                api.get.return_value = detail
                errors: list[str] = []

                AUDIT.audit_merge_queue_ruleset(
                    api,
                    "mindclade",
                    "mindclade-internal-monorepo",
                    [{"id": 71, "name": "merge-queue"}],
                    self.TEAM_IDS,
                    contexts,
                    errors,
                )

                self.assertTrue(
                    any(expected_label in error for error in errors), errors
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
                            "name": "stable-semver-only",
                            "negate": False,
                            "operator": "regex",
                            "pattern": "^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$",
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

    def test_release_tag_inventory_accepts_only_stable_semver(self) -> None:
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
                "alpha: non-stable-SemVer tag 'v5.0.0-rc.1' is forbidden; integrate or "
                "remove rescue, reconcile, backup, and temporary refs",
                "beta: non-stable-SemVer tag 'rescue/pre-rebase' is forbidden; integrate or "
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
