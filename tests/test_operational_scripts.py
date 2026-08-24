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
from datetime import date
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
EXPIRY = load("check_access_expiry", "scripts/check-access-expiry.py")


class ExportSafetyTest(unittest.TestCase):
    @staticmethod
    def deployed_v12_contract() -> dict[str, object]:
        repositories = (
            "bootstrap",
            "github-config",
            "infrastructure-live",
            "gitops",
            "mindclade-internal-monorepo",
        )
        pool = "projects/123456789/locations/global/workloadIdentityPools/github"
        return {
            "contract_version": "1.2.0",
            "organization_id": "960418882450",
            "billing_account": "01262F-73BD24-9AE6B7",
            "state_project_id": "mc-b-seed-fb7649",
            "federation_project_id": "mc-b-cicd-fb7649",
            "state": {
                "primary_location": "US",
                "primary_buckets": {
                    "bootstrap": "mc-bootstrap-state",
                    "github-config": "mc-github-config-state",
                    "infrastructure-live-development": "mc-live-development",
                    "infrastructure-live-staging": "mc-live-staging",
                    "infrastructure-live-production": "mc-live-production",
                },
                "replica_buckets": {"bootstrap": "mc-bootstrap-replica"},
            },
            "github": {
                "organization": "mindclade",
                "workload_identity_pool": pool,
                "workload_identity_providers": {
                    name: f"{pool}/providers/gh-{name}" for name in repositories
                },
                "repository_identities": {
                    name: {
                        "repository": f"mindclade/{name}",
                        "repository_owner_id": "316676129",
                        "repository_id": str(1000 + index),
                    }
                    for index, name in enumerate(repositories)
                },
                "artifact_signer": {
                    "workload_identity_provider": (
                        f"{pool}/providers/gh-mindclade-internal-monorepo"
                    ),
                    "principal": (
                        f"principal://iam.googleapis.com/{pool}/subject/"
                        "repo:mindclade@316676129/"
                        "mindclade-internal-monorepo@1004:environment:release"
                    ),
                    "job_workflow_ref": (
                        "mindclade/.github/.github/workflows/"
                        "reusable-binauthz-sign.yml@refs/tags/v3.0.0"
                    ),
                },
            },
            "buildkite": {
                "enabled": False,
                "workload_identity_pool": None,
                "workload_identity_provider": None,
            },
            "automation_identities": {
                "bootstrap-plan": "bootstrap-plan@example.iam.gserviceaccount.com",
                "bootstrap-drift": "bootstrap-drift@example.iam.gserviceaccount.com",
                "bootstrap-apply": "bootstrap-apply@example.iam.gserviceaccount.com",
                "github-config-plan": "github-config-plan@example.iam.gserviceaccount.com",
                "github-config-apply": "github-config-apply@example.iam.gserviceaccount.com",
                "infrastructure-live-plan": "live-plan@example.iam.gserviceaccount.com",
                "infrastructure-live-apply-foundation": "live-foundation@example.iam.gserviceaccount.com",
                "infrastructure-live-apply-development": "live-development@example.iam.gserviceaccount.com",
                "infrastructure-live-apply-staging": "live-staging@example.iam.gserviceaccount.com",
                "infrastructure-live-apply-production": "live-production@example.iam.gserviceaccount.com",
            },
            "automation_secret": {"project_id": "mc-b-seed-fb7649"},
        }

    @classmethod
    def staged_v15_contract(cls) -> dict[str, object]:
        platform = cls.deployed_v12_contract()
        platform["contract_version"] = "1.5.0"
        github = platform["github"]
        pool = github["workload_identity_pool"]
        monorepo_identity = github["repository_identities"][
            "mindclade-internal-monorepo"
        ]
        owner_id = monorepo_identity["repository_owner_id"]
        repository_id = monorepo_identity["repository_id"]
        subject_prefix = (
            f"repo:mindclade@{owner_id}/"
            f"mindclade-internal-monorepo@{repository_id}"
        )
        workflows = {
            "canary": "reusable-arc-wif-canary.yml",
            "builder": "reusable-arc-oci-build.yml",
            "qualification-reader": "reusable-arc-oci-qualify.yml",
            "qualifier": "reusable-arc-qualification-attest.yml",
            "signer": "reusable-binauthz-sign.yml",
            "promoter": "reusable-gitops-promote.yml",
        }
        release_identities = {}
        for capability, workflow in workflows.items():
            subject = subject_prefix + (
                ":environment:release"
                if capability in {"signer", "promoter"}
                else ":ref:refs/heads/main"
            )
            provider_id = (
                "gh-mindclade-internal-monorepo"
                if capability == "signer"
                else f"gh-arc-{capability}"
            )
            mapped_subject = (
                subject
                if capability == "signer"
                else f"arc-{capability}:{subject}"
            )
            release_identities[capability] = {
                "workload_identity_provider": f"{pool}/providers/{provider_id}",
                "principal": (
                    f"principal://iam.googleapis.com/{pool}/subject/{mapped_subject}"
                ),
                "subject": subject,
                "workflow_ref": (
                    "mindclade/mindclade-internal-monorepo/.github/workflows/"
                    "release.yml@refs/heads/main"
                ),
                "job_workflow_ref": (
                    f"mindclade/.github/.github/workflows/{workflow}"
                    "@refs/tags/v5.0.0"
                ),
            }
        github["artifact_release_identities"] = release_identities
        github["artifact_signer"] = {
            field: release_identities["signer"][field]
            for field in (
                "workload_identity_provider",
                "principal",
                "job_workflow_ref",
            )
        }
        production_subject = (
            "repo:mindclade@316676129/gitops@1003:environment:production"
        )
        github["production_qualification_identity"] = {
            "workload_identity_provider": (
                f"{pool}/providers/gh-production-qualification"
            ),
            "principal": (
                f"principal://iam.googleapis.com/{pool}/subject/"
                f"production-qualification:{production_subject}"
            ),
            "subject": production_subject,
            "workflow_ref": (
                "mindclade/gitops/.github/workflows/"
                "production-qualification-evidence.yml@refs/heads/main"
            ),
        }
        github["dr_evidence_identity"] = {
            "workload_identity_provider": f"{pool}/providers/gh-dr-evidence",
            "job_workflow_ref": (
                "mindclade/.github/.github/workflows/"
                "reusable-dr-evidence.yml@refs/tags/v5.0.0"
            ),
            "principals": {
                f"{repository}:{environment}": (
                    f"principal://iam.googleapis.com/{pool}/subject/dr-evidence:"
                    f"repo:mindclade@316676129/{repository}@1000:"
                    f"environment:{environment}"
                )
                for repository in (
                    "bootstrap",
                    "github-config",
                    "infrastructure-live",
                    "gitops",
                )
                for environment in ("scratch", "staging")
            },
        }
        repository = "mindclade/mindclade-internal-monorepo"
        routes = {
            "pull-request-read": (
                "read",
                "pull_request",
                "pull-request-merge",
                f"{repository}/.github/workflows/presubmit.yml",
            ),
            "trusted-main-write": (
                "write",
                "push",
                "protected-main",
                f"{repository}/.github/workflows/presubmit.yml",
            ),
            "merge-group-write": (
                "write",
                "merge_group",
                "protected-merge-queue",
                f"{repository}/.github/workflows/presubmit.yml",
            ),
            "nightly-write": (
                "write",
                "schedule",
                "protected-main",
                f"{repository}/.github/workflows/nightly.yml",
            ),
        }
        github["bazel_cache_identity"] = {
            "workload_identity_provider": f"{pool}/providers/gh-bazel-cache",
            "repository": repository,
            "repository_owner_id": owner_id,
            "repository_id": repository_id,
            "routes": {
                route: {
                    "access": access,
                    "event_name": event_name,
                    "principal": (
                        f"principal://iam.googleapis.com/{pool}/subject/"
                        f"bazel-cache:{route}"
                    ),
                    "ref_policy": ref_policy,
                    "workflow_path": workflow_path,
                }
                for route, (
                    access,
                    event_name,
                    ref_policy,
                    workflow_path,
                ) in routes.items()
            },
        }
        return platform

    @staticmethod
    def staged_v14_handoff(platform: dict[str, object]) -> object:
        variables = {
            name: f"value-{name.lower()}"
            for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.4.0"]
        }
        variables.update(
            {
                "CI_PROJECT_ID": "mc-common-ci",
                "WIF_PROVIDER_BAZEL_CACHE": platform["github"][
                    "bazel_cache_identity"
                ]["workload_identity_provider"],
                "SA_BAZEL_CACHE_READER": (
                    "bazel-cache-reader@mc-common-ci.iam.gserviceaccount.com"
                ),
                "SA_BAZEL_CACHE_WRITER": (
                    "bazel-cache-writer@mc-common-ci.iam.gserviceaccount.com"
                ),
            }
        )
        return CI.AppliedHandoff(contract_version="1.4.0", variables=variables)

    @classmethod
    def staged_v16_contract(cls) -> dict[str, object]:
        platform = cls.staged_v15_contract()
        platform["contract_version"] = "1.6.0"
        github = platform["github"]
        pool = github["workload_identity_pool"]
        repository_identity = github["repository_identities"][
            "mindclade-internal-monorepo"
        ]
        subject = (
            f"repo:mindclade@{repository_identity['repository_owner_id']}/"
            f"mindclade-internal-monorepo@{repository_identity['repository_id']}:"
            "environment:workstation-image-publication"
        )
        github["workstation_image_identity"] = {
            "workload_identity_provider": f"{pool}/providers/gh-workstation-image",
            "principal": (
                f"principal://iam.googleapis.com/{pool}/subject/"
                f"workstation-image:{subject}"
            ),
            "repository": "mindclade/mindclade-internal-monorepo",
            "repository_id": repository_identity["repository_id"],
            "subject": subject,
            "workflow_ref": (
                "mindclade/mindclade-internal-monorepo/.github/workflows/"
                "nixos-image.yml@refs/heads/main"
            ),
            "job_workflow_ref": (
                "mindclade/.github/.github/workflows/"
                "reusable-nixos-gce-image-publish.yml@refs/tags/v5.0.0"
            ),
        }
        return platform

    @staticmethod
    def staged_v15_handoff(platform: dict[str, object]) -> object:
        variables = {
            name: f"value-{name.lower()}"
            for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.5.0"]
        }
        project = "mc-common-ci"
        variables.update(
            {
                "CI_PROJECT_ID": project,
                "WIF_PROVIDER_BAZEL_CACHE": platform["github"][
                    "bazel_cache_identity"
                ]["workload_identity_provider"],
                "SA_BAZEL_CACHE_READER": (
                    f"bazel-cache-reader@{project}.iam.gserviceaccount.com"
                ),
                "SA_BAZEL_CACHE_WRITER": (
                    f"bazel-cache-writer@{project}.iam.gserviceaccount.com"
                ),
                "WIF_PROVIDER_WORKSTATION_IMAGE": platform["github"][
                    "workstation_image_identity"
                ]["workload_identity_provider"],
                "SA_WORKSTATION_IMAGE_BUILDER": (
                    f"workstation-image-pub@{project}.iam.gserviceaccount.com"
                ),
                "WORKSTATION_IMAGE_BUCKET": "mc-common-ci-workstation-images",
            }
        )
        return CI.AppliedHandoff(contract_version="1.5.0", variables=variables)

    def test_deployed_v12_contract_keeps_arc_authority_inactive(self) -> None:
        catalog = {
            ".github": {},
            ".github-private": {},
            "github-config": {"ENVIRONMENT_PROJECT_IDS": "{}"},
            "bootstrap": {
                "ENABLE_BUILDKITE_WIF": "false",
                "SECURITY_CONTACT": "security@mindclade.com",
            },
            "infrastructure-live": {},
            "gitops": {},
            "mindclade-internal-monorepo": {},
        }
        outputs = {"platform_contract": {"value": self.deployed_v12_contract()}}
        with (
            mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]),
            mock.patch.object(CI, "resolve_environment", side_effect=lambda value: value),
        ):
            payload = CI.compile_payload(ROOT, stage="bootstrap")

        self.assertNotIn(
            "ARTIFACT_RELEASE_IDENTITIES_JSON", payload["infrastructure-live"]
        )
        self.assertEqual(
            payload["mindclade-internal-monorepo"]["WIF_PROVIDER_SIGNER"],
            payload["infrastructure-live"]["WIF_PROVIDER_SIGNER"],
        )
        self.assertNotIn(
            "WIF_PROVIDER_ARC_BUILDER", payload["mindclade-internal-monorepo"]
        )

    def test_v16_workstation_image_handoff_is_exact(self) -> None:
        platform = self.staged_v16_contract()
        pool = platform["github"]["workload_identity_pool"]
        identity = CI.workstation_image_identity_contract(
            platform["github"], pool, "mindclade"
        )
        handoff = self.staged_v15_handoff(platform)
        CI.validate_applied_workstation_image_handoff(handoff, identity)
        handoff.variables["SA_WORKSTATION_IMAGE_BUILDER"] = handoff.variables[
            "SA_BAZEL_CACHE_READER"
        ]
        with self.assertRaisesRegex(ValueError, "publisher differs"):
            CI.validate_applied_workstation_image_handoff(handoff, identity)

    def test_deployed_v12_rejects_a_future_signer_workflow(self) -> None:
        platform = self.deployed_v12_contract()
        platform["github"]["artifact_signer"]["job_workflow_ref"] = (
            "mindclade/.github/.github/workflows/"
            "reusable-binauthz-sign.yml@refs/tags/v5.0.0"
        )
        catalog = {
            name: {}
            for name in (
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            )
        }
        catalog["bootstrap"]["ENABLE_BUILDKITE_WIF"] = "false"
        outputs = {"platform_contract": {"value": platform}}
        with (
            mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]),
            mock.patch.object(CI, "resolve_environment", side_effect=lambda value: value),
        ):
            with self.assertRaisesRegex(ValueError, "legacy artifact signer"):
                CI.compile_payload(ROOT, stage="bootstrap")

    def test_ci_generation_failure_never_calls_gh(self) -> None:
        arguments = SimpleNamespace(
            bootstrap=ROOT,
            repo="mindclade/github-config",
            stage="full",
            applied_handoff=None,
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
                "job_workflow_ref": (
                    f"mindclade/.github/.github/workflows/{workflow}@refs/tags/v5.0.0"
                ),
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

    def test_production_qualification_identity_is_exact(self) -> None:
        pool = "projects/123456789/locations/global/workloadIdentityPools/github"
        subject = "repo:mindclade@316676129/gitops@1333792222:environment:production"
        identity = {
            "workload_identity_provider": (
                f"{pool}/providers/gh-production-qualification"
            ),
            "principal": (
                f"principal://iam.googleapis.com/{pool}/subject/"
                f"production-qualification:{subject}"
            ),
            "subject": subject,
            "workflow_ref": (
                "mindclade/gitops/.github/workflows/"
                "production-qualification-evidence.yml@refs/heads/main"
            ),
        }
        github = {"production_qualification_identity": identity}
        self.assertEqual(
            CI.production_qualification_identity_contract(
                github, pool, "mindclade"
            ),
            identity,
        )
        identity["subject"] = subject.replace("production", "staging")
        with self.assertRaisesRegex(ValueError, "subject differs"):
            CI.production_qualification_identity_contract(
                github, pool, "mindclade"
            )

    def test_applied_handoff_inventory_and_catalog_projection_are_exact(self) -> None:
        variables = {
            name: f"value-{name.lower()}"
            for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.3.0"]
        }
        config = {
            "gitops": {"SA_GITOPS_RENDER": "env:SA_GITOPS_RENDER"},
            "other": {
                name: f"env:{name}"
                for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.3.0"]
                - {"SA_GITOPS_RENDER"}
            },
        }
        handoff = CI.AppliedHandoff(
            contract_version="1.3.0", variables=variables
        )
        CI.apply_applied_handoff(config, handoff)
        self.assertEqual(
            config["gitops"]["SA_GITOPS_RENDER"], variables["SA_GITOPS_RENDER"]
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.json"
            payload = {
                "contract_version": "1.3.0",
                "producer": "mindclade/infrastructure-live",
                "source_commit": "a" * 40,
                "environment": "production",
                "source_units": CI.APPLIED_HANDOFF_SOURCE_UNITS,
                "variables": variables,
                "credential_material_included": False,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(CI.load_applied_handoff(path), handoff)

            v14_variables = {
                name: f"value-{name.lower()}"
                for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.4.0"]
            }
            v14_handoff = CI.AppliedHandoff(
                contract_version="1.4.0", variables=v14_variables
            )
            payload["contract_version"] = "1.4.0"
            payload["variables"] = v14_variables
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(CI.load_applied_handoff(path), v14_handoff)

            payload["variables"].pop("SA_GITOPS_RENDER")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inventory"):
                CI.load_applied_handoff(path)

    def test_bazel_cache_contract_and_applied_handoff_are_exact(self) -> None:
        platform = self.staged_v15_contract()
        github = platform["github"]
        pool = github["workload_identity_pool"]
        identity = github["bazel_cache_identity"]

        self.assertEqual(
            CI.bazel_cache_identity_contract(github, pool, "mindclade"),
            identity,
        )
        handoff = self.staged_v14_handoff(platform)
        CI.validate_applied_bazel_cache_handoff(handoff, identity)

        identity["routes"]["pull-request-read"]["access"] = "write"
        with self.assertRaisesRegex(ValueError, "route differs: pull-request-read"):
            CI.bazel_cache_identity_contract(github, pool, "mindclade")

    def test_bazel_cache_handoff_rejects_provider_or_account_substitution(self) -> None:
        platform = self.staged_v15_contract()
        identity = platform["github"]["bazel_cache_identity"]
        handoff = self.staged_v14_handoff(platform)
        handoff.variables["WIF_PROVIDER_BAZEL_CACHE"] = (
            "projects/123456789/locations/global/workloadIdentityPools/github/"
            "providers/gh-mindclade-internal-monorepo"
        )
        with self.assertRaisesRegex(ValueError, "provider differs"):
            CI.validate_applied_bazel_cache_handoff(handoff, identity)

        handoff = self.staged_v14_handoff(platform)
        handoff.variables["SA_BAZEL_CACHE_WRITER"] = handoff.variables[
            "SA_BAZEL_CACHE_READER"
        ]
        with self.assertRaisesRegex(ValueError, "SA_BAZEL_CACHE_WRITER"):
            CI.validate_applied_bazel_cache_handoff(handoff, identity)

    def test_bootstrap_account_handoff_is_canonical_and_source_exact(self) -> None:
        platform = self.staged_v15_contract()
        values = {
            "STATE_LOCATION": platform["state"]["primary_location"],
            "TFSTATE_BUCKET_DEVELOPMENT": platform["state"]["primary_buckets"][
                "infrastructure-live-development"
            ],
            "TFSTATE_BUCKET_STAGING": platform["state"]["primary_buckets"][
                "infrastructure-live-staging"
            ],
            "TFSTATE_BUCKET_PRODUCTION": platform["state"]["primary_buckets"][
                "infrastructure-live-production"
            ],
            "SA_TF_LIVE_PLAN": platform["automation_identities"][
                "infrastructure-live-plan"
            ],
            "SA_TF_LIVE_APPLY_FOUNDATION": platform["automation_identities"][
                "infrastructure-live-apply-foundation"
            ],
            "SA_TF_LIVE_APPLY_DEVELOPMENT": platform["automation_identities"][
                "infrastructure-live-apply-development"
            ],
            "SA_TF_LIVE_APPLY_STAGING": platform["automation_identities"][
                "infrastructure-live-apply-staging"
            ],
            "SA_TF_LIVE_APPLY_PRODUCTION": platform["automation_identities"][
                "infrastructure-live-apply-production"
            ],
        }
        source_commit = "c" * 40
        record = CI.build_bootstrap_account_handoff(
            platform, values, source_commit
        )
        self.assertEqual(
            CI.bootstrap_account_handoff_errors(
                record, platform, values, source_commit
            ),
            [],
        )
        reordered = dict(reversed(list(platform.items())))
        self.assertEqual(
            CI.build_bootstrap_account_handoff(
                reordered, values, source_commit
            )["platform_contract_sha256"],
            record["platform_contract_sha256"],
        )
        canonical_fixture = {
            "contract_version": "1.5.0",
            "organization_id": "1",
            "state": {"primary_location": "US"},
            "unicode": "λ",
        }
        self.assertEqual(
            CI.build_bootstrap_account_handoff(
                canonical_fixture, values, source_commit
            )["platform_contract_sha256"],
            "sha256:b375ee572e6274f25c9be5e6c76dda6690ceb64a059a92c80cd9036d8931e613",
        )

        record["state_buckets"]["production"] = "redacted-substitution"
        errors = CI.bootstrap_account_handoff_errors(
            record, platform, values, source_commit
        )
        self.assertEqual(
            errors,
            [
                "[ACCOUNT-HANDOFF-MISMATCH] bootstrap account handoff differs "
                "from applied platform output"
            ],
        )
        self.assertNotIn("redacted-substitution", "\n".join(errors))

    def test_bootstrap_account_handoff_requires_a_clean_full_commit(self) -> None:
        clean = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        revision = subprocess.CompletedProcess(
            [], 0, stdout=f"{'d' * 40}\n", stderr=""
        )
        with mock.patch.object(CI.subprocess, "run", side_effect=[clean, revision]):
            self.assertEqual(CI.bootstrap_source_commit(ROOT), "d" * 40)

        dirty = subprocess.CompletedProcess(
            [], 0, stdout="?? unreviewed-output.json\n", stderr=""
        )
        with mock.patch.object(CI.subprocess, "run", return_value=dirty):
            with self.assertRaisesRegex(ValueError, "ACCOUNT-HANDOFF-SOURCE-DIRTY"):
                CI.bootstrap_source_commit(ROOT)

    def test_bootstrap_account_handoff_cannot_be_catalog_authored(self) -> None:
        catalog = {
            "infrastructure-live": {
                "BOOTSTRAP_ACCOUNT_HANDOFF_JSON": '{"schema_version":1}'
            }
        }
        with mock.patch.object(CI, "run_json", return_value=catalog):
            with self.assertRaisesRegex(ValueError, "free-form catalog input"):
                CI.compile_payload(ROOT, stage="bootstrap")

    def test_bootstrap_v15_full_export_requires_applied_v14_handoff(self) -> None:
        platform = self.staged_v15_contract()
        catalog = {
            repository: {}
            for repository in (
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            )
        }
        catalog["bootstrap"]["ENABLE_BUILDKITE_WIF"] = "false"
        outputs = {"platform_contract": {"value": platform}}
        with mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]):
            with self.assertRaisesRegex(ValueError, "requires applied handoff 1.4.0"):
                CI.compile_payload(ROOT, stage="full")

    def test_bootstrap_v15_exports_source_contract_and_applied_cache_identities(
        self,
    ) -> None:
        platform = self.staged_v15_contract()
        handoff = self.staged_v14_handoff(platform)
        catalog = {
            repository: {}
            for repository in (
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            )
        }
        catalog["bootstrap"]["ENABLE_BUILDKITE_WIF"] = "false"
        catalog["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"] = "{}"
        catalog["mindclade-internal-monorepo"].update(
            {
                name: f"env:{name}"
                for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.4.0"]
            }
        )
        outputs = {"platform_contract": {"value": platform}}
        with (
            mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]),
            mock.patch.object(
                CI, "resolve_environment", side_effect=lambda value: value
            ),
            mock.patch.object(
                CI, "dr_evidence_environment_contract", return_value={}
            ),
            mock.patch.object(
                CI, "bootstrap_source_commit", return_value="c" * 40
            ),
        ):
            payload = CI.compile_payload(
                ROOT, stage="full", applied_handoff=handoff
            )

        self.assertEqual(
            json.loads(payload["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"]),
            platform["github"]["bazel_cache_identity"],
        )
        for name in CI.BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES:
            self.assertEqual(
                payload["mindclade-internal-monorepo"][name],
                handoff.variables[name],
            )
        account_handoff = json.loads(
            payload["infrastructure-live"]["BOOTSTRAP_ACCOUNT_HANDOFF_JSON"]
        )
        self.assertEqual(account_handoff["bootstrap_source_commit"], "c" * 40)
        self.assertEqual(
            account_handoff["state_buckets"],
            {
                "development": payload["infrastructure-live"][
                    "TFSTATE_BUCKET_DEVELOPMENT"
                ],
                "staging": payload["infrastructure-live"][
                    "TFSTATE_BUCKET_STAGING"
                ],
                "production": payload["infrastructure-live"][
                    "TFSTATE_BUCKET_PRODUCTION"
                ],
            },
        )

    def test_bootstrap_v15_stage_exports_only_the_cache_source_contract(self) -> None:
        platform = self.staged_v15_contract()
        catalog = {
            repository: {}
            for repository in (
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            )
        }
        catalog["bootstrap"]["ENABLE_BUILDKITE_WIF"] = "false"
        catalog["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"] = "{}"
        catalog["mindclade-internal-monorepo"].update(
            {
                name: f"env:{name}"
                for name in CI.BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES
            }
        )
        catalog["mindclade-internal-monorepo"]["BAZEL_REMOTE_CACHE_STATE"] = (
            "blocked"
        )
        outputs = {"platform_contract": {"value": platform}}
        with (
            mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]),
            mock.patch.object(
                CI, "resolve_environment", side_effect=lambda value: value
            ),
            mock.patch.object(
                CI, "bootstrap_source_commit", return_value="c" * 40
            ),
        ):
            payload = CI.compile_payload(ROOT, stage="bootstrap")

        self.assertEqual(
            json.loads(payload["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"]),
            platform["github"]["bazel_cache_identity"],
        )
        self.assertEqual(
            json.loads(
                payload["infrastructure-live"]["BOOTSTRAP_ACCOUNT_HANDOFF_JSON"]
            )["bootstrap_source_commit"],
            "c" * 40,
        )
        for name in CI.BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES:
            self.assertNotIn(name, payload["mindclade-internal-monorepo"])
        self.assertEqual(
            payload["mindclade-internal-monorepo"]["BAZEL_REMOTE_CACHE_STATE"],
            "blocked",
        )

    def test_legacy_platform_prunes_cache_fields_and_rejects_v14_handoff(self) -> None:
        platform = self.deployed_v12_contract()
        variables = {
            name: f"value-{name.lower()}"
            for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.3.0"]
        }
        handoff = CI.AppliedHandoff(
            contract_version="1.3.0", variables=variables
        )
        catalog = {
            repository: {}
            for repository in (
                ".github",
                ".github-private",
                "github-config",
                "bootstrap",
                "infrastructure-live",
                "gitops",
                "mindclade-internal-monorepo",
            )
        }
        catalog["bootstrap"]["ENABLE_BUILDKITE_WIF"] = "false"
        catalog["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"] = "{}"
        catalog["mindclade-internal-monorepo"].update(
            {
                name: f"env:{name}"
                for name in (
                    CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.3.0"]
                    | CI.BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES
                )
            }
        )
        outputs = {"platform_contract": {"value": platform}}
        with (
            mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]),
            mock.patch.object(
                CI, "resolve_environment", side_effect=lambda value: value
            ),
        ):
            payload = CI.compile_payload(
                ROOT, stage="full", applied_handoff=handoff
            )
        self.assertNotIn("BAZEL_CACHE_IDENTITY_JSON", payload["infrastructure-live"])
        self.assertNotIn(
            "BOOTSTRAP_ACCOUNT_HANDOFF_JSON", payload["infrastructure-live"]
        )
        for name in CI.BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES:
            self.assertNotIn(name, payload["mindclade-internal-monorepo"])

        v14_handoff = CI.AppliedHandoff(
            contract_version="1.4.0",
            variables={
                name: f"value-{name.lower()}"
                for name in CI.APPLIED_HANDOFF_VARIABLES_BY_VERSION["1.4.0"]
            },
        )
        with mock.patch.object(CI, "run_json", side_effect=[catalog, outputs]):
            with self.assertRaisesRegex(ValueError, "requires applied handoff 1.3.0"):
                CI.compile_payload(
                    ROOT, stage="full", applied_handoff=v14_handoff
                )

    def test_dr_evidence_environment_handoff_is_exact_and_applied(self) -> None:
        pool = "projects/123456789/locations/global/workloadIdentityPools/github"
        principals = {}
        for repository in (
            "bootstrap",
            "github-config",
            "infrastructure-live",
            "gitops",
        ):
            for environment in ("scratch", "staging"):
                principals[f"{repository}:{environment}"] = (
                    f"principal://iam.googleapis.com/{pool}/subject/dr-evidence:"
                    f"repo:mindclade@316676129/{repository}@1333792222:"
                    f"environment:{environment}"
                )
        github = {
            "dr_evidence_identity": {
                "workload_identity_provider": f"{pool}/providers/gh-dr-evidence",
                "job_workflow_ref": (
                    "mindclade/.github/.github/workflows/"
                    "reusable-dr-evidence.yml@refs/tags/v5.0.0"
                ),
                "principals": principals,
            }
        }
        applied = {
            "SA_DR_EVIDENCE_WRITER": (
                "sa-dr-evidence-writer@mc-common-ci.iam.gserviceaccount.com"
            ),
            "DR_EVIDENCE_PROJECT": "mc-common-security",
            "DR_EVIDENCE_BUCKET": "mc-dr-evidence-123456",
        }

        with mock.patch.dict(CI.os.environ, applied, clear=False):
            values = CI.dr_evidence_environment_contract(
                github, pool, "mindclade"
            )
        self.assertEqual(values["WIF_PROVIDER_DR_EVIDENCE"], f"{pool}/providers/gh-dr-evidence")
        self.assertEqual(values["DR_EVIDENCE_BUCKET"], applied["DR_EVIDENCE_BUCKET"])

        del github["dr_evidence_identity"]["principals"]["gitops:staging"]
        with mock.patch.dict(CI.os.environ, applied, clear=False):
            with self.assertRaisesRegex(ValueError, "principal inventory"):
                CI.dr_evidence_environment_contract(github, pool, "mindclade")

    def test_bootstrap_stage_omits_deferred_catalog_inputs(self) -> None:
        config = {
            ".github": {
                "PIN_AUDIT_APP_ID": "env:PIN_AUDIT_APP_ID",
                "RELEASE_GOVERNANCE_READER_APP_ID": (
                    "env:RELEASE_GOVERNANCE_READER_APP_ID"
                ),
            },
            ".github-private": {},
            "github-config": {
                "ORGANIZATION": "mindclade",
                "BILLING_EMAIL": "env:BILLING_EMAIL",
                "ENVIRONMENT_PROJECT_IDS": "{}",
                "TF_PLAN_APP_ID": "env:TF_PLAN_APP_ID",
            },
            "bootstrap": {
                "GH_ORGANIZATION": "mindclade",
                "AUTOMATION_SECRET_LOCATION": "us-central1",
                "ENABLE_BUILDKITE_WIF": "false",
                "KMS_PROTECTION_LEVEL": "SOFTWARE",
                "NONCURRENT_VERSION_COUNT": "100",
                "NONCURRENT_VERSION_DAYS": "90",
                "PRESERVE_LEGACY_EU_STATE_REPLICAS": (
                    "env:PRESERVE_LEGACY_EU_STATE_REPLICAS"
                ),
                "STATE_SOFT_DELETE_DAYS": "30",
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
                "RELEASE_GOVERNANCE_READER_APP_ID": (
                    "env:RELEASE_GOVERNANCE_READER_APP_ID"
                ),
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
        self.assertNotIn(
            "RELEASE_GOVERNANCE_READER_APP_ID",
            selected["mindclade-internal-monorepo"],
        )
        self.assertEqual(selected["github-config"]["ENVIRONMENT_PROJECT_IDS"], "{}")
        self.assertEqual(
            selected["bootstrap"]["SECURITY_CONTACT"], "env:SECURITY_CONTACT"
        )
        self.assertEqual(
            {
                name: selected["bootstrap"][name]
                for name in (
                    "AUTOMATION_SECRET_LOCATION",
                    "KMS_PROTECTION_LEVEL",
                    "NONCURRENT_VERSION_COUNT",
                    "NONCURRENT_VERSION_DAYS",
                    "PRESERVE_LEGACY_EU_STATE_REPLICAS",
                    "STATE_SOFT_DELETE_DAYS",
                )
            },
            {
                "AUTOMATION_SECRET_LOCATION": "us-central1",
                "KMS_PROTECTION_LEVEL": "SOFTWARE",
                "NONCURRENT_VERSION_COUNT": "100",
                "NONCURRENT_VERSION_DAYS": "90",
                "PRESERVE_LEGACY_EU_STATE_REPLICAS": (
                    "env:PRESERVE_LEGACY_EU_STATE_REPLICAS"
                ),
                "STATE_SOFT_DELETE_DAYS": "30",
            },
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

    def test_idp_billing_project_is_passed_to_gcloud(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="{}", stderr="")
        with mock.patch.object(IDP.subprocess, "run", return_value=completed) as run:
            IDP.gcloud_json(
                ["identity", "users", "describe", "person@example.com"],
                "mc-b-cicd-fb7649",
            )

        command = run.call_args.args[0]
        self.assertIn("--billing-project=mc-b-cicd-fb7649", command)
        self.assertEqual(
            command[-2:],
            ["--format=json", "--billing-project=mc-b-cicd-fb7649"],
        )

    def test_empty_team_regression_is_detected(self) -> None:
        current = {"team_members": {"security": [{"username": "alice"}]}}
        generated = {"team_members": {"security": []}}
        self.assertEqual(
            IDP.empty_team_regressions(current, generated), ["security (had 1)"]
        )

    def test_idp_team_inventory_is_explicit(self) -> None:
        expected = {
            "biosecurity",
            "bootstrap-reviewers",
            "data-platform",
            "engineering",
            "incident-command",
            "infrastructure",
            "legal",
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

    def test_independent_review_teams_must_be_disjoint_and_nonempty(self) -> None:
        mappings = {team: f"{team}@example.com" for team in ("legal", "platform", "security")}
        valid = {
            "team_members": {
                "legal": [{"username": "legal-reviewer"}],
                "platform": [{"username": "platform-reviewer"}],
                "security": [{"username": "security-reviewer"}],
            }
        }
        with mock.patch.object(IDP, "TEAM_GROUPS", mappings):
            IDP.validate_independent_review_membership(valid)
            overlapping = {
                "team_members": {
                    "legal": [{"username": "same-human"}],
                    "platform": [{"username": "platform-reviewer"}],
                    "security": [{"username": "same-human"}],
                }
            }
            with self.assertRaises(IDP.ExportError):
                IDP.validate_independent_review_membership(overlapping)
            empty = {
                "team_members": {
                    "legal": [],
                    "platform": [{"username": "platform-reviewer"}],
                    "security": [{"username": "security-reviewer"}],
                }
            }
            with self.assertRaises(IDP.ExportError):
                IDP.validate_independent_review_membership(empty)

    def test_access_expiry_warns_at_t14_and_expires_after_deadline(self) -> None:
        items = [
            {
                "id": "temporary",
                "principal": "robpearc",
                "repository": "bootstrap",
                "expires_at": "2026-11-18",
            }
        ]

        expired, upcoming = EXPIRY.evaluate(items, date(2026, 11, 4), 14)
        self.assertEqual(expired, [])
        self.assertEqual(len(upcoming), 1)

        expired, upcoming = EXPIRY.evaluate(items, date(2026, 11, 19), 14)
        self.assertEqual(len(expired), 1)
        self.assertEqual(upcoming, [])

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
