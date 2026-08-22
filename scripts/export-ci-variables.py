#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compile governed GitHub Actions variables from catalog and bootstrap outputs."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parent.parent

SUPPORTED_BOOTSTRAP_CONTRACT_VERSIONS = {"1.2.0", "1.4.0", "1.5.0"}
BOOTSTRAP_ACCOUNT_HANDOFF_CONTRACT_VERSION = 1
BOOTSTRAP_ACCOUNT_HANDOFF_PLATFORM_VERSION = "1.5.0"
BOOTSTRAP_ACCOUNT_HANDOFF_SCHEMA = (
    ROOT / "contracts/bootstrap-account-handoff.schema.json"
)
BOOTSTRAP_ACCOUNT_HANDOFF_STATE_BUCKETS = {
    "development": "TFSTATE_BUCKET_DEVELOPMENT",
    "staging": "TFSTATE_BUCKET_STAGING",
    "production": "TFSTATE_BUCKET_PRODUCTION",
}
BOOTSTRAP_ACCOUNT_HANDOFF_SERVICE_ACCOUNTS = {
    "plan": "SA_TF_LIVE_PLAN",
    "foundation": "SA_TF_LIVE_APPLY_FOUNDATION",
    "development": "SA_TF_LIVE_APPLY_DEVELOPMENT",
    "staging": "SA_TF_LIVE_APPLY_STAGING",
    "production": "SA_TF_LIVE_APPLY_PRODUCTION",
}

APPLIED_HANDOFF_V13_VARIABLES = {
    "CI_PROJECT_ID",
    "SA_ARC_CANARY",
    "SA_ARTIFACT_BUILDER",
    "SA_ARTIFACT_QUALIFICATION_READER",
    "SA_ARTIFACT_QUALIFIER",
    "SA_ARTIFACT_SIGNER",
    "SA_ARTIFACT_PROMOTER",
    "SA_GITOPS_RENDER",
    "SA_GITOPS_VERIFIER",
    "WIF_PROVIDER_PRODUCTION_QUALIFICATION",
    "SA_PRODUCTION_QUALIFICATION_EVALUATOR",
    "SA_PRODUCTION_QUALIFICATION_READER",
    "SA_PRODUCTION_QUALIFICATION_WRITER",
    "PRODUCTION_QUALIFICATION_PROJECT",
    "PRODUCTION_QUALIFICATION_BUCKET",
    "PRODUCTION_QUALIFICATION_PRIVATE_KEY_SECRET",
    "PRODUCTION_ELIGIBILITY_SIGNING_KEY_ID",
    "PRODUCTION_ELIGIBILITY_KMS_KEY_VERSION",
    "BINAUTHZ_BUILD_ATTESTOR_PROJECT",
    "BINAUTHZ_BUILD_ATTESTOR",
    "BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT",
    "BINAUTHZ_QUALIFICATION_ATTESTOR",
    "BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT",
    "BINAUTHZ_DEPLOYMENT_ATTESTOR",
    "BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION",
}
BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES = {
    "WIF_PROVIDER_BAZEL_CACHE",
    "SA_BAZEL_CACHE_READER",
    "SA_BAZEL_CACHE_WRITER",
}
APPLIED_HANDOFF_VARIABLES_BY_VERSION = {
    "1.3.0": APPLIED_HANDOFF_V13_VARIABLES,
    "1.4.0": APPLIED_HANDOFF_V13_VARIABLES | BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES,
}
APPLIED_HANDOFF_SOURCE_UNITS = {
    "automation_iam": "1-org/automation-iam",
    "gitops_identities": "5-workloads/shared/control-plane-identities",
    "binary_authorization": "5-workloads/production/binary-authorization",
    "qualification_evidence": "5-workloads/shared/production-qualification-evidence",
}


class AppliedHandoff(NamedTuple):
    contract_version: str
    variables: dict[str, str]

BUILDKITE_DEFERRED_VARIABLES: dict[str, set[str]] = {}

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
        "RESIDENCY_PROFILE",
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
        "RESIDENCY_PROFILE",
        "PRIMARY_REGION",
        "GPU_ZONE",
        "DR_REGION",
        "DR_GPU_ZONE",
        "DOMAIN",
    },
    "gitops": {"MONOREPO_ORG"},
    "mindclade-internal-monorepo": {
        "ARTIFACT_REGISTRY_HOST",
        "ARTIFACT_REGISTRY_DR_HOST",
        "BAZEL_REMOTE_CACHE_STATE",
    },
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
    parser.add_argument(
        "--applied-handoff",
        type=Path,
        help="Exact infrastructure-live applied control-plane handoff (full stage only).",
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


def bootstrap_source_commit(root: Path) -> str:
    """Return the exact clean bootstrap source commit used for applied output."""

    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError(
            "[ACCOUNT-HANDOFF-SOURCE-DIRTY] bootstrap checkout has changes or "
            "untracked files"
        )
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError(
            "[ACCOUNT-HANDOFF-SOURCE] bootstrap checkout does not resolve to one "
            "full commit SHA"
        )
    return commit


def build_bootstrap_account_handoff(
    contract: dict[str, Any], values: dict[str, Any], source_commit: str
) -> dict[str, Any]:
    """Build the canonical non-secret record from applied bootstrap output."""

    if contract.get("contract_version") != BOOTSTRAP_ACCOUNT_HANDOFF_PLATFORM_VERSION:
        raise ValueError(
            "[ACCOUNT-HANDOFF-BOOTSTRAP] bootstrap platform contract version differs"
        )
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("[ACCOUNT-HANDOFF-SOURCE] bootstrap source commit is invalid")
    encoded = json.dumps(
        contract, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return {
        "schema_version": BOOTSTRAP_ACCOUNT_HANDOFF_CONTRACT_VERSION,
        "bootstrap_contract_version": BOOTSTRAP_ACCOUNT_HANDOFF_PLATFORM_VERSION,
        "bootstrap_source_commit": source_commit,
        "platform_contract_sha256": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        "state_location": values["STATE_LOCATION"],
        "state_buckets": {
            name: values[variable]
            for name, variable in BOOTSTRAP_ACCOUNT_HANDOFF_STATE_BUCKETS.items()
        },
        "service_accounts": {
            name: values[variable]
            for name, variable in BOOTSTRAP_ACCOUNT_HANDOFF_SERVICE_ACCOUNTS.items()
        },
    }


def bootstrap_account_handoff_errors(
    handoff: object,
    contract: dict[str, Any],
    values: dict[str, Any],
    source_commit: str,
) -> list[str]:
    """Validate exact producer parity without returning record values."""

    try:
        schema = json.loads(
            BOOTSTRAP_ACCOUNT_HANDOFF_SCHEMA.read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError):
        return [
            "[ACCOUNT-HANDOFF-CONTRACT] bootstrap account handoff schema is unavailable"
        ]
    if any(Draft202012Validator(schema).iter_errors(handoff)):
        return [
            "[ACCOUNT-HANDOFF-SCHEMA] bootstrap account handoff violates its schema"
        ]
    try:
        expected = build_bootstrap_account_handoff(
            contract, values, source_commit
        )
    except (KeyError, TypeError, ValueError):
        return [
            "[ACCOUNT-HANDOFF-SOURCE] bootstrap account handoff source is invalid"
        ]
    if handoff != expected:
        return [
            "[ACCOUNT-HANDOFF-MISMATCH] bootstrap account handoff differs from "
            "applied platform output"
        ]
    return []


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


def load_applied_handoff(path: Path) -> AppliedHandoff:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"applied control-plane handoff is unreadable: {error}") from error
    required = {
        "contract_version",
        "producer",
        "source_commit",
        "environment",
        "source_units",
        "variables",
        "credential_material_included",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("applied control-plane handoff field inventory is not exact")
    contract_version = payload["contract_version"]
    expected_variables = (
        APPLIED_HANDOFF_VARIABLES_BY_VERSION.get(contract_version)
        if isinstance(contract_version, str)
        else None
    )
    if (
        expected_variables is None
        or payload["producer"] != "mindclade/infrastructure-live"
        or payload["environment"] != "production"
        or payload["credential_material_included"] is not False
        or re.fullmatch(r"[0-9a-f]{40}", str(payload["source_commit"])) is None
        or payload["source_units"] != APPLIED_HANDOFF_SOURCE_UNITS
    ):
        raise ValueError("applied control-plane handoff authority is invalid")
    variables = payload["variables"]
    if not isinstance(variables, dict) or set(variables) != expected_variables:
        raise ValueError("applied control-plane handoff variable inventory is not exact")
    for name, value in variables.items():
        if not isinstance(value, str) or not value or re.search(
            r"(?i)(mock|unknown|placeholder|example|changeme|known after apply)", value
        ):
            raise ValueError(f"applied control-plane handoff value is invalid: {name}")
    return AppliedHandoff(contract_version=contract_version, variables=variables)


def apply_applied_handoff(
    config: dict[str, dict[str, Any]], handoff: AppliedHandoff
) -> None:
    variables = handoff.variables
    consumed: set[str] = set()
    for repository, values in config.items():
        for name, value in values.items():
            if value == f"env:{name}" and name in variables:
                config[repository][name] = variables[name]
                consumed.add(name)
    expected_consumed = APPLIED_HANDOFF_VARIABLES_BY_VERSION[handoff.contract_version]
    if consumed != expected_consumed:
        difference = sorted(consumed ^ expected_consumed)
        raise ValueError(
            "applied control-plane handoff/catalog projection differs: "
            + ", ".join(difference)
        )


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
    catalog_flag = config.get("bootstrap", {}).get("ENABLE_BUILDKITE_WIF")
    if catalog_flag != "false":
        raise ValueError(
            "catalog must permanently disable retired Buildkite federation"
        )
    if enabled or buildkite.get("workload_identity_pool") is not None or (
        buildkite.get("workload_identity_provider") is not None
    ):
        raise ValueError(
            "Buildkite is retired and must publish disabled with null pool and provider"
        )
    return None


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


def artifact_release_contract(
    github_contract: dict[str, Any], github_pool: str, organization: str
) -> dict[str, dict[str, str]]:
    identities = require(
        github_contract,
        "artifact_release_identities",
        "platform_contract.github",
    )
    workflows = {
        "canary": "reusable-arc-wif-canary.yml",
        "builder": "reusable-arc-oci-build.yml",
        "qualification-reader": "reusable-arc-oci-qualify.yml",
        "qualifier": "reusable-arc-qualification-attest.yml",
        "signer": "reusable-binauthz-sign.yml",
        "promoter": "reusable-gitops-promote.yml",
    }
    fields = {
        "workload_identity_provider",
        "principal",
        "subject",
        "workflow_ref",
        "job_workflow_ref",
    }
    if not isinstance(identities, dict) or set(identities) != set(workflows):
        raise ValueError("platform_contract ARC release identity inventory is not exact")
    for capability, workflow in workflows.items():
        identity = identities[capability]
        if not isinstance(identity, dict) or set(identity) != fields:
            raise ValueError(f"ARC release identity is not exact: {capability}")
        provider_id = (
            "gh-mindclade-internal-monorepo"
            if capability == "signer"
            else f"gh-arc-{capability}"
        )
        if identity.get("workload_identity_provider") != (
            f"{github_pool}/providers/{provider_id}"
        ):
            raise ValueError(f"ARC release provider differs: {capability}")
        suffix = (
            "environment:release"
            if capability in {"signer", "promoter"}
            else "ref:refs/heads/main"
        )
        subject = identity.get("subject")
        if not isinstance(subject, str) or re.fullmatch(
            rf"repo:{re.escape(organization)}@[0-9]+/"
            rf"mindclade-internal-monorepo@[0-9]+:{re.escape(suffix)}",
            subject,
        ) is None:
            raise ValueError(f"ARC release subject differs: {capability}")
        mapped_subject = subject if capability == "signer" else f"arc-{capability}:{subject}"
        if identity.get("principal") != (
            f"principal://iam.googleapis.com/{github_pool}/subject/{mapped_subject}"
        ):
            raise ValueError(f"ARC release principal differs: {capability}")
        if identity.get("workflow_ref") != (
            f"{organization}/mindclade-internal-monorepo/.github/workflows/"
            "release.yml@refs/heads/main"
        ):
            raise ValueError(f"ARC release caller differs: {capability}")
        workflow_version = "v5.0.0"
        if identity.get("job_workflow_ref") != (
            f"{organization}/.github/.github/workflows/{workflow}@refs/tags/"
            f"{workflow_version}"
        ):
            raise ValueError(f"ARC reusable workflow differs: {capability}")
    signer = require(github_contract, "artifact_signer", "platform_contract.github")
    if not isinstance(signer, dict) or signer != {
        field: identities["signer"][field]
        for field in ("workload_identity_provider", "principal", "job_workflow_ref")
    }:
        raise ValueError("legacy artifact_signer projection differs from signer capability")
    return identities


def production_qualification_identity_contract(
    github_contract: dict[str, Any], github_pool: str, organization: str
) -> dict[str, str]:
    identity = require(
        github_contract,
        "production_qualification_identity",
        "platform_contract.github",
    )
    fields = {
        "workload_identity_provider",
        "principal",
        "subject",
        "workflow_ref",
    }
    if not isinstance(identity, dict) or set(identity) != fields:
        raise ValueError("platform_contract production qualification identity is not exact")
    provider = f"{github_pool}/providers/gh-production-qualification"
    if identity["workload_identity_provider"] != provider:
        raise ValueError("platform_contract production qualification provider differs")
    subject = identity["subject"]
    if not isinstance(subject, str) or re.fullmatch(
        rf"repo:{re.escape(organization)}@[0-9]+/gitops@[0-9]+:environment:production",
        subject,
    ) is None:
        raise ValueError("platform_contract production qualification subject differs")
    if identity["principal"] != (
        f"principal://iam.googleapis.com/{github_pool}/subject/"
        f"production-qualification:{subject}"
    ):
        raise ValueError("platform_contract production qualification principal differs")
    if identity["workflow_ref"] != (
        f"{organization}/gitops/.github/workflows/"
        "production-qualification-evidence.yml@refs/heads/main"
    ):
        raise ValueError("platform_contract production qualification workflow differs")
    return identity


def bazel_cache_identity_contract(
    github_contract: dict[str, Any], github_pool: str, organization: str
) -> dict[str, Any]:
    identity = require(
        github_contract, "bazel_cache_identity", "platform_contract.github"
    )
    fields = {
        "workload_identity_provider",
        "repository",
        "repository_owner_id",
        "repository_id",
        "routes",
    }
    if not isinstance(identity, dict) or set(identity) != fields:
        raise ValueError("platform_contract Bazel cache identity is not exact")

    repository = f"{organization}/mindclade-internal-monorepo"
    if identity["workload_identity_provider"] != (
        f"{github_pool}/providers/gh-bazel-cache"
    ):
        raise ValueError("platform_contract Bazel cache provider differs")
    if identity["repository"] != repository:
        raise ValueError("platform_contract Bazel cache repository differs")

    repository_identities = require(
        github_contract, "repository_identities", "platform_contract.github"
    )
    monorepo_identity = require(
        repository_identities,
        "mindclade-internal-monorepo",
        "platform_contract.github.repository_identities",
    )
    if not isinstance(monorepo_identity, dict) or (
        identity["repository_owner_id"] != monorepo_identity.get("repository_owner_id")
        or identity["repository_id"] != monorepo_identity.get("repository_id")
    ):
        raise ValueError("platform_contract Bazel cache immutable IDs differ")

    presubmit = f"{repository}/.github/workflows/presubmit.yml"
    nightly = f"{repository}/.github/workflows/nightly.yml"
    expected_routes = {
        "pull-request-read": {
            "access": "read",
            "event_name": "pull_request",
            "ref_policy": "pull-request-merge",
            "workflow_path": presubmit,
        },
        "trusted-main-write": {
            "access": "write",
            "event_name": "push",
            "ref_policy": "protected-main",
            "workflow_path": presubmit,
        },
        "merge-group-write": {
            "access": "write",
            "event_name": "merge_group",
            "ref_policy": "protected-merge-queue",
            "workflow_path": presubmit,
        },
        "nightly-write": {
            "access": "write",
            "event_name": "schedule",
            "ref_policy": "protected-main",
            "workflow_path": nightly,
        },
    }
    routes = identity["routes"]
    route_fields = {
        "access",
        "event_name",
        "principal",
        "ref_policy",
        "workflow_path",
    }
    if not isinstance(routes, dict) or set(routes) != set(expected_routes):
        raise ValueError("platform_contract Bazel cache route inventory is not exact")
    for route, expected in expected_routes.items():
        value = routes[route]
        if not isinstance(value, dict) or set(value) != route_fields:
            raise ValueError(f"platform_contract Bazel cache route is not exact: {route}")
        if any(value.get(name) != expected_value for name, expected_value in expected.items()):
            raise ValueError(f"platform_contract Bazel cache route differs: {route}")
        if value["principal"] != (
            f"principal://iam.googleapis.com/{github_pool}/subject/bazel-cache:{route}"
        ):
            raise ValueError(f"platform_contract Bazel cache principal differs: {route}")
    return identity


def validate_applied_bazel_cache_handoff(
    handoff: AppliedHandoff, identity: dict[str, Any]
) -> None:
    variables = handoff.variables
    provider = variables["WIF_PROVIDER_BAZEL_CACHE"]
    if provider != identity["workload_identity_provider"]:
        raise ValueError("applied Bazel cache provider differs from bootstrap")
    project = variables["CI_PROJECT_ID"]
    expected_accounts = {
        "SA_BAZEL_CACHE_READER": (
            f"bazel-cache-reader@{project}.iam.gserviceaccount.com"
        ),
        "SA_BAZEL_CACHE_WRITER": (
            f"bazel-cache-writer@{project}.iam.gserviceaccount.com"
        ),
    }
    for name, expected in expected_accounts.items():
        if variables[name] != expected:
            raise ValueError(f"applied Bazel cache service account differs: {name}")


def dr_evidence_environment_contract(
    github_contract: dict[str, Any], github_pool: str, organization: str
) -> dict[str, str]:
    """Compile the protected-environment handoff from Ring 0 and applied live outputs."""
    identity = require(
        github_contract, "dr_evidence_identity", "platform_contract.github"
    )
    if not isinstance(identity, dict) or set(identity) != {
        "workload_identity_provider",
        "job_workflow_ref",
        "principals",
    }:
        raise ValueError("platform_contract DR evidence identity is not exact")

    provider = identity.get("workload_identity_provider")
    if provider != f"{github_pool}/providers/gh-dr-evidence":
        raise ValueError("platform_contract DR evidence provider differs")
    if identity.get("job_workflow_ref") != (
        f"{organization}/.github/.github/workflows/"
        "reusable-dr-evidence.yml@refs/tags/v5.0.0"
    ):
        raise ValueError("platform_contract DR evidence reusable workflow differs")

    repositories = ("bootstrap", "github-config", "infrastructure-live", "gitops")
    environments = ("scratch", "staging")
    expected_principals = {
        f"{repository}:{environment}"
        for repository in repositories
        for environment in environments
    }
    principals = identity.get("principals")
    if not isinstance(principals, dict) or set(principals) != expected_principals:
        raise ValueError("platform_contract DR evidence principal inventory is not exact")
    for key, principal in principals.items():
        repository, environment = key.split(":", 1)
        if not isinstance(principal, str) or re.fullmatch(
            rf"principal://iam\.googleapis\.com/{re.escape(github_pool)}/subject/"
            rf"dr-evidence:repo:{re.escape(organization)}@[0-9]+/"
            rf"{re.escape(repository)}@[0-9]+:environment:{re.escape(environment)}",
            principal,
        ) is None:
            raise ValueError(f"platform_contract DR evidence principal differs: {key}")

    values = {
        "WIF_PROVIDER_DR_EVIDENCE": str(provider),
        "SA_DR_EVIDENCE_WRITER": os.environ.get("SA_DR_EVIDENCE_WRITER", ""),
        "DR_EVIDENCE_PROJECT": os.environ.get("DR_EVIDENCE_PROJECT", ""),
        "DR_EVIDENCE_BUCKET": os.environ.get("DR_EVIDENCE_BUCKET", ""),
    }
    empty = [name for name, value in values.items() if not value]
    if empty:
        raise ValueError(
            "required applied DR evidence outputs are unset: " + ", ".join(empty)
        )
    if re.fullmatch(
        r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com",
        values["SA_DR_EVIDENCE_WRITER"],
    ) is None:
        raise ValueError("SA_DR_EVIDENCE_WRITER is not a service-account email")
    if re.fullmatch(
        r"[a-z][a-z0-9-]{4,28}[a-z0-9]", values["DR_EVIDENCE_PROJECT"]
    ) is None:
        raise ValueError("DR_EVIDENCE_PROJECT is not a Google Cloud project ID")
    if re.fullmatch(
        r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", values["DR_EVIDENCE_BUCKET"]
    ) is None:
        raise ValueError("DR_EVIDENCE_BUCKET is not a Cloud Storage bucket name")
    return values


def compile_payload(
    bootstrap: Path,
    *,
    stage: str = "full",
    applied_handoff: AppliedHandoff | None = None,
) -> dict[str, dict[str, Any]]:
    config = run_json(
        ["yq", "-o=json", ".", str(ROOT / "catalog/ci-variables.yaml")]
    )
    if not isinstance(config, dict):
        raise ValueError("ci-variables catalog is not an object")
    if "BOOTSTRAP_ACCOUNT_HANDOFF_JSON" in config.get("infrastructure-live", {}):
        raise ValueError(
            "BOOTSTRAP_ACCOUNT_HANDOFF_JSON must not be a free-form catalog input"
        )
    outputs = run_json(["terraform", f"-chdir={bootstrap}", "output", "-json"])
    if not outputs:
        raise ValueError("bootstrap has no outputs")
    platform = require(outputs, "platform_contract", "bootstrap output").get("value")
    if not isinstance(platform, dict):
        raise ValueError("bootstrap output platform_contract is not an object")
    contract_version = platform.get("contract_version")
    if contract_version not in SUPPORTED_BOOTSTRAP_CONTRACT_VERSIONS:
        raise ValueError(
            f"unsupported bootstrap platform_contract version: {contract_version or 'missing'}"
        )
    buildkite = require(platform, "buildkite", "platform_contract")
    if not isinstance(buildkite, dict):
        raise ValueError("platform_contract.buildkite is not an object")
    buildkite_pool = configure_buildkite_phase(config, buildkite)
    if stage == "bootstrap":
        if applied_handoff is not None:
            raise ValueError("applied handoff is only valid for the full export stage")
        config = select_bootstrap_stage(config)
    elif stage == "full":
        if contract_version == "1.5.0":
            if applied_handoff is None or applied_handoff.contract_version != "1.4.0":
                raise ValueError(
                    "bootstrap 1.5.0 full export requires applied handoff 1.4.0"
                )
        else:
            for name in BAZEL_CACHE_APPLIED_HANDOFF_VARIABLES:
                config["mindclade-internal-monorepo"].pop(name, None)
            config["infrastructure-live"].pop("BAZEL_CACHE_IDENTITY_JSON", None)
            if (
                applied_handoff is not None
                and applied_handoff.contract_version != "1.3.0"
            ):
                raise ValueError(
                    "bootstrap 1.2.0/1.4.0 full export requires applied handoff 1.3.0"
                )
    else:
        raise ValueError(f"unsupported CI variable export stage: {stage}")
    if applied_handoff is not None:
        apply_applied_handoff(config, applied_handoff)
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
    release_identities: dict[str, dict[str, str]] | None = None
    production_qualification_identity: dict[str, str] | None = None
    bazel_cache_identity: dict[str, Any] | None = None
    if contract_version in {"1.4.0", "1.5.0"}:
        release_identities = artifact_release_contract(
            github_contract, str(github_pool), github_organization
        )
        production_qualification_identity = (
            production_qualification_identity_contract(
                github_contract, str(github_pool), github_organization
            )
        )
        signer = release_identities["signer"]
    else:
        signer = require(
            github_contract, "artifact_signer", "platform_contract.github"
        )
        if not isinstance(signer, dict):
            raise ValueError("platform_contract.github.artifact_signer is not an object")
        expected_signer = {
            "workload_identity_provider": (
                f"{github_pool}/providers/gh-mindclade-internal-monorepo"
            ),
            "job_workflow_ref": (
                f"{github_organization}/.github/.github/workflows/"
                "reusable-binauthz-sign.yml@refs/tags/v3.0.0"
            ),
        }
        for name, expected in expected_signer.items():
            if signer.get(name) != expected:
                raise ValueError(f"legacy artifact signer {name} differs")
        principal = signer.get("principal")
        if not isinstance(principal, str) or re.fullmatch(
            rf"principal://iam\.googleapis\.com/{re.escape(str(github_pool))}/subject/"
            rf"repo:{re.escape(github_organization)}@[0-9]+/"
            r"mindclade-internal-monorepo@[0-9]+:environment:release",
            principal,
        ) is None:
            raise ValueError("legacy artifact signer principal differs")
    if contract_version == "1.5.0":
        bazel_cache_identity = bazel_cache_identity_contract(
            github_contract, str(github_pool), github_organization
        )
        if stage == "full":
            if applied_handoff is None:
                raise ValueError("applied Bazel cache handoff is missing")
            validate_applied_bazel_cache_handoff(
                applied_handoff, bazel_cache_identity
            )
    if stage == "full" and contract_version in {"1.4.0", "1.5.0"}:
        config["github-config"]["DR_EVIDENCE_ENVIRONMENT_VARIABLES"] = json.dumps(
            dr_evidence_environment_contract(
                github_contract, str(github_pool), github_organization
            ),
            sort_keys=True,
            separators=(",", ":"),
        )

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
    if release_identities is not None:
        infrastructure_live_values["ARTIFACT_RELEASE_IDENTITIES_JSON"] = json.dumps(
            release_identities, sort_keys=True, separators=(",", ":")
        )
    if production_qualification_identity is not None:
        infrastructure_live_values[
            "PRODUCTION_QUALIFICATION_IDENTITY_JSON"
        ] = json.dumps(
            production_qualification_identity,
            sort_keys=True,
            separators=(",", ":"),
        )
    if bazel_cache_identity is not None:
        infrastructure_live_values["BAZEL_CACHE_IDENTITY_JSON"] = json.dumps(
            bazel_cache_identity, sort_keys=True, separators=(",", ":")
        )
    if contract_version == BOOTSTRAP_ACCOUNT_HANDOFF_PLATFORM_VERSION:
        source_commit = bootstrap_source_commit(bootstrap)
        account_handoff = build_bootstrap_account_handoff(
            platform, infrastructure_live_values, source_commit
        )
        account_handoff_errors = bootstrap_account_handoff_errors(
            account_handoff,
            platform,
            infrastructure_live_values,
            source_commit,
        )
        if account_handoff_errors:
            raise ValueError("; ".join(account_handoff_errors))
        infrastructure_live_values["BOOTSTRAP_ACCOUNT_HANDOFF_JSON"] = json.dumps(
            account_handoff, sort_keys=True, separators=(",", ":")
        )
    config["infrastructure-live"].update(infrastructure_live_values)
    config["gitops"]["WIF_PROVIDER_PLAN"] = need(
        providers, "gitops", "GitHub WIF providers"
    )
    monorepo_provider_names = {
        "canary": "WIF_PROVIDER_ARC_CANARY",
        "builder": "WIF_PROVIDER_ARC_BUILDER",
        "qualification-reader": "WIF_PROVIDER_ARC_QUALIFICATION_READER",
        "qualifier": "WIF_PROVIDER_ARC_QUALIFIER",
        "signer": "WIF_PROVIDER_SIGNER",
        "promoter": "WIF_PROVIDER_ARC_PROMOTER",
    }
    if release_identities is None:
        config["mindclade-internal-monorepo"]["WIF_PROVIDER_SIGNER"] = need(
            signer, "workload_identity_provider", "artifact signer"
        )
    else:
        for capability, variable_name in monorepo_provider_names.items():
            identity = require(
                release_identities,
                capability,
                "platform_contract.github.artifact_release_identities",
            )
            if not isinstance(identity, dict):
                raise ValueError(f"ARC release identity is not an object: {capability}")
            config["mindclade-internal-monorepo"][variable_name] = need(
                identity,
                "workload_identity_provider",
                f"ARC release identity {capability}",
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
        applied_handoff = (
            load_applied_handoff(args.applied_handoff.resolve())
            if args.applied_handoff is not None
            else None
        )
        payload = compile_payload(
            args.bootstrap.resolve(),
            stage=args.stage,
            applied_handoff=applied_handoff,
        )
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
