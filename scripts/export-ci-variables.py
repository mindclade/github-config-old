#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compile governed GitHub Actions variables from catalog and bootstrap outputs."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent

BUILDKITE_DEFERRED_VARIABLES = {
    "bootstrap": {
        "BUILDKITE_ORGANIZATION_ID",
        "BUILDKITE_PIPELINE_IDS_JSON",
        "BUILDKITE_PIPELINE_STEP_CONTRACTS_JSON",
    },
    "mindclade-internal-monorepo": {
        "BUILDKITE_ORGANIZATION_ID",
        "BUILDKITE_BUILD_PIPELINE_ID",
        "BUILDKITE_QUALIFICATION_PIPELINE_ID",
        "BUILDKITE_PROMOTION_PIPELINE_ID",
        "BUILDKITE_BUILDER_IDENTITY",
        "BUILDKITE_QUALIFIER_IDENTITY",
        "BUILDKITE_PROMOTER_IDENTITY",
    },
}

# Initial governance runs before GitHub Apps, normal-plane identities, attestors, and
# environment projects exist. Keep this allowlist deliberately small: platform-contract values
# are added after filtering, while every unavailable env: input is deferred to the full export.
BOOTSTRAP_STAGE_CATALOG_KEYS = {
    ".github": set(),
    ".github-private": set(),
    "github-config": {"ORGANIZATION", "BILLING_EMAIL", "ENVIRONMENT_PROJECT_IDS"},
    "bootstrap": {
        "RESOURCE_PREFIX",
        "GCP_REGION",
        "STATE_BUCKET_LOCATION",
        "STATE_KMS_LOCATION",
        "STATE_REPLICA_LOCATION",
        "STATE_REPLICA_KMS_LOCATION",
        "BREAK_GLASS_PRINCIPALS_JSON",
        "SECURITY_CONTACT",
        "ENABLE_BUILDKITE_WIF",
    },
    "infrastructure-live": {
        "ORG_POLICY_ACTIVATION_PHASE",
        "MONOREPO_ORG",
        "RESOURCE_PREFIX",
        "PRIMARY_REGION",
        "GPU_ZONE",
        "DOMAIN",
    },
    "gitops": {"MONOREPO_ORG"},
    "mindclade-internal-monorepo": {"ARTIFACT_REGISTRY_HOST"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", type=Path, default=ROOT.parent / "bootstrap")
    parser.add_argument(
        "--repo", default=os.environ.get("GH_REPO", "mindclade/github-config")
    )
    parser.add_argument(
        "--stage",
        choices=("bootstrap", "full"),
        default="full",
        help="bootstrap emits only initial-governance inputs; full remains fail-closed",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--set", action="store_true", help="set CI_VARIABLES with gh")
    mode.add_argument("--check", action="store_true", help="compare with GitHub")
    return parser.parse_args()


def run_json(command: list[str], *, cwd: Path | None = None) -> Any:
    result = subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=True
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{' '.join(command)} returned invalid JSON: {error}"
        ) from error


def resolve_environment(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: resolve_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_environment(item) for item in value]
    if isinstance(value, str) and value.startswith("env:"):
        name = value[4:]
        resolved = os.environ.get(name, "")
        if not resolved:
            raise ValueError(f"required operator environment variable is unset: {name}")
        return resolved
    return value


def require(mapping: dict[str, Any], key: str, label: str) -> Any:
    value = mapping.get(key)
    if value in (None, ""):
        raise ValueError(f"{label} is missing: {key}")
    return value


def configure_buildkite_phase(
    config: dict[str, dict[str, Any]], buildkite: dict[str, Any]
) -> str | None:
    enabled = buildkite.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("platform_contract.buildkite.enabled is not boolean")
    expected_flag = "true" if enabled else "false"
    catalog_flag = config.get("bootstrap", {}).get("ENABLE_BUILDKITE_WIF")
    if catalog_flag != expected_flag:
        raise ValueError(
            "catalog ENABLE_BUILDKITE_WIF does not match platform_contract.buildkite.enabled"
        )
    if not enabled:
        for repository, names in BUILDKITE_DEFERRED_VARIABLES.items():
            for name in names:
                config.get(repository, {}).pop(name, None)
        return None

    buildkite_pool = require(
        buildkite, "workload_identity_pool", "platform_contract.buildkite"
    )
    if not re.fullmatch(
        r"projects/[0-9]+/locations/global/workloadIdentityPools/buildkite",
        str(buildkite_pool),
    ):
        raise ValueError(
            "platform_contract Buildkite WIF pool has an invalid resource name"
        )
    return str(buildkite_pool)


def select_bootstrap_stage(
    config: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    selected = {
        repository: {
            name: value
            for name, value in config.get(repository, {}).items()
            if name in names
        }
        for repository, names in BOOTSTRAP_STAGE_CATALOG_KEYS.items()
    }
    # The eventual group mailbox is intentionally not assumed during bootstrap. Requiring
    # the current live value preserves Ring-0 alerting until the IdP-backed group exists.
    selected["bootstrap"]["SECURITY_CONTACT"] = "env:SECURITY_CONTACT"
    return selected


def github_repository_contract(
    github_contract: dict[str, Any],
) -> tuple[str, str, str]:
    organization = str(
        require(github_contract, "organization", "platform_contract.github")
    )
    identities = require(
        github_contract, "repository_identities", "platform_contract.github"
    )
    if not isinstance(identities, dict):
        raise ValueError("platform_contract.github.repository_identities is not an object")
    expected_repositories = {
        "bootstrap",
        "github-config",
        "infrastructure-live",
        "gitops",
        "mindclade-internal-monorepo",
    }
    if set(identities) != expected_repositories:
        difference = sorted(set(identities) ^ expected_repositories)
        raise ValueError(
            "platform_contract.github.repository_identities differs from the managed WIF "
            f"repository set: {difference}"
        )

    owner_ids: set[str] = set()
    repository_ids: dict[str, str] = {}
    for repository, identity in identities.items():
        if not isinstance(identity, dict):
            raise ValueError(
                f"platform_contract.github.repository_identities.{repository} is not an object"
            )
        expected_name = f"{organization}/{repository}"
        if identity.get("repository") != expected_name:
            raise ValueError(
                "platform_contract GitHub repository identity has an unexpected name: "
                f"{identity.get('repository', 'missing')}"
            )
        owner_id = str(
            require(identity, "repository_owner_id", f"GitHub identity {repository}")
        )
        repository_id = str(
            require(identity, "repository_id", f"GitHub identity {repository}")
        )
        if not owner_id.isdigit() or not repository_id.isdigit():
            raise ValueError(
                f"platform_contract GitHub identity IDs are not numeric: {repository}"
            )
        owner_ids.add(owner_id)
        repository_ids[repository] = repository_id
    if len(owner_ids) != 1:
        raise ValueError("platform_contract GitHub identities disagree on repository_owner_id")
    return (
        organization,
        owner_ids.pop(),
        json.dumps(repository_ids, sort_keys=True, separators=(",", ":")),
    )


def compile_payload(
    bootstrap: Path, *, stage: str = "full"
) -> dict[str, dict[str, Any]]:
    config = run_json(
        ["yq", "-o=json", ".", str(ROOT / "catalog/ci-variables.yaml")]
    )
    if not isinstance(config, dict):
        raise ValueError("ci-variables catalog is not an object")
    outputs = run_json(["terraform", f"-chdir={bootstrap}", "output", "-json"])
    if not outputs:
        raise ValueError("bootstrap has no outputs")
    platform = require(outputs, "platform_contract", "bootstrap output").get("value")
    if not isinstance(platform, dict):
        raise ValueError("bootstrap output platform_contract is not an object")
    if platform.get("contract_version") != "1.2.0":
        raise ValueError(
            f"unsupported bootstrap platform_contract version: {platform.get('contract_version', 'missing')}"
        )
    buildkite = require(platform, "buildkite", "platform_contract")
    if not isinstance(buildkite, dict):
        raise ValueError("platform_contract.buildkite is not an object")
    buildkite_pool = configure_buildkite_phase(config, buildkite)
    if stage == "bootstrap":
        config = select_bootstrap_stage(config)
    elif stage != "full":
        raise ValueError(f"unsupported CI variable export stage: {stage}")
    config = resolve_environment(config)

    state_contract = require(platform, "state", "platform_contract")
    github_contract = require(platform, "github", "platform_contract")
    if not isinstance(github_contract, dict):
        raise ValueError("platform_contract.github is not an object")
    github_organization, github_organization_id, github_repository_ids_json = (
        github_repository_contract(github_contract)
    )
    state = require(state_contract, "primary_buckets", "platform_contract.state")
    replicas = require(state_contract, "replica_buckets", "platform_contract.state")
    identities = require(platform, "automation_identities", "platform_contract")
    providers = require(
        github_contract, "workload_identity_providers", "platform_contract.github"
    )
    github_pool = require(
        github_contract, "workload_identity_pool", "platform_contract.github"
    )
    match = re.fullmatch(r"projects/([0-9]+)/.*", str(github_pool))
    if match is None:
        raise ValueError(
            "platform_contract GitHub WIF pool has an invalid resource name"
        )
    signer = require(github_contract, "artifact_signer", "platform_contract.github")

    def need(mapping: dict[str, Any], key: str, label: str) -> Any:
        return require(mapping, key, label)

    config["github-config"].update(
        {
            "ORGANIZATION": need(
                github_contract, "organization", "platform_contract.github"
            ),
            "TFSTATE_BUCKET": need(state, "github-config", "state.primary_buckets"),
            "WIF_POOL_PROJECT_NUMBER": match.group(1),
            "WIF_PROVIDER_PLAN": need(
                providers, "github-config", "GitHub WIF providers"
            ),
            "WIF_PROVIDER_APPLY": need(
                providers, "github-config", "GitHub WIF providers"
            ),
            "SA_GITHUB_CONFIG_PLAN": need(
                identities, "github-config-plan", "automation identities"
            ),
            "SA_GITHUB_CONFIG_APPLY": need(
                identities, "github-config-apply", "automation identities"
            ),
        }
    )
    config["bootstrap"].update(
        {
            "GCP_ORG_ID": str(need(platform, "organization_id", "platform_contract")),
            "BILLING_ACCOUNT": need(
                platform, "billing_account", "platform_contract"
            ),
            "GH_ORGANIZATION": github_organization,
            "GH_ORGANIZATION_ID": github_organization_id,
            "GH_REPOSITORY_IDS_JSON": github_repository_ids_json,
            "TFSTATE_BUCKET": need(state, "bootstrap", "state.primary_buckets"),
            "TFSTATE_REPLICA_BUCKET": need(
                replicas, "bootstrap", "state.replica_buckets"
            ),
            "WIF_PROVIDER_PLAN": need(providers, "bootstrap", "GitHub WIF providers"),
            "WIF_PROVIDER_APPLY": need(providers, "bootstrap", "GitHub WIF providers"),
            "SA_BOOTSTRAP_PLAN": need(
                identities, "bootstrap-plan", "automation identities"
            ),
            "SA_BOOTSTRAP_DRIFT": need(
                identities, "bootstrap-drift", "automation identities"
            ),
            "SA_BOOTSTRAP_APPLY": need(
                identities, "bootstrap-apply", "automation identities"
            ),
        }
    )
    infrastructure_live_values = {
        "GCP_ORG_ID": str(need(platform, "organization_id", "platform_contract")),
        "BILLING_ACCOUNT": need(platform, "billing_account", "platform_contract"),
        "BOOTSTRAP_SEED_PROJECT_ID": need(
            platform, "state_project_id", "platform_contract"
        ),
        "BOOTSTRAP_CICD_PROJECT_ID": need(
            platform, "federation_project_id", "platform_contract"
        ),
        "BOOTSTRAP_CICD_PROJECT_NUMBER": match.group(1),
        "WIF_POOL_GITHUB_NAME": github_pool,
        "WIF_PROVIDER_SIGNER": need(
            signer, "workload_identity_provider", "artifact signer"
        ),
        "ARTIFACT_SIGNER_PRINCIPAL": need(signer, "principal", "artifact signer"),
        "ARTIFACT_SIGNER_JOB_WORKFLOW_REF": need(
            signer, "job_workflow_ref", "artifact signer"
        ),
        "STATE_LOCATION": need(
            state_contract, "primary_location", "platform_contract.state"
        ),
        "SECRETS_PROJECT_ID": need(
            require(platform, "automation_secret", "platform_contract"),
            "project_id",
            "automation secret",
        ),
        "TFSTATE_BUCKET_DEVELOPMENT": need(
            state, "infrastructure-live-development", "state.primary_buckets"
        ),
        "TFSTATE_BUCKET_STAGING": need(
            state, "infrastructure-live-staging", "state.primary_buckets"
        ),
        "TFSTATE_BUCKET_PRODUCTION": need(
            state, "infrastructure-live-production", "state.primary_buckets"
        ),
        "WIF_PROVIDER_PLAN": need(
            providers, "infrastructure-live", "GitHub WIF providers"
        ),
        "WIF_PROVIDER_APPLY": need(
            providers, "infrastructure-live", "GitHub WIF providers"
        ),
        "SA_TF_LIVE_PLAN": need(
            identities, "infrastructure-live-plan", "automation identities"
        ),
        "SA_TF_LIVE_APPLY_FOUNDATION": need(
            identities,
            "infrastructure-live-apply-foundation",
            "automation identities",
        ),
        "SA_TF_LIVE_APPLY_DEVELOPMENT": need(
            identities,
            "infrastructure-live-apply-development",
            "automation identities",
        ),
        "SA_TF_LIVE_APPLY_STAGING": need(
            identities, "infrastructure-live-apply-staging", "automation identities"
        ),
        "SA_TF_LIVE_APPLY_PRODUCTION": need(
            identities,
            "infrastructure-live-apply-production",
            "automation identities",
        ),
    }
    if buildkite_pool is not None:
        infrastructure_live_values["BUILDKITE_WIF_POOL_NAME"] = buildkite_pool
    config["infrastructure-live"].update(infrastructure_live_values)
    config["gitops"]["WIF_PROVIDER_PLAN"] = need(
        providers, "gitops", "GitHub WIF providers"
    )
    config["mindclade-internal-monorepo"]["WIF_PROVIDER_SIGNER"] = need(
        signer, "workload_identity_provider", "artifact signer"
    )
    empty = [
        f"{repo}/{name}"
        for repo, values in config.items()
        for name, value in values.items()
        if value in (None, "")
    ]
    if empty:
        raise ValueError(f"required CI variable values are unset: {', '.join(empty)}")
    return config


def rendered(payload: dict[str, dict[str, Any]], *, compact: bool = False) -> str:
    if compact:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    args = parse_args()
    try:
        payload = compile_payload(args.bootstrap.resolve(), stage=args.stage)
        expected = rendered(payload)
        if args.set:
            subprocess.run(
                [
                    "gh",
                    "variable",
                    "set",
                    "CI_VARIABLES",
                    "--repo",
                    args.repo,
                    "--body",
                    rendered(payload, compact=True),
                ],
                check=True,
            )
        elif args.check:
            current = subprocess.run(
                ["gh", "variable", "get", "CI_VARIABLES", "--repo", args.repo],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            current_text = rendered(json.loads(current))
            if current_text != expected:
                sys.stdout.writelines(
                    difflib.unified_diff(
                        current_text.splitlines(keepends=True),
                        expected.splitlines(keepends=True),
                        fromfile="GitHub CI_VARIABLES",
                        tofile="compiled CI_VARIABLES",
                    )
                )
                return 1
        else:
            sys.stdout.write(expected)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
