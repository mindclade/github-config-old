#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Regression tests for semantic governance contract validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import yaml


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


class TerraformSemanticContractTest(unittest.TestCase):
    def test_bootstrap_account_handoff_contract_accepts_current_source(self) -> None:
        self.assertEqual(ACCOUNT_HANDOFF.contract_errors(ROOT), [])

    def test_required_context_in_a_comment_cannot_satisfy_the_contract(self) -> None:
        source = (
            ROOT / "modules/rulesets/required-checks-infra-static.tf"
        ).read_text(encoding="utf-8")
        source = source.replace(
            'context = "infra-static"',
            'context = "wrong-context"\n        # context = "infra-static"',
        )
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
