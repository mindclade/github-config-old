#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Safety tests for local GitHub configuration operators."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CI = load("export_ci_variables", "scripts/export-ci-variables.py")
IDP = load("export_idp_groups", "scripts/export-idp-groups.py")
OIDC = load("enforce_immutable_oidc", "scripts/enforce-immutable-oidc.py")


class ExportSafetyTest(unittest.TestCase):
    def test_ci_generation_failure_never_calls_gh(self) -> None:
        arguments = SimpleNamespace(
            bootstrap=ROOT,
            repo="mindclade/github-config",
            stage="full",
            set=True,
            check=False,
        )
        with (
            mock.patch.object(CI, "parse_args", return_value=arguments),
            mock.patch.object(
                CI, "compile_payload", side_effect=ValueError("invalid contract")
            ),
            mock.patch.object(CI.subprocess, "run") as run,
        ):
            self.assertEqual(CI.main(), 1)
        run.assert_not_called()

    def test_disabled_buildkite_is_a_noop_without_deferred_inputs(self) -> None:
        config = {
            "bootstrap": {"ENABLE_BUILDKITE_WIF": "false"},
            "mindclade-internal-monorepo": {
                "ARC_PROMOTER_APP_ID": "env:ARC_PROMOTER_APP_ID",
            },
        }

        pool = CI.configure_buildkite_phase(
            config, {"enabled": False, "workload_identity_pool": None}
        )

        self.assertIsNone(pool)
        self.assertEqual(config["bootstrap"], {"ENABLE_BUILDKITE_WIF": "false"})
        self.assertEqual(
            config["mindclade-internal-monorepo"],
            {"ARC_PROMOTER_APP_ID": "env:ARC_PROMOTER_APP_ID"},
        )

    def test_enabled_buildkite_is_rejected_after_retirement(self) -> None:
        config = {
            "bootstrap": {"ENABLE_BUILDKITE_WIF": "true"},
            "mindclade-internal-monorepo": {},
        }

        with self.assertRaisesRegex(ValueError, "retired"):
            CI.configure_buildkite_phase(
                config, {"enabled": True, "workload_identity_pool": None}
            )

        with self.assertRaisesRegex(ValueError, "retired"):
            CI.configure_buildkite_phase(
                config,
                {
                    "enabled": True,
                    "workload_identity_pool": "projects/not-numeric/locations/global/workloadIdentityPools/buildkite",
                },
            )

    def test_arc_release_identities_are_provider_and_workflow_exact(self) -> None:
        pool = "projects/123456789/locations/global/workloadIdentityPools/github"
        workflows = {
            "canary": "reusable-arc-wif-canary.yml",
            "builder": "reusable-arc-oci-build.yml",
            "qualification-reader": "reusable-arc-oci-qualify.yml",
            "qualifier": "reusable-arc-qualification-attest.yml",
            "signer": "reusable-binauthz-sign.yml",
            "promoter": "reusable-gitops-promote.yml",
        }
        identities = {}
        for capability, workflow in workflows.items():
            subject = (
                "repo:mindclade@316676129/mindclade-internal-monorepo@1333792222:"
                + (
                    "environment:release"
                    if capability in {"signer", "promoter"}
                    else "ref:refs/heads/main"
                )
            )
            provider = (
                "gh-mindclade-internal-monorepo"
                if capability == "signer"
                else f"gh-arc-{capability}"
            )
            mapped = subject if capability == "signer" else f"arc-{capability}:{subject}"
            identities[capability] = {
                "workload_identity_provider": f"{pool}/providers/{provider}",
                "principal": f"principal://iam.googleapis.com/{pool}/subject/{mapped}",
                "subject": subject,
                "workflow_ref": "mindclade/mindclade-internal-monorepo/.github/workflows/release.yml@refs/heads/main",
                "job_workflow_ref": f"mindclade/.github/.github/workflows/{workflow}@refs/tags/v4.0.0",
            }
        github = {
            "artifact_release_identities": identities,
            "artifact_signer": {
                field: identities["signer"][field]
                for field in (
                    "workload_identity_provider",
                    "principal",
                    "job_workflow_ref",
                )
            },
        }

        self.assertEqual(
            CI.artifact_release_contract(github, pool, "mindclade"), identities
        )
        identities["builder"]["principal"] = identities["qualifier"]["principal"]
        with self.assertRaisesRegex(ValueError, "builder"):
            CI.artifact_release_contract(github, pool, "mindclade")

    def test_bootstrap_stage_omits_deferred_catalog_inputs(self) -> None:
        config = {
            ".github": {"PIN_AUDIT_APP_ID": "env:PIN_AUDIT_APP_ID"},
            ".github-private": {},
            "github-config": {
                "ORGANIZATION": "mindclade",
                "BILLING_EMAIL": "env:BILLING_EMAIL",
                "ENVIRONMENT_PROJECT_IDS": "{}",
                "TF_PLAN_APP_ID": "env:TF_PLAN_APP_ID",
            },
            "bootstrap": {
                "GH_ORGANIZATION": "mindclade",
                "ENABLE_BUILDKITE_WIF": "false",
            },
            "infrastructure-live": {
                "DOMAIN": "mindclade.com",
                "TF_APP_ID": "env:TF_APP_ID",
            },
            "gitops": {
                "MONOREPO_ORG": "mindclade",
                "RENDER_APP_ID": "env:RENDER_APP_ID",
            },
            "mindclade-internal-monorepo": {
                "ARTIFACT_REGISTRY_HOST": "us-central1-docker.pkg.dev",
                "BINAUTHZ_BUILD_ATTESTOR": "env:BINAUTHZ_BUILD_ATTESTOR",
            },
        }

        selected = CI.select_bootstrap_stage(config)

        self.assertEqual(selected[".github"], {})
        self.assertNotIn("TF_PLAN_APP_ID", selected["github-config"])
        self.assertNotIn("TF_APP_ID", selected["infrastructure-live"])
        self.assertNotIn("RENDER_APP_ID", selected["gitops"])
        self.assertNotIn(
            "BINAUTHZ_BUILD_ATTESTOR", selected["mindclade-internal-monorepo"]
        )
        self.assertEqual(selected["github-config"]["ENVIRONMENT_PROJECT_IDS"], "{}")
        self.assertEqual(
            selected["bootstrap"]["SECURITY_CONTACT"], "env:SECURITY_CONTACT"
        )

    def test_github_identity_variables_are_derived_from_platform_contract(self) -> None:
        identities = {
            repository: {
                "repository": f"mindclade/{repository}",
                "repository_owner_id": "123",
                "repository_id": str(index),
            }
            for index, repository in enumerate(
                (
                    "bootstrap",
                    "github-config",
                    "infrastructure-live",
                    "gitops",
                    "mindclade-internal-monorepo",
                ),
                start=10,
            )
        }

        organization, owner_id, repository_ids_json = CI.github_repository_contract(
            {"organization": "mindclade", "repository_identities": identities}
        )

        self.assertEqual(organization, "mindclade")
        self.assertEqual(owner_id, "123")
        self.assertNotIn(" ", repository_ids_json)
        self.assertEqual(
            json.loads(repository_ids_json),
            {
                repository: identity["repository_id"]
                for repository, identity in identities.items()
            },
        )

    def test_idp_api_failure_is_not_treated_as_an_unmapped_user(self) -> None:
        failure = subprocess.CalledProcessError(
            1, ["gcloud"], stderr="permission denied"
        )
        with mock.patch.object(IDP.subprocess, "run", side_effect=failure):
            with self.assertRaises(IDP.ExportError):
                IDP.github_login("person@example.com")

    def test_empty_team_regression_is_detected(self) -> None:
        current = {"team_members": {"security": [{"username": "alice"}]}}
        generated = {"team_members": {"security": []}}
        self.assertEqual(
            IDP.empty_team_regressions(current, generated), ["security (had 1)"]
        )

    def test_idp_team_inventory_is_explicit(self) -> None:
        expected = {
            "biosecurity",
            "data-platform",
            "engineering",
            "incident-command",
            "infrastructure",
            "model-serving",
            "model-training",
            "platform",
            "product",
            "release",
            "research",
            "security",
        }

        self.assertFalse(set(IDP.TEAM_GROUPS) & IDP.DEFERRED_TEAMS)
        self.assertEqual(set(IDP.TEAM_GROUPS) | IDP.DEFERRED_TEAMS, expected)
        self.assertNotIn("data", IDP.TEAM_GROUPS)

    def test_atomic_write_replaces_complete_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "team-members.json"
            target.write_text("old", encoding="utf-8")
            IDP.atomic_write(target, "new\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

    def test_immutable_oidc_inputs_are_catalog_derived(self) -> None:
        self.assertEqual(
            OIDC.top_level_keys(ROOT / "catalog/repositories.yaml"),
            [
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            ],
        )
        claims, repository_opt_in, immutable_required = OIDC.oidc_policy(
            ROOT / "catalog/oidc-policy.yaml"
        )
        self.assertEqual(
            claims,
            [
                "repository_owner_id",
                "repository_id",
                "repository",
                "workflow_ref",
                "ref",
            ],
        )
        self.assertFalse(repository_opt_in)
        self.assertTrue(immutable_required)

    def test_immutable_oidc_check_rejects_legacy_subject(self) -> None:
        errors = OIDC.repository_expected(
            "bootstrap",
            {
                "use_default": True,
                "use_immutable_subject": False,
                "sub_claim_prefix": "repo:mindclade/bootstrap",
            },
            organization="mindclade",
            use_default=True,
            claims=[],
        )
        self.assertIn("bootstrap: use_immutable_subject is not true", errors)
        self.assertIn(
            "bootstrap: immutable sub_claim_prefix is absent or malformed", errors
        )

    def test_immutable_oidc_apply_uses_gh_without_a_token_argument(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(OIDC.subprocess, "run", return_value=completed) as run:
            OIDC.apply_policy(
                "mindclade",
                ["bootstrap"],
                ["repository_owner_id", "repository_id"],
                False,
            )

        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:2], ["gh", "api"])
            self.assertNotIn("Authorization", " ".join(command))
            self.assertNotIn("Bearer", " ".join(command))
            self.assertIn("use_immutable_subject=true", command)


if __name__ == "__main__":
    unittest.main()
