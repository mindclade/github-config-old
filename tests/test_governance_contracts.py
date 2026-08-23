#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Regression tests for semantic governance contract validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GOVERNANCE = load("governance_contracts", "scripts/governance_contracts.py")
TERRAFORM = load("terraform_contracts", "scripts/terraform_contracts.py")
ACCOUNT_HANDOFF = load(
    "validate_bootstrap_account_handoff",
    "scripts/validate-bootstrap-account-handoff.py",
)


class PromotionContractTest(unittest.TestCase):
    @staticmethod
    def rulesets(enforcement: str = "evaluate") -> dict[str, dict[str, str]]:
        return {
            ruleset: {"enforcement": enforcement}
            for ruleset in GOVERNANCE.EVIDENCE_GATED_RULESET_GATES
        }

    @staticmethod
    def gates(value: str = "blocked") -> dict[str, str]:
        names = {
            gate
            for gates in GOVERNANCE.EVIDENCE_GATED_RULESET_GATES.values()
            for gate in gates
        }
        return {name: value for name in names}

    def test_evaluate_is_valid_while_evidence_is_blocked(self) -> None:
        self.assertEqual(
            GOVERNANCE.evidence_gated_ruleset_errors(
                self.rulesets(),
                self.gates(),
            ),
            [],
        )

    def test_active_is_valid_only_after_every_ruleset_gate_is_qualified(self) -> None:
        self.assertEqual(
            GOVERNANCE.evidence_gated_ruleset_errors(
                self.rulesets("active"),
                self.gates("qualified"),
            ),
            [],
        )
        errors = GOVERNANCE.evidence_gated_ruleset_errors(
            self.rulesets("active"),
            self.gates(),
        )
        self.assertEqual(
            len(errors), len(GOVERNANCE.EVIDENCE_GATED_RULESET_GATES)
        )
        self.assertTrue(all("requires qualified gates" in message for message in errors))

    def test_disabled_is_not_a_valid_promotion_state(self) -> None:
        errors = GOVERNANCE.evidence_gated_ruleset_errors(
            self.rulesets("disabled"),
            self.gates(),
        )
        self.assertEqual(
            len(errors), len(GOVERNANCE.EVIDENCE_GATED_RULESET_GATES)
        )
        self.assertTrue(all("evaluate or active" in message for message in errors))

    def test_release_tag_creation_requires_the_signer_identity_gate(self) -> None:
        rulesets = self.rulesets()
        rulesets["release-tag-creation"]["enforcement"] = "active"
        gates = self.gates("qualified")
        gates["release_signer_identity_qualified"] = "blocked"
        errors = GOVERNANCE.evidence_gated_ruleset_errors(rulesets, gates)
        self.assertEqual(len(errors), 1)
        self.assertIn("release_signer_identity_qualified", errors[0])

    def test_release_tag_creation_requires_the_environment_gate(self) -> None:
        rulesets = self.rulesets()
        rulesets["release-tag-creation"]["enforcement"] = "active"
        gates = self.gates("qualified")
        gates["release_environments_qualified"] = "blocked"
        errors = GOVERNANCE.evidence_gated_ruleset_errors(rulesets, gates)
        self.assertEqual(len(errors), 1)
        self.assertIn("release_environments_qualified", errors[0])

    def test_fixed_resting_state_does_not_freeze_qualified_rules(self) -> None:
        expected = {
            "baseline-all": "active",
            "required-checks-mixed": "evaluate",
        }
        rulesets = {
            "baseline-all": {"enforcement": "active"},
            "required-checks-mixed": {"enforcement": "active"},
        }
        self.assertEqual(
            GOVERNANCE.resting_ruleset_errors(rulesets, expected),
            [],
        )
        rulesets["baseline-all"]["enforcement"] = "evaluate"
        self.assertEqual(
            len(GOVERNANCE.resting_ruleset_errors(rulesets, expected)),
            1,
        )


class DrEvidenceWorkflowContractTest(unittest.TestCase):
    def test_current_workflow_fails_closed_while_v5_is_blocked(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/dr-evidence.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            GOVERNANCE.dr_evidence_workflow_errors(workflow, "blocked"),
            [],
        )

    def test_qualified_state_requires_the_exact_v5_publication_caller(self) -> None:
        workflow = {
            "permissions": {"contents": "read", "id-token": "write"},
            "jobs": {
                "publish": {
                    "uses": (
                        "mindclade/.github/.github/workflows/"
                        "reusable-dr-evidence.yml@v5.0.0"
                    ),
                    "with": {
                        "report-path": "${{ inputs.report_path }}",
                        "environment": "${{ inputs.environment }}",
                        "primary-operator": "${{ github.actor }}",
                        "observer-operator": "${{ inputs.observer_operator }}",
                    },
                    "permissions": {
                        "actions": "read",
                        "contents": "read",
                        "id-token": "write",
                    },
                }
            },
        }
        self.assertEqual(
            GOVERNANCE.dr_evidence_workflow_errors(workflow, "qualified"),
            [],
        )
        self.assertTrue(
            GOVERNANCE.dr_evidence_workflow_errors(workflow, "blocked")
        )


class RunnerGroupContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner_groups = yaml.safe_load(
            (ROOT / "catalog/runner-groups.yaml").read_text(encoding="utf-8")
        )

    def test_current_release_and_presubmit_groups_are_exact(self) -> None:
        self.assertEqual(
            GOVERNANCE.runner_group_contract_errors(self.runner_groups),
            [],
        )

    def test_release_caller_cannot_replace_job_defining_workflows(self) -> None:
        self.runner_groups["mindclade-arc-artifact-authority"]["workflows"] = [
            "mindclade/mindclade-internal-monorepo/.github/workflows/release.yml@refs/heads/main"
        ]
        errors = GOVERNANCE.runner_group_contract_errors(self.runner_groups)
        self.assertEqual(len(errors), 1)
        self.assertIn("workflows is not exact", errors[0])

    def test_presubmit_cannot_share_artifact_authority_group(self) -> None:
        del self.runner_groups["mindclade-arc-ci"]
        errors = GOVERNANCE.runner_group_contract_errors(self.runner_groups)
        self.assertEqual(errors, ["ARC runner-group inventory is not exact"])


class RequiredCheckReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = yaml.safe_load(
            (ROOT / "catalog/required-check-readiness.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.gates = {"infrastructure_cost_verdict_ready": "blocked"}
        self.contexts = {"required-checks-tf": ("fmt", "validate", "plan")}

    def test_candidate_cost_verdict_is_not_required_while_blocked(self) -> None:
        self.assertEqual(
            GOVERNANCE.required_check_readiness_errors(
                self.contract,
                self.gates,
                self.contexts,
            ),
            [],
        )

    def test_blocked_cost_job_cannot_enter_the_active_ruleset(self) -> None:
        self.contexts["required-checks-tf"] += ("infracost / verdict",)
        errors = GOVERNANCE.required_check_readiness_errors(
            self.contract,
            self.gates,
            self.contexts,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("candidate context must not be required", errors[0])

    def test_qualified_readiness_requires_gate_and_required_context(self) -> None:
        cost = self.contract["contexts"]["infrastructure-cost"]
        cost["status"] = "qualified"
        cost["qualified_context"] = "infracost / verdict"
        errors = GOVERNANCE.required_check_readiness_errors(
            self.contract,
            self.gates,
            self.contexts,
        )
        self.assertEqual(len(errors), 4)

        self.gates["infrastructure_cost_verdict_ready"] = "qualified"
        self.contexts["required-checks-tf"] += ("infracost / verdict",)
        cost["observed_events"] = ["pull_request", "merge_group"]
        cost["intentional_negative_observed"] = True
        self.assertEqual(
            GOVERNANCE.required_check_readiness_errors(
                self.contract,
                self.gates,
                self.contexts,
            ),
            [],
        )


class MergeQueueReadinessTest(unittest.TestCase):
    EVIDENCE_EXPECTATIONS = {
        "positive_pull_request": ("pull_request", "success"),
        "positive_merge_group": ("merge_group", "success"),
        "intentional_negative_merge_group": ("merge_group", "failure"),
        "permanent_ruleset_audit": ("workflow_dispatch", "success"),
    }

    def setUp(self) -> None:
        self.contract = yaml.safe_load(
            (ROOT / "catalog/merge-queue-readiness.yaml").read_text(
                encoding="utf-8"
            )
        )

    def evidence(
        self,
        repository: str,
        field: str,
        index: int,
        *,
        qualified_uri: bool = True,
    ) -> dict[str, object]:
        event_name, conclusion = self.EVIDENCE_EXPECTATIONS[field]
        run_repository = (
            "github-config" if field == "permanent_ruleset_audit" else repository
        )
        digit = format(index, "x")
        generation = f"#{index}" if qualified_uri else ""
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
                f"gs://restricted/{repository}-{field}.json{generation}"
            ),
            "sha256": "sha256:" + digit * 64,
        }

    def test_current_sequential_contract_is_exact_and_blocked(self) -> None:
        self.assertEqual(
            GOVERNANCE.merge_queue_readiness_errors(self.contract), []
        )

    def test_repository_order_and_contexts_are_exact(self) -> None:
        self.contract["rollout_order"][0]["required_contexts"][0] = "wrong"
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertEqual(len(errors), 1)
        self.assertIn("required contexts are not exact", errors[0])

        self.setUp()
        self.contract["rollout_order"].reverse()
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertEqual(len(errors), 1)
        self.assertIn("repository order must be exactly", errors[0])

    def test_actions_integration_id_is_pinned(self) -> None:
        self.contract["rollout_order"][0]["github_actions_integration_id"] = 1
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertEqual(len(errors), 1)
        self.assertIn("integration id must be 15368", errors[0])

    def test_canary_state_requires_exact_three_evidence_records(self) -> None:
        monorepo = self.contract["rollout_order"][0]
        monorepo["status"] = "canary_passed"
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertEqual(len(errors), 1)
        self.assertIn("canary_passed evidence must be exactly", errors[0])

        for index, field in enumerate(GOVERNANCE.MERGE_QUEUE_EVIDENCE_FIELDS[:3], 1):
            monorepo["evidence"][field] = self.evidence(
                "mindclade-internal-monorepo", field, index
            )
        self.assertEqual(
            GOVERNANCE.merge_queue_readiness_errors(self.contract), []
        )

    def test_active_canary_is_source_represented_before_evidence(self) -> None:
        monorepo = self.contract["rollout_order"][0]
        monorepo["status"] = "canary_active"

        self.assertEqual(
            GOVERNANCE.merge_queue_readiness_errors(self.contract), []
        )

    def test_evidence_is_bound_to_role_repository_outcome_and_unique_run(self) -> None:
        monorepo = self.contract["rollout_order"][0]
        monorepo["status"] = "canary_passed"
        monorepo["blocker"] = None
        for index, field in enumerate(GOVERNANCE.MERGE_QUEUE_EVIDENCE_FIELDS[:3], 1):
            monorepo["evidence"][field] = self.evidence(
                "mindclade-internal-monorepo", field, index
            )

        negative = monorepo["evidence"]["intentional_negative_merge_group"]
        negative["conclusion"] = "success"
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertTrue(any("conclusion must be failure" in error for error in errors))

        negative["conclusion"] = "failure"
        negative["evidence_role"] = "positive_merge_group"
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertTrue(any("evidence role is not exact" in error for error in errors))

        negative["evidence_role"] = "intentional_negative_merge_group"
        negative["subject_repository"] = "gitops"
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertTrue(any("subject repository is not exact" in error for error in errors))

        negative["subject_repository"] = "mindclade-internal-monorepo"
        negative["run_url"] = monorepo["evidence"]["positive_merge_group"]["run_url"]
        errors = GOVERNANCE.merge_queue_readiness_errors(self.contract)
        self.assertTrue(any("run URLs must be unique" in error for error in errors))

    def test_schema_rejects_mutable_or_unqualified_evidence_location(self) -> None:
        schema = json.loads(
            (ROOT / "catalog/schema/merge-queue-readiness.schema.json").read_text(
                encoding="utf-8"
            )
        )
        monorepo = self.contract["rollout_order"][0]
        monorepo["status"] = "canary_passed"
        monorepo["blocker"] = None
        for index, field in enumerate(GOVERNANCE.MERGE_QUEUE_EVIDENCE_FIELDS[:3], 1):
            monorepo["evidence"][field] = self.evidence(
                "mindclade-internal-monorepo",
                field,
                index,
                qualified_uri=False,
            )
        errors = list(Draft202012Validator(schema).iter_errors(self.contract))
        self.assertTrue(
            any("restricted_snapshot_uri" in str(error.absolute_path) for error in errors)
        )

        for index, field in enumerate(GOVERNANCE.MERGE_QUEUE_EVIDENCE_FIELDS[:3], 1):
            monorepo["evidence"][field]["restricted_snapshot_uri"] += f"#{index}"
        self.assertEqual(
            list(Draft202012Validator(schema).iter_errors(self.contract)), []
        )

    def test_affected_latency_does_not_gate_required_check_activation(self) -> None:
        self.assertNotIn(
            "monorepo_affected_latency_qualified",
            GOVERNANCE.EVIDENCE_GATED_RULESET_GATES["required-checks-go"],
        )
        self.assertNotIn(
            "monorepo_affected_latency_qualified",
            GOVERNANCE.EVIDENCE_GATED_RULESET_GATES["required-checks-mixed"],
        )

class TerraformSemanticContractTest(unittest.TestCase):
    def test_bootstrap_account_handoff_contract_accepts_current_source(self) -> None:
        self.assertEqual(ACCOUNT_HANDOFF.contract_errors(ROOT), [])

    def test_required_context_in_a_comment_cannot_satisfy_the_contract(self) -> None:
        source = (
            ROOT / "modules/rulesets/required-checks-infra-static.tf"
        ).read_text(encoding="utf-8")
        source, replacements = re.subn(
            r'context\s*=\s*"infra-static"',
            'context = "wrong-context"\n        # context = "infra-static"',
            source,
            count=1,
        )
        self.assertEqual(replacements, 1)
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / "modules/rulesets/required-checks-infra-static.tf"
            target.parent.mkdir(parents=True)
            target.write_text(source, encoding="utf-8")
            contract = TERRAFORM.RequiredStatusRulesetContract(
                path="modules/rulesets/required-checks-infra-static.tf",
                resource_name="required_checks_infra_static",
                ruleset_name="required-checks-infra-static",
                repositories=("mindclade-internal-monorepo",),
                contexts=("infra-static",),
            )
            with self.assertRaisesRegex(
                TERRAFORM.TerraformContractError,
                "required_check.contexts",
            ):
                TERRAFORM.validate_required_status_ruleset(
                    temporary_root,
                    contract,
                    {
                        "repositories": ["mindclade-internal-monorepo"],
                        "enforcement": "evaluate",
                    },
                )

    def test_required_check_integration_pin_is_semantic(self) -> None:
        source = (
            ROOT / "modules/rulesets/required-checks-infra-static.tf"
        ).read_text(encoding="utf-8")
        source, replacements = re.subn(
            r"integration_id\s*=\s*local\.github_actions_integration_id",
            "integration_id = local.wrong_integration_id "
            "# integration_id = local.github_actions_integration_id",
            source,
            count=1,
        )
        self.assertEqual(replacements, 1)
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / "modules/rulesets/required-checks-infra-static.tf"
            target.parent.mkdir(parents=True)
            target.write_text(source, encoding="utf-8")
            contract = TERRAFORM.RequiredStatusRulesetContract(
                path="modules/rulesets/required-checks-infra-static.tf",
                resource_name="required_checks_infra_static",
                ruleset_name="required-checks-infra-static",
                repositories=("mindclade-internal-monorepo",),
                contexts=("infra-static",),
                integration_expression="local.github_actions_integration_id",
            )
            with self.assertRaisesRegex(
                TERRAFORM.TerraformContractError,
                "required_check.integration_ids",
            ):
                TERRAFORM.validate_required_status_ruleset(
                    temporary_root,
                    contract,
                    {
                        "repositories": ["mindclade-internal-monorepo"],
                        "enforcement": "evaluate",
                    },
                )

    def test_structural_ruleset_and_oidc_contracts_accept_current_modules(self) -> None:
        contract = TERRAFORM.RequiredStatusRulesetContract(
            path="modules/rulesets/required-checks-mixed.tf",
            resource_name="required_checks_mixed",
            ruleset_name="required-checks-mixed",
            language_profiles=("mixed",),
            contexts=(
                "python / build",
                "rust / build",
                "architecture",
                "Go registry + admission / live PostgreSQL and failure injection",
                "bazel / verdict",
            ),
            integration_expression="local.github_actions_integration_id",
        )
        TERRAFORM.validate_required_status_ruleset(
            ROOT,
            contract,
            {"language_profiles": ["mixed"], "enforcement": "evaluate"},
        )
        TERRAFORM.validate_release_tag_contracts(ROOT)
        TERRAFORM.validate_environment_handoff(ROOT)
        TERRAFORM.validate_oidc_module(ROOT)
        TERRAFORM.validate_import_contract(ROOT)
        TERRAFORM.validate_bazel_cache_ci_variable_contract(ROOT)
        TERRAFORM.validate_bootstrap_account_handoff_ci_variable_contract(ROOT)

    def test_bootstrap_account_handoff_contract_rejects_catalog_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            for source in (
                "contracts/bootstrap-account-handoff.schema.json",
                "catalog/ci-variables.yaml",
                "modules/repositories/ci-variables.tf",
            ):
                target = temporary_root / source
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    (ROOT / source).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            catalog = temporary_root / "catalog/ci-variables.yaml"
            catalog_data = yaml.safe_load(catalog.read_text(encoding="utf-8"))
            catalog_data["infrastructure-live"][
                "BOOTSTRAP_ACCOUNT_HANDOFF_JSON"
            ] = "{}"
            catalog.write_text(
                yaml.safe_dump(catalog_data, sort_keys=True),
                encoding="utf-8",
            )
            self.assertIn(
                "[ACCOUNT-HANDOFF-CATALOG] handoff must not be a free-form catalog input",
                ACCOUNT_HANDOFF.contract_errors(temporary_root),
            )

    def test_bootstrap_account_handoff_comment_cannot_hide_substitution(self) -> None:
        source = (ROOT / "modules/repositories/ci-variables.tf").read_text(
            encoding="utf-8"
        )
        safe_expression = (
            "local.bootstrap_account_handoff.service_accounts[name] == expected"
        )
        source = source.replace(
            safe_expression,
            "local.bootstrap_account_handoff.service_accounts[name] != expected\n"
            f"        # {safe_expression}",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / "modules/repositories/ci-variables.tf"
            target.parent.mkdir(parents=True)
            target.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                TERRAFORM.TerraformContractError,
                "assertion omits required terms",
            ):
                TERRAFORM.validate_bootstrap_account_handoff_ci_variable_contract(
                    temporary_root
                )

    def test_bazel_cache_comment_cannot_hide_collapsed_reader_writer(self) -> None:
        source = (ROOT / "modules/repositories/ci-variables.tf").read_text(
            encoding="utf-8"
        )
        safe_expression = (
            "local.bazel_cache_handoff.reader != local.bazel_cache_handoff.writer"
        )
        source = source.replace(
            safe_expression,
            "local.bazel_cache_handoff.reader == local.bazel_cache_handoff.writer\n"
            f"      # {safe_expression}",
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / "modules/repositories/ci-variables.tf"
            target.parent.mkdir(parents=True)
            target.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                TERRAFORM.TerraformContractError,
                "handoff: assertion omits required terms",
            ):
                TERRAFORM.validate_bazel_cache_ci_variable_contract(temporary_root)

    def test_bazel_cache_activation_requires_complete_applied_handoff(self) -> None:
        source = (ROOT / "modules/repositories/ci-variables.tf").read_text(
            encoding="utf-8"
        )
        safe_expression = (
            "alltrue([for value in local.bazel_cache_handoff_values : value != \"\"])"
        )
        activation_expression = (
            'local.bazel_remote_cache_state == "blocked" || (\n'
            f"          {safe_expression}"
        )
        source = source.replace(
            activation_expression,
            'local.bazel_remote_cache_state == "blocked" || (\n'
            "          true &&\n"
            f"          # {safe_expression}",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            target = temporary_root / "modules/repositories/ci-variables.tf"
            target.parent.mkdir(parents=True)
            target.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                TERRAFORM.TerraformContractError,
                "activation: assertion omits required terms",
            ):
                TERRAFORM.validate_bazel_cache_ci_variable_contract(
                    temporary_root
                )

    def test_access_expiry_checks_the_parsed_job_not_comments(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/drift.yml").read_text(encoding="utf-8")
        )
        TERRAFORM.validate_drift_access_expiry(workflow)
        workflow["jobs"]["access-expiry"]["steps"][-1]["if"] = "${{ false }}"
        with self.assertRaisesRegex(
            TERRAFORM.TerraformContractError,
            "does not select the failure step",
        ):
            TERRAFORM.validate_drift_access_expiry(workflow)

    def test_drift_readiness_binds_exact_catalog_variables(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/drift.yml").read_text(encoding="utf-8")
        )
        TERRAFORM.validate_drift_readiness(workflow)
        activation = workflow["jobs"]["readiness"]["steps"][0]
        activation["env"]["TF_PLAN_APP_ID"] = "${{ secrets.TF_PLAN_APP_ID }}"
        with self.assertRaisesRegex(
            TERRAFORM.TerraformContractError,
            "activation.env",
        ):
            TERRAFORM.validate_drift_readiness(workflow)


if __name__ == "__main__":
    unittest.main()
