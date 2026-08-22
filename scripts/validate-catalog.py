#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

#
"""Validate Mindclade's GitHub governance catalog without cloud credentials."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from governance_contracts import (
    evidence_gated_ruleset_errors,
    required_check_readiness_errors,
    resting_ruleset_errors,
)
from terraform_contracts import (
    RequiredStatusRulesetContract,
    TerraformContractError,
    literal_toset_strings,
    local_value,
    load_terraform,
    validate_drift_access_expiry,
    validate_drift_readiness,
    validate_bazel_cache_ci_variable_contract,
    validate_environment_handoff,
    validate_import_contract,
    validate_oidc_module,
    validate_release_tag_contracts,
    validate_required_status_ruleset,
)

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "catalog"
SCHEMA = CAT / "schema"
EXPECTED_REPOS = {
    ".github",
    ".github-private",
    "github-config",
    "bootstrap",
    "infrastructure-live",
    "gitops",
    "mindclade-internal-monorepo",
}
EXPECTED_CLASSES = {
    "enterprise-control",
    "production-control",
    "source-monorepo",
    "public-sdk",
    "archive",
}
EXPECTED_ENVIRONMENTS = {
    "development",
    "scratch",
    "staging",
    "production",
    "plan",
    "governance",
    "bootstrap",
    "bootstrap-recovery-read",
    "release",
    "nix-cache-publication",
    "workflow-release-platform",
    "workflow-release-security",
    "repository-observability",
    "repository-maintenance",
    "break-glass",
}
EXPECTED_RULESETS = {
    "baseline-all",
    "legal-policy-paths",
    "merge-queue",
    "protected-paths",
    "release-authority-paths",
    "release-tag-creation",
    "push-blocklist",
    "required-checks-bootstrap",
    "required-checks-gitops",
    "required-checks-go",
    "required-checks-github-config",
    "required-checks-infra-static",
    "required-checks-mixed",
    "required-checks-nix",
    "required-checks-tf",
    "required-checks-tf-static",
    "required-checks-tf-tests",
    "ruleset-workflows",
    "tag-protection",
}
EXPECTED_RULESET_ENFORCEMENT = {
    "baseline-all": "active",
    "legal-policy-paths": "evaluate",
    "merge-queue": "active",
    "protected-paths": "active",
    "release-authority-paths": "active",
    "release-tag-creation": "evaluate",
    "push-blocklist": "active",
    "required-checks-bootstrap": "evaluate",
    "required-checks-gitops": "active",
    "required-checks-go": "evaluate",
    "required-checks-github-config": "evaluate",
    "required-checks-nix": "evaluate",
    "required-checks-tf": "active",
    "required-checks-tf-static": "active",
    "required-checks-tf-tests": "active",
    "ruleset-workflows": "evaluate",
    "tag-protection": "active",
}
REQUIRED_STATUS_RULESET_CONTRACTS = (
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-bootstrap.tf",
        resource_name="required_checks_bootstrap",
        ruleset_name="required-checks-bootstrap",
        repositories=("bootstrap",),
        contexts=("plan / verdict",),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-github-config.tf",
        resource_name="required_checks_github_config",
        ruleset_name="required-checks-github-config",
        repositories=("github-config",),
        contexts=("fmt", "validate", "plan / verdict"),
        lifecycle_condition=(
            'local.enforcement["required-checks-github-config"] != "active" || '
            "var.github_config_verdict_observed"
        ),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-gitops.tf",
        resource_name="required_checks_gitops",
        ruleset_name="required-checks-gitops",
        repositories=("gitops",),
        contexts=(
            "contract",
            "lint",
            "schema",
            "policy",
            "exemptions",
            "promotion-integrity",
            "repository-invariants",
        ),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-go.tf",
        resource_name="required_checks_go",
        ruleset_name="required-checks-go",
        language_profiles=("go", "mixed"),
        contexts=("ci / build", "codeql / analyze (go)"),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-infra-static.tf",
        resource_name="required_checks_infra_static",
        ruleset_name="required-checks-infra-static",
        repositories=("mindclade-internal-monorepo",),
        contexts=("infra-static",),
    ),
    RequiredStatusRulesetContract(
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
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-nix.tf",
        resource_name="required_checks_nix",
        ruleset_name="required-checks-nix",
        repositories=(
            ".github",
            ".github-private",
            "bootstrap",
            "github-config",
            "gitops",
            "infrastructure-live",
            "mindclade-internal-monorepo",
        ),
        contexts=("nix / verdict",),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-tf.tf",
        resource_name="required_checks_tf",
        ruleset_name="required-checks-tf",
        repositories=("infrastructure-live",),
        contexts=("fmt", "validate", "plan"),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-tf.tf",
        resource_name="required_checks_tf_static",
        ruleset_name="required-checks-tf-static",
        repositories=("github-config", "infrastructure-live"),
        contexts=("tflint", "checkov"),
    ),
    RequiredStatusRulesetContract(
        path="modules/rulesets/required-checks-tf.tf",
        resource_name="required_checks_tf_tests",
        ruleset_name="required-checks-tf-tests",
        repositories=("github-config",),
        contexts=("test",),
    ),
)
EXPECTED_IDP_GROUPS = {
    "biosecurity": "biosecurity-review@{domain}",
    "bootstrap-reviewers": "github-bootstrap-reviewers@{domain}",
    "data-platform": "eng-data@{domain}",
    "engineering": "eng-all@{domain}",
    "platform": "eng-platform@{domain}",
    "research": "eng-research@{domain}",
    "security": "eng-security@{domain}",
}
EXPECTED_DEFERRED_IDP_TEAMS = {
    "incident-command",
    "infrastructure",
    "legal",
    "model-serving",
    "model-training",
    "product",
    "release",
}
PROPERTY_FIELDS = {
    "mindclade_repository_class": "repository_class",
    "mindclade_owner_team": "owner_team",
    "mindclade_criticality": "criticality",
    "mindclade_data_classification": "data_classification",
    "mindclade_production_authority": "production_authority",
    "mindclade_ci_profile": "ci_profile",
    "mindclade_language_profile": "language_profile",
    "mindclade_lifecycle": "lifecycle",
}
UNIVERSAL_OIDC_CLAIMS = {
    "repository_owner_id",
    "repository_id",
    "repository",
    "workflow_ref",
    "ref",
}
REQUIRED_WIF_CLAIMS = UNIVERSAL_OIDC_CLAIMS | {"event_name"}
FORBIDDEN_ORG_SUBJECT_CLAIMS = {"environment", "job_workflow_ref", "job_workflow_sha"}
REQUIRED_CI_VARIABLES = {
    ".github": {
        "ESTATE_OBSERVER_APP_ID": "env:ESTATE_OBSERVER_APP_ID",
        "REF_JANITOR_APP_ID": "env:REF_JANITOR_APP_ID",
    },
    "github-config": {
        "BILLING_EMAIL": "env:BILLING_EMAIL",
        "GOVERNANCE_CONNECTED_DRIFT": "false",
    },
    "bootstrap": {
        "ENABLE_BUILDKITE_WIF": "false",
        "GCP_REGION": "us-central1",
        "RESIDENCY_PROFILE": "us-only-v1",
        "SECURITY_CONTACT": "security@mindclade.com",
        "STATE_BUCKET_LOCATION": "US",
        "STATE_KMS_LOCATION": "us",
        "STATE_REPLICA_LOCATION": "us-east4",
        "STATE_REPLICA_KMS_LOCATION": "us-east4",
    },
    "infrastructure-live": {
        "BAZEL_CACHE_IDENTITY_JSON": "{}",
        "CLOUD_IDENTITY_CUSTOMER_ID": "env:CLOUD_IDENTITY_CUSTOMER_ID",
        "DR_GPU_ZONE": "us-east4-b",
        "DR_REGION": "us-east4",
        "ORG_POLICY_ACTIVATION_PHASE": "baseline",
        "PRIMARY_REGION": "us-central1",
        "GPU_ZONE": "us-central1-b",
        "RESIDENCY_PROFILE": "us-only-v1",
    },
    "gitops": {
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR",
        "SA_GITOPS_RENDER": "env:SA_GITOPS_RENDER",
        "SA_GITOPS_VERIFIER": "env:SA_GITOPS_VERIFIER",
        "SA_PRODUCTION_QUALIFICATION_EVALUATOR": "env:SA_PRODUCTION_QUALIFICATION_EVALUATOR",
        "PRODUCTION_ELIGIBILITY_SIGNING_KEY_ID": "env:PRODUCTION_ELIGIBILITY_SIGNING_KEY_ID",
        "PRODUCTION_ELIGIBILITY_KMS_KEY_VERSION": "env:PRODUCTION_ELIGIBILITY_KMS_KEY_VERSION",
        "PRODUCTION_ELIGIBILITY_URL": "https://mindclade.studio",
    },
    "mindclade-internal-monorepo": {
        "ARTIFACT_REGISTRY_DR_HOST": "us-east4-docker.pkg.dev",
        "ARTIFACT_REGISTRY_HOST": "us-central1-docker.pkg.dev",
        "CI_PROJECT_ID": "env:CI_PROJECT_ID",
        "WIF_PROVIDER_BAZEL_CACHE": "env:WIF_PROVIDER_BAZEL_CACHE",
        "SA_BAZEL_CACHE_READER": "env:SA_BAZEL_CACHE_READER",
        "SA_BAZEL_CACHE_WRITER": "env:SA_BAZEL_CACHE_WRITER",
        "SA_ARC_CANARY": "env:SA_ARC_CANARY",
        "SA_ARTIFACT_BUILDER": "env:SA_ARTIFACT_BUILDER",
        "SA_ARTIFACT_QUALIFICATION_READER": "env:SA_ARTIFACT_QUALIFICATION_READER",
        "SA_ARTIFACT_QUALIFIER": "env:SA_ARTIFACT_QUALIFIER",
        "SA_ARTIFACT_PROMOTER": "env:SA_ARTIFACT_PROMOTER",
        "BINAUTHZ_BUILD_ATTESTOR_PROJECT": "env:BINAUTHZ_BUILD_ATTESTOR_PROJECT",
        "BINAUTHZ_BUILD_ATTESTOR": "env:BINAUTHZ_BUILD_ATTESTOR",
        "BINAUTHZ_BUILD_ATTESTOR_KEY_VERSION": "env:BINAUTHZ_BUILD_ATTESTOR_KEY_VERSION",
        "BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT": "env:BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT",
        "BINAUTHZ_QUALIFICATION_ATTESTOR": "env:BINAUTHZ_QUALIFICATION_ATTESTOR",
        "BINAUTHZ_QUALIFICATION_ATTESTOR_KEY_VERSION": "env:BINAUTHZ_QUALIFICATION_ATTESTOR_KEY_VERSION",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION": (
            "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION"
        ),
        "SA_ARTIFACT_SIGNER": "env:SA_ARTIFACT_SIGNER",
        "ARC_PROMOTER_APP_ID": "env:ARC_PROMOTER_APP_ID",
        "ARC_PROMOTER_SECRET_PROJECT": "env:ARC_PROMOTER_SECRET_PROJECT",
        "ARC_PROMOTER_PRIVATE_KEY_SECRET": "env:ARC_PROMOTER_PRIVATE_KEY_SECRET",
        "ARC_PROMOTER_PRIVATE_KEY_VERSION": "env:ARC_PROMOTER_PRIVATE_KEY_VERSION",
    },
}
ROLE_RANK = {"pull": 0, "triage": 1, "push": 2, "maintain": 3, "admin": 4}
errors: list[str] = []


def load_yaml(name: str) -> Any:
    path = CAT / name
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        errors.append(f"{name}: cannot parse YAML: {exc}")
        return None


def err(message: str) -> None:
    errors.append(message)


# Schema-backed core catalogs.
for stem in (
    "repositories",
    "teams",
    "access",
    "adoption-inventory",
    "environments",
    "control-plane-apps",
    "connected-resource-exceptions",
    "governance-activation",
    "required-check-readiness",
):
    data = load_yaml(f"{stem}.yaml")
    try:
        schema = json.loads(
            (SCHEMA / f"{stem}.schema.json").read_text(encoding="utf-8")
        )
    except Exception as exc:
        err(f"{stem}: cannot read schema: {exc}")
        continue
    for issue in Draft202012Validator(schema).iter_errors(data):
        location = "/".join(map(str, issue.absolute_path)) or "<root>"
        err(f"{stem}: {location}: {issue.message}")

repos = load_yaml("repositories.yaml") or {}
teams = load_yaml("teams.yaml") or {}
access = load_yaml("access.yaml") or {}
environments = load_yaml("environments.yaml") or {}
classes = load_yaml("repository-classes.yaml") or {}
actions = load_yaml("actions-policy.yaml") or {}
oidc = load_yaml("oidc-policy.yaml") or {}
properties = load_yaml("custom-properties.yaml") or {}
rulesets = load_yaml("rulesets.yaml") or {}
runner_groups = load_yaml("runner-groups.yaml") or {}
github_apps = load_yaml("github-apps.yaml") or {}
control_plane_apps = load_yaml("control-plane-apps.yaml") or {}
exceptions = load_yaml("access-exceptions.yaml") or []
ci_variables = load_yaml("ci-variables.yaml") or {}
governance_activation = load_yaml("governance-activation.yaml") or {}
required_check_readiness = load_yaml("required-check-readiness.yaml") or {}
adoption_inventory = load_yaml("adoption-inventory.yaml") or {}
connected_exceptions = load_yaml("connected-resource-exceptions.yaml") or {}
try:
    repository_maintenance = json.loads(
        (CAT / "repository-maintenance.json").read_text(encoding="utf-8")
    )
    repository_maintenance_schema = json.loads(
        (SCHEMA / "repository-maintenance.schema.json").read_text(encoding="utf-8")
    )
    for issue in Draft202012Validator(repository_maintenance_schema).iter_errors(
        repository_maintenance
    ):
        location = "/".join(map(str, issue.absolute_path)) or "<root>"
        err(f"repository-maintenance: {location}: {issue.message}")
except Exception as exc:
    err(f"repository-maintenance: cannot read contract: {exc}")
    repository_maintenance = {}

idp_mappings_path = ROOT / "idp" / "mappings.yaml"
try:
    idp_mappings = yaml.safe_load(idp_mappings_path.read_text(encoding="utf-8")) or {}
except Exception as exc:  # pragma: no cover - diagnostic path
    err(f"idp/mappings.yaml: cannot parse YAML: {exc}")
    idp_mappings = {}
try:
    idp_schema = json.loads(
        (SCHEMA / "idp-mappings.schema.json").read_text(encoding="utf-8")
    )
    for issue in Draft202012Validator(idp_schema).iter_errors(idp_mappings):
        location = "/".join(map(str, issue.absolute_path)) or "<root>"
        err(f"idp/mappings.yaml: {location}: {issue.message}")
except Exception as exc:
    err(f"idp/mappings.yaml: cannot read schema: {exc}")

if set(repos) != EXPECTED_REPOS:
    err(f"repository estate differs: {sorted(set(repos) ^ EXPECTED_REPOS)}")
if set(classes) != EXPECTED_CLASSES:
    err(f"repository classes differ: {sorted(set(classes) ^ EXPECTED_CLASSES)}")
if set(environments) != EXPECTED_ENVIRONMENTS:
    err(
        f"environment inventory differs: {sorted(set(environments) ^ EXPECTED_ENVIRONMENTS)}"
    )
if set(access) != EXPECTED_REPOS:
    err(
        f"access catalog must cover every managed repository: {sorted(set(access) ^ EXPECTED_REPOS)}"
    )
if set(rulesets) != EXPECTED_RULESETS:
    err(
        f"ruleset inventory differs from implementation: {sorted(set(rulesets) ^ EXPECTED_RULESETS)}"
    )
for message in resting_ruleset_errors(rulesets, EXPECTED_RULESET_ENFORCEMENT):
    err(message)

expected_copilot_exception_repositories = {
    ".github",
    "github-config",
    "infrastructure-live",
    "gitops",
    "mindclade-internal-monorepo",
}
copilot_exceptions = connected_exceptions.get("repository_environments", [])
copilot_keys = [
    (item.get("repository"), item.get("name"))
    for item in copilot_exceptions
    if isinstance(item, dict)
]
if len(copilot_keys) != len(set(copilot_keys)):
    err("connected resource exceptions contain duplicate repository environments")
if {repository for repository, name in copilot_keys if name == "copilot"} != expected_copilot_exception_repositories:
    err("Copilot platform-managed environment exceptions must cover the exact observed estate")
if any(repository not in repos for repository, _ in copilot_keys):
    err("connected resource exception names an unmanaged repository")

tag_exceptions = connected_exceptions.get("tag_refs", [])
if tag_exceptions:
    err("connected resource tag exceptions must be empty after rescue-tag cleanup")

activation_enforcement = governance_activation.get("ruleset_enforcement", {})
for name in (
    "baseline-all",
    "merge-queue",
    "protected-paths",
    "release-tag-creation",
    "required-checks-bootstrap",
    "required-checks-github-config",
    "required-checks-go",
    "required-checks-infra-static",
    "required-checks-mixed",
    "required-checks-nix",
    "ruleset-workflows",
):
    if activation_enforcement.get(name) != rulesets.get(name, {}).get("enforcement"):
        err(f"governance activation evidence disagrees with ruleset {name}")
activation_gates = governance_activation.get("gates", {})
all_activation_gates_qualified = bool(activation_gates) and all(
    value == "qualified" for value in activation_gates.values()
)
if (governance_activation.get("qualification") == "qualified") != all_activation_gates_qualified:
    err("governance activation qualification must equal the complete gate set")
for message in evidence_gated_ruleset_errors(rulesets, activation_gates):
    err(message)
ruleset_contexts = {
    contract.ruleset_name: contract.contexts
    for contract in REQUIRED_STATUS_RULESET_CONTRACTS
}
for message in required_check_readiness_errors(
    required_check_readiness,
    activation_gates,
    ruleset_contexts,
):
    err(message)
expected_runner_group = {
    "visibility": "selected",
    "allowsPublicRepositories": False,
    "restrictedToWorkflows": True,
    "repositories": ["mindclade-internal-monorepo"],
    "workflows": [
        "mindclade/mindclade-internal-monorepo/.github/workflows/release.yml@refs/heads/main"
    ],
}
if runner_groups != {"mindclade-arc-artifact-authority": expected_runner_group}:
    err("ARC artifact-authority runner group contract is not exact")
if set(github_apps) != {
    "mindclade-arc",
    "mindclade-estate-observer",
    "mindclade-policy-sync",
    "mindclade-ref-janitor",
    "mindclade-release-promoter",
    "mindclade-production-qualification-reader",
}:
    err("GitHub App contract inventory is not exact")
else:
    if github_apps["mindclade-arc"].get("repositories") != [
        "mindclade-internal-monorepo"
    ]:
        err("ARC GitHub App must be selected to the monorepo only")
    if github_apps["mindclade-arc"].get("organizationPermissions") != {
        "selfHostedRunners": "write"
    }:
        err("ARC GitHub App has an unexpected organization permission contract")
    if github_apps["mindclade-arc"].get("repositoryPermissions") != {
        "actions": "read",
        "metadata": "read",
    }:
        err("ARC GitHub App has an unexpected repository permission contract")
    promoter = github_apps["mindclade-release-promoter"]
    if promoter.get("repositories") != ["gitops"]:
        err("release promoter App must be selected to gitops only")
    if promoter.get("repositoryPermissions") != {
        "contents": "write",
        "metadata": "read",
        "pullRequests": "write",
    }:
        err("release promoter App has an unexpected repository permission contract")
    if promoter.get("organizationPermissions") != {}:
        err("release promoter App must not have organization permissions")
    qualification = github_apps["mindclade-production-qualification-reader"]
    if set(qualification.get("repositories", [])) != EXPECTED_REPOS:
        err("production qualification App must select exactly the seven managed repositories")
    if qualification.get("repositoryPermissions") != {
        "actions": "read",
        "contents": "read",
        "metadata": "read",
    }:
        err("production qualification App has an unexpected repository permission contract")
    if qualification.get("organizationPermissions") != {}:
        err("production qualification App must not have organization permissions")
    policy_sync = github_apps["mindclade-policy-sync"]
    if set(policy_sync.get("repositories", [])) != EXPECTED_REPOS - {".github"}:
        err("policy sync App must select exactly the six policy-consumer repositories")
    if policy_sync.get("repositoryPermissions") != {
        "contents": "write",
        "metadata": "read",
        "pullRequests": "write",
    }:
        err("policy sync App has an unexpected repository permission contract")
    if policy_sync.get("organizationPermissions") != {}:
        err("policy sync App must not have organization permissions")
    observer = github_apps["mindclade-estate-observer"]
    if set(observer.get("repositories", [])) != EXPECTED_REPOS:
        err("estate observer App must select exactly the seven managed repositories")
    if observer.get("repositoryPermissions") != {
        "actions": "read",
        "checks": "read",
        "contents": "read",
        "metadata": "read",
        "pullRequests": "read",
    } or observer.get("organizationPermissions") != {}:
        err("estate observer App permission contract is not exact and read-only")
    janitor = github_apps["mindclade-ref-janitor"]
    if set(janitor.get("repositories", [])) != EXPECTED_REPOS:
        err("ref janitor App must select exactly the seven managed repositories")
    if janitor.get("repositoryPermissions") != {
        "contents": "write",
        "metadata": "read",
        "pullRequests": "read",
    } or janitor.get("organizationPermissions") != {}:
        err("ref janitor App permission contract is not exact")

if set(repository_maintenance.get("repositories", {})) != EXPECTED_REPOS:
    err("repository maintenance policy must cover exactly the seven managed repositories")
for repository, maintenance in repository_maintenance.get("repositories", {}).items():
    if maintenance.get("protected_branches") != ["main"]:
        err(f"{repository}: ref janitor must protect exactly main by branch name")
    if maintenance.get("branch_retention_days", 0) < 7 or maintenance.get("tag_retention_days", 0) < 7:
        err(f"{repository}: ref janitor retention must be at least seven days")
    try:
        patterns = [re.compile(value) for value in maintenance.get("allowed_tag_patterns", [])]
    except re.error as exc:
        err(f"{repository}: ref janitor tag pattern is invalid: {exc}")
    else:
        if not any(pattern.fullmatch("v1.2.3") for pattern in patterns):
            err(f"{repository}: semantic release tags must be preserved")

expected_control_repositories = sorted(EXPECTED_REPOS)
expected_control_permissions = {
    "mindclade-github-config-plan": {
        "capability": "plan",
        "workflow_mutation_allowed": False,
        "permission_nonmutating": False,
        "organization_permissions": {
            "members": "read",
            "organization_actions_variables": "read",
            "organization_administration": "write",
            "organization_custom_properties": "read",
            "organization_self_hosted_runners": "read",
        },
        "repository_permissions": {
            "actions": "read",
            "actions_variables": "read",
            "administration": "read",
            "environments": "read",
            "metadata": "read",
            "repository_custom_properties": "read",
            "vulnerability_alerts": "read",
        },
        "credential": {
            "app_id_variable": "TF_PLAN_APP_ID",
            "private_key_secret": "TF_GITHUB_PLAN_APP_PEM",
            "protected_environment": "plan",
        },
    },
    "mindclade-github-config-apply": {
        "capability": "apply",
        "workflow_mutation_allowed": True,
        "permission_nonmutating": False,
        "organization_permissions": {
            "members": "write",
            "organization_actions_variables": "write",
            "organization_administration": "write",
            "organization_custom_properties": "admin",
            "organization_self_hosted_runners": "write",
        },
        "repository_permissions": {
            "actions": "write",
            "actions_variables": "write",
            "administration": "write",
            "environments": "write",
            "metadata": "read",
            "repository_custom_properties": "write",
            "vulnerability_alerts": "write",
        },
        "credential": {
            "app_id_variable": "TF_APPLY_APP_ID",
            "private_key_secret": "TF_GITHUB_APPLY_APP_PEM",
            "protected_environment": "governance",
        },
    },
}
if control_plane_apps.get("organization") != "mindclade":
    err("control-plane Apps must be owned by the canonical mindclade organization")
declared_control_apps = control_plane_apps.get("apps", {})
if set(declared_control_apps) != set(expected_control_permissions):
    err("control-plane GitHub App inventory is not exact")
for name, expected in expected_control_permissions.items():
    app = declared_control_apps.get(name, {})
    if sorted(app.get("repositories", [])) != expected_control_repositories:
        err(f"{name}: installation selection must contain exactly the managed estate")
    if app.get("repository_selection") != "selected":
        err(f"{name}: repository selection must be selected, never all")
    if app.get("webhook_active") is not False or app.get("events") != []:
        err(f"{name}: webhooks and events must be disabled")
    for field, value in expected.items():
        if app.get(field) != value:
            err(f"{name}: {field} differs from the least-privilege contract")
plan_exception = str(
    declared_control_apps.get("mindclade-github-config-plan", {}).get(
        "permission_exception", ""
    )
)
if "organization_administration write" not in plan_exception:
    err("plan App must document GitHub's organization-ruleset read permission exception")
if set(properties) != set(PROPERTY_FIELDS):
    err(
        f"custom-property inventory differs: {sorted(set(properties) ^ set(PROPERTY_FIELDS))}"
    )

# Teams and hierarchy.
for name, cfg in teams.items():
    parent = cfg.get("parent")
    if parent is not None and parent not in teams:
        err(f"team {name}: unknown parent {parent}")
for start in teams:
    seen: set[str] = set()
    current = start
    while current is not None:
        if current in seen:
            err(f"team hierarchy cycle includes {current}")
            break
        seen.add(current)
        current = teams.get(current, {}).get("parent")

# The mapping document is the exporter's sole group-address authority. Deferred teams are
# explicit activation blockers; the validator never guesses their directory addresses.
idp_groups = idp_mappings.get("groups", {})
idp_exported_teams = {
    name for name, config in idp_groups.items() if config.get("status") == "mapped"
}
idp_deferred_teams = {
    name for name, config in idp_groups.items() if config.get("status") == "deferred"
}
if idp_exported_teams != set(EXPECTED_IDP_GROUPS):
    err(
        "verified IdP group inventory differs: "
        f"{sorted(idp_exported_teams ^ set(EXPECTED_IDP_GROUPS))}"
    )
for name, address in EXPECTED_IDP_GROUPS.items():
    if idp_groups.get(name, {}).get("directory_group") != address:
        err(f"IdP group {name}: directory address differs from verified source")
if idp_deferred_teams != EXPECTED_DEFERRED_IDP_TEAMS:
    err(
        "deferred IdP team inventory differs: "
        f"{sorted(idp_deferred_teams ^ EXPECTED_DEFERRED_IDP_TEAMS)}"
    )
for name in idp_deferred_teams:
    if idp_groups.get(name, {}).get("directory_group") is not None:
        err(f"IdP group {name}: deferred teams must not carry a guessed address")
if idp_exported_teams | idp_deferred_teams != set(teams):
    err(
        "IdP mapped/deferred inventory differs from catalog/teams.yaml: "
        f"{sorted((idp_exported_teams | idp_deferred_teams) ^ set(teams))}"
    )
mapped_github_teams = {
    str(config.get("github_team", ""))
    for config in idp_groups.values()
    if isinstance(config, dict)
}
if mapped_github_teams != set(teams):
    err(
        "idp/mappings.yaml GitHub team inventory differs from catalog/teams.yaml: "
        f"{sorted(mapped_github_teams ^ set(teams))}"
    )

# The solo-founder reviewer is deliberately standalone and read-only. The shared `plan`
# environment couples the three control repositories, so every grant and review surface is
# asserted exactly to prevent this exception from expanding silently.
bootstrap_reviewer = teams.get("bootstrap-reviewers", {})
if bootstrap_reviewer.get("privacy") != "closed" or bootstrap_reviewer.get(
    "parent"
) is not None:
    err("team bootstrap-reviewers must remain closed and standalone")
bootstrap_reviewer_access = {
    repository: grants["bootstrap-reviewers"]
    for repository, grants in access.items()
    if "bootstrap-reviewers" in grants
}
expected_bootstrap_reviewer_access = {
    "bootstrap": "pull",
    "github-config": "pull",
    "infrastructure-live": "pull",
}
if bootstrap_reviewer_access != expected_bootstrap_reviewer_access:
    err(
        "bootstrap-reviewers access must be exactly read-only on bootstrap, "
        "github-config, and infrastructure-live"
    )
bootstrap_reviewer_environments = {
    name
    for name, config in environments.items()
    if "bootstrap-reviewers" in config.get("reviewer_teams", [])
}
if bootstrap_reviewer_environments != {
    "plan",
    "bootstrap",
    "bootstrap-recovery-read",
}:
    err(
        "bootstrap-reviewers must review exactly plan, bootstrap, and "
        "bootstrap-recovery-read"
    )
if idp_groups.get("bootstrap-reviewers") != {
    "github_team": "bootstrap-reviewers",
    "status": "mapped",
    "directory_group": "github-bootstrap-reviewers@{domain}",
}:
    err(
        "idp/mappings.yaml must map bootstrap-reviewers exactly to its verified "
        "directory group"
    )

legal_team = teams.get("legal", {})
if legal_team.get("privacy") != "closed" or legal_team.get("parent") is not None:
    err("team legal must remain closed and standalone")
legal_access = {
    repository: grants["legal"]
    for repository, grants in access.items()
    if "legal" in grants
}
if legal_access != {repository: "pull" for repository in EXPECTED_REPOS}:
    err("legal access must be exactly read-only across the seven managed repositories")
if idp_groups.get("legal") != {
    "github_team": "legal",
    "status": "deferred",
    "directory_group": None,
}:
    err("legal must remain an explicit activation blocker until its IdP group is verified")

# Repository cross references, visibility and owner access.
for repo, cfg in repos.items():
    if cfg.get("default_branch") != "main":
        err(f"{repo}: default_branch must be main")
    owner = cfg.get("owner_team")
    repo_class = cfg.get("repository_class")
    if owner not in teams:
        err(f"{repo}: unknown owner_team {owner}")
    if repo_class not in classes:
        err(f"{repo}: unknown repository_class {repo_class}")
    for environment in cfg.get("environments", []):
        if environment not in environments:
            err(f"{repo}: unknown environment {environment}")
            continue
        for reviewer in environments[environment].get("reviewer_teams", []):
            if reviewer not in access.get(repo, {}):
                err(
                    f"{repo}/{environment}: reviewer team {reviewer} must have "
                    "repository access"
                )
    if cfg.get("visibility") == "public":
        err(f"{repo}: public visibility requires a separate release/security review")
    if cfg.get("production_authority") == "true" and repo_class not in {
        "enterprise-control",
        "production-control",
    }:
        err(f"{repo}: production authority is incompatible with class {repo_class}")
    owner_role = access.get(repo, {}).get(owner)
    if owner_role not in ROLE_RANK or ROLE_RANK[owner_role] < ROLE_RANK["maintain"]:
        err(f"{repo}: owner team {owner} must have maintain access")

for repo, grants in access.items():
    if repo not in repos:
        err(f"access: unknown repository {repo}")
    for team, role in grants.items():
        if team not in teams:
            err(f"access: unknown team {team}")
        if role not in ROLE_RANK:
            err(f"access: invalid role {repo}/{team}/{role}")
        if role == "admin":
            err(f"access: direct team admin is forbidden for {repo}/{team}")

# Environment governance.
for name, cfg in environments.items():
    for reviewer in cfg.get("reviewer_teams", []):
        if reviewer not in teams:
            err(f"environment {name}: unknown reviewer team {reviewer}")
    if name in {
        "scratch",
        "staging",
        "governance",
        "bootstrap",
        "bootstrap-recovery-read",
        "production",
        "release",
        "nix-cache-publication",
        "workflow-release-platform",
        "workflow-release-security",
        "repository-maintenance",
        "break-glass",
    }:
        if not cfg.get("protected_branches"):
            err(f"environment {name}: protected_branches must be true")
        if not cfg.get("prevent_self_review"):
            err(f"environment {name}: prevent_self_review must be true")
        if not cfg.get("reviewer_teams"):
            err(f"environment {name}: at least one reviewer team is required")
    if cfg.get("protected_branches") and cfg.get("custom_branch_policies"):
        err(
            f"environment {name}: protected and custom branch policies are mutually exclusive"
        )
plan_environment = environments.get("plan", {})
if plan_environment.get("protected_branches") or plan_environment.get(
    "custom_branch_policies"
):
    err("environment plan: branch filters must allow pull-request merge refs")
if "infrastructure" not in plan_environment.get("reviewer_teams", []):
    err("environment plan: infrastructure review is required")
if not plan_environment.get("prevent_self_review"):
    err("environment plan: self-review must be disabled")
expected_workflow_release_reviewers = {
    "workflow-release-platform": {"platform"},
    "workflow-release-security": {"security"},
}
github_environments = set(repos.get(".github", {}).get("environments", []))
expected_github_environments = set(expected_workflow_release_reviewers) | {
    "repository-observability",
    "repository-maintenance",
}
if expected_github_environments != github_environments:
    err(".github must declare the exact workflow-release and repository-operations environments")
for name, reviewers in expected_workflow_release_reviewers.items():
    environment = environments.get(name, {})
    if set(environment.get("reviewer_teams", [])) != reviewers:
        err(f"environment {name}: reviewer team must be exactly {sorted(reviewers)}")
    if not environment.get("protected_branches") or not environment.get(
        "prevent_self_review"
    ):
        err(f"environment {name}: protected main and no self-review are required")
observability_environment = environments.get("repository-observability", {})
if observability_environment.get("reviewer_teams") != [] or not observability_environment.get("protected_branches"):
    err("environment repository-observability must be protected-main and approval-free")
maintenance_environment = environments.get("repository-maintenance", {})
if set(maintenance_environment.get("reviewer_teams", [])) != {"platform", "security"} or maintenance_environment.get("wait_timer", 0) < 5:
    err("environment repository-maintenance requires platform and security review plus a wait timer")
nix_cache_environment = environments.get("nix-cache-publication", {})
if (
    set(nix_cache_environment.get("reviewer_teams", [])) != {"platform", "security"}
    or nix_cache_environment.get("wait_timer", 0) < 5
    or not nix_cache_environment.get("protected_branches")
    or nix_cache_environment.get("custom_branch_policies")
    or not nix_cache_environment.get("prevent_self_review")
):
    err(
        "environment nix-cache-publication requires protected main, platform and security "
        "review, no self-review, and a wait timer"
    )
cache_environment_repositories = {
    repository
    for repository, config in repos.items()
    if "nix-cache-publication" in config.get("environments", [])
}
if cache_environment_repositories != {"mindclade-internal-monorepo"}:
    err("nix-cache-publication must be assigned only to mindclade-internal-monorepo")
break_glass_environment = environments.get("break-glass", {})
if set(break_glass_environment.get("reviewer_teams", [])) != {"security"}:
    err(
        "environment break-glass: the closed security team must be the sole GitHub "
        "reviewer; GitHub does not retain secret teams as environment reviewers"
    )
for repository, config in repos.items():
    if "break-glass" in config.get("environments", []) and access.get(repository, {}).get(
        "incident-command"
    ) != "pull":
        err(
            f"{repository}/break-glass: secret incident-command requires read-only "
            "incident access"
        )
for repository in ("bootstrap", "github-config", "infrastructure-live"):
    if "plan" not in repos.get(repository, {}).get("environments", []):
        err(f"{repository} must declare the protected plan environment")
recovery_environment = environments.get("bootstrap-recovery-read", {})
if "bootstrap-recovery-read" not in repos.get("bootstrap", {}).get("environments", []):
    err("bootstrap must declare its bootstrap-recovery-read environment")
if not {"infrastructure", "security"}.issubset(
    set(recovery_environment.get("reviewer_teams", []))
):
    err(
        "environment bootstrap-recovery-read: infrastructure and security review are required"
    )

dr_evidence_repositories = {"bootstrap", "github-config", "infrastructure-live", "gitops"}
for repository in dr_evidence_repositories:
    declared = set(repos.get(repository, {}).get("environments", []))
    if not {"scratch", "staging"}.issubset(declared):
        err(f"{repository}: DR evidence requires scratch and staging environments")
expected_dr_reviewers = {
    "scratch": {"security"},
    # Staging is also the GitOps production rehearsal gate, so its effective reviewer set is
    # the union of DR security authority and platform promotion authority.
    "staging": {"platform", "security"},
}
for name, expected_reviewers in expected_dr_reviewers.items():
    environment = environments.get(name, {})
    if set(environment.get("reviewer_teams", [])) != expected_reviewers:
        err(
            f"environment {name}: reviewers must be exactly "
            f"{sorted(expected_reviewers)} for DR and promotion authority"
        )
    if not environment.get("protected_branches") or not environment.get("prevent_self_review"):
        err(f"environment {name}: DR evidence requires protected branches and no self-review")

# GitOps promotion jobs select an environment from the promotion target. Both pre-production
# rehearsal and production therefore need explicit protected-branch gates; otherwise a caller
# could name an environment that exists only as an unreviewed workflow string.
gitops_environments = set(repos.get("gitops", {}).get("environments", []))
for name in ("staging", "production"):
    cfg = environments.get(name, {})
    if name not in gitops_environments:
        err(f"gitops must declare the {name} promotion environment")
    if not cfg.get("protected_branches") or cfg.get("custom_branch_policies"):
        err(
            f"environment {name}: GitOps promotion must be restricted to protected branches"
        )
    if not cfg.get("prevent_self_review"):
        err(f"environment {name}: GitOps promotion must prevent self-review")
if "platform" not in environments.get("staging", {}).get("reviewer_teams", []):
    err("environment staging: platform review is required for GitOps promotion")
if not {"platform", "security"}.issubset(
    set(environments.get("production", {}).get("reviewer_teams", []))
):
    err(
        "environment production: platform and security review are required for GitOps promotion"
    )

# Custom properties are a compiled view of repository metadata.
for name, definition in properties.items():
    if definition.get("type") != "single_select":
        err(f"custom property {name}: only single_select is supported by this catalog")
    allowed = definition.get("values", [])
    if len(allowed) != len(set(allowed)):
        err(f"custom property {name}: allowed values are not unique")
    if definition.get("default_value") not in allowed:
        err(f"custom property {name}: default_value is not allowed")
    if definition.get("values_editable_by") != "org_actors":
        err(f"custom property {name}: values must be editable only by org actors")
    if not definition.get("required"):
        err(f"custom property {name}: must be required")
for repo, cfg in repos.items():
    for property_name, field in PROPERTY_FIELDS.items():
        value = cfg.get(field)
        if value not in properties.get(property_name, {}).get("values", []):
            err(f"{repo}: {field}={value!r} is not allowed by {property_name}")

# Actions policy.
if actions.get("enabled_repositories") != "all":
    err("actions policy: enabled_repositories must be all")
if actions.get("allowed_actions") != "selected":
    err("actions policy: allowed_actions must be selected")
if actions.get("default_workflow_permissions") != "read":
    err("actions policy: default GITHUB_TOKEN permission must be read")
if actions.get("can_approve_pull_request_reviews") is not False:
    err("actions policy: workflows may not approve pull requests by default")
if actions.get("sha_pinning_required") is not True:
    err("actions policy: immutable SHA pinning must be required")
patterns = actions.get("allowed_action_patterns", [])
if not patterns or len(patterns) != len(set(patterns)):
    err("actions policy: allowlist must be non-empty and unique")
for pattern in patterns:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./*-]+@[^\s]+", str(pattern)):
        err(f"actions policy: malformed allowlist pattern {pattern!r}")
if not any(
    str(item).startswith("mindclade/.github/.github/workflows/") for item in patterns
):
    err("actions policy: Mindclade shared workflows are not allowlisted")
if "mindclade/.github/actions/validate-repository-home@*" not in patterns:
    err("actions policy: the repository-home validator action is not allowlisted")

# OIDC policy. Optional claims must not be required organization-wide.
subject_claims = set(oidc.get("subject_claim_keys", []))
wif_claims = set(oidc.get("required_wif_attribute_claims", []))
if subject_claims != UNIVERSAL_OIDC_CLAIMS:
    err(
        f"OIDC subject claims must be {sorted(UNIVERSAL_OIDC_CLAIMS)}, got {sorted(subject_claims)}"
    )
if wif_claims != REQUIRED_WIF_CLAIMS:
    err(
        f"OIDC WIF claims must be {sorted(REQUIRED_WIF_CLAIMS)}, got {sorted(wif_claims)}"
    )
if subject_claims & FORBIDDEN_ORG_SUBJECT_CLAIMS:
    err(
        f"OIDC subject requires optional claims: {sorted(subject_claims & FORBIDDEN_ORG_SUBJECT_CLAIMS)}"
    )
if oidc.get("repository_opt_in") is not False:
    err("OIDC policy: managed repositories must use GitHub immutable default subjects")
for flag in (
    "require_immutable_default_subject",
    "require_trusted_owner_id",
    "require_repository_id",
    "require_workflow_ref",
    "require_ref",
    "require_protected_environment_for_sensitive_plan",
    "require_protected_environment_for_apply",
    "explicit_audience_required",
):
    if oidc.get(flag) is not True:
        err(f"OIDC policy: {flag} must be true")

# Ruleset inventory and references.
for name, cfg in rulesets.items():
    if cfg.get("enforcement") not in {"active", "evaluate", "disabled"}:
        err(f"ruleset {name}: invalid enforcement")
    for cls in cfg.get("classes", []):
        if cls not in classes:
            err(f"ruleset {name}: unknown class {cls}")
    for repo in cfg.get("repositories", []):
        if repo not in repos:
            err(f"ruleset {name}: unknown repository {repo}")
workflow_ref = rulesets.get("ruleset-workflows", {}).get("workflow_ref", "")
if not re.fullmatch(r"refs/tags/v[0-9]+\.[0-9]+\.[0-9]+", workflow_ref):
    err(
        "ruleset-workflows.workflow_ref must be an immutable release tag such as refs/tags/v5.0.0"
    )
merge_queue_classes = set(rulesets.get("merge-queue", {}).get("classes", []))
class_merge_queue = {
    name for name, config in classes.items() if config.get("merge_queue") is True
}
if merge_queue_classes != class_merge_queue:
    err(
        "merge-queue ruleset classes must exactly match repository classes whose "
        f"merge_queue policy is true: {sorted(class_merge_queue)}"
    )
if "enterprise-control" in merge_queue_classes:
    err("enterprise-control repositories must not receive merge-queue enforcement")
release_tag_creation = rulesets.get("release-tag-creation", {})
if release_tag_creation.get("target") != "all":
    err("release-tag-creation must target the complete managed estate")
bootstrap_checks = rulesets.get("required-checks-bootstrap", {})
if bootstrap_checks.get("repositories") != ["bootstrap"]:
    err("required-checks-bootstrap must target only bootstrap")
gitops_checks = rulesets.get("required-checks-gitops", {})
if gitops_checks.get("enforcement") != "active":
    err("required-checks-gitops must remain active")
if gitops_checks.get("repositories") != ["gitops"]:
    err("required-checks-gitops must target only gitops")
mixed_checks = rulesets.get("required-checks-mixed", {})
if mixed_checks.get("language_profiles") != ["mixed"]:
    err("required-checks-mixed must target only the mixed language profile")
infra_static_checks = rulesets.get("required-checks-infra-static", {})
if infra_static_checks.get("repositories") != ["mindclade-internal-monorepo"]:
    err(
        "required-checks-infra-static must target only the canonical "
        "mindclade-internal-monorepo repository"
    )

nix_checks = rulesets.get("required-checks-nix", {})
nix_repositories = nix_checks.get("repositories", [])
if len(nix_repositories) != len(EXPECTED_REPOS) or set(nix_repositories) != EXPECTED_REPOS:
    err("required-checks-nix must target exactly the seven managed repositories")

try:
    validate_release_tag_contracts(ROOT)
except TerraformContractError as exc:
    err(str(exc))
for contract in REQUIRED_STATUS_RULESET_CONTRACTS:
    try:
        validate_required_status_ruleset(
            ROOT,
            contract,
            rulesets.get(contract.ruleset_name, {}),
        )
    except TerraformContractError as exc:
        err(str(exc))

nix_workflow_path = ROOT / ".github" / "workflows" / "nix-qualification.yml"
try:
    nix_workflow = yaml.safe_load(nix_workflow_path.read_text(encoding="utf-8"))
except (OSError, yaml.YAMLError) as exc:
    err(f"nix-qualification workflow cannot be parsed: {exc}")
    nix_workflow = {}
nix_job = nix_workflow.get("jobs", {}).get("nix", {})
if nix_workflow.get("permissions") != {"contents": "read"}:
    err("nix-qualification workflow must have exact contents:read top-level permission")
if nix_job.get("permissions"):
    err("nix-qualification caller job must not add permissions")
if nix_job.get("secrets"):
    err("nix-qualification caller must not inherit or pass secrets")
if nix_job.get("uses") != (
    "mindclade/.github/.github/workflows/"
    "reusable-nix-qualification.yml@0bdba2a8d06c732a6eb0a09238267dc83e1ca576"
):
    err("nix-qualification must use the audited immutable v5.0.0 candidate commit")
nix_inputs = nix_job.get("with", {})
for name in ("enable-aarch64-linux", "enable-aarch64-darwin"):
    if nix_inputs.get(name) is not True:
        err(f"nix-qualification must enable native {name.removeprefix('enable-')}")
if nix_inputs.get("ci-command") != "make validate":
    err("nix-qualification must execute the canonical make validate entrypoint")
if nix_inputs.get("reproducibility-targets") != ".#packages.x86_64-linux.terraform":
    err("nix-qualification must rebuild the pinned x86_64-linux Terraform package")

# Time-bounded access exceptions.
if not isinstance(exceptions, list):
    err("access-exceptions.yaml must be a list")
else:
    seen_ids: set[str] = set()
    for item in exceptions:
        if not isinstance(item, dict):
            err("access exception must be an object")
            continue
        required = {
            "id",
            "principal",
            "repository",
            "role",
            "reason",
            "approver",
            "created_at",
            "expires_at",
        }
        missing = required - set(item)
        if missing:
            err(f"access exception missing fields: {sorted(missing)}")
            continue
        if item["id"] in seen_ids:
            err(f"duplicate access exception id: {item['id']}")
        seen_ids.add(item["id"])
        if item["repository"] not in repos:
            err(f"access exception {item['id']}: unknown repository")
        if item["role"] not in ROLE_RANK or item["role"] == "admin":
            err(f"access exception {item['id']}: invalid/forbidden role")
        try:
            created = date.fromisoformat(str(item["created_at"]))
            expiry = date.fromisoformat(str(item["expires_at"]))
            if expiry <= created:
                err(f"access exception {item['id']}: expires_at must follow created_at")
            if expiry < date.today():
                err(f"access exception {item['id']}: expired on {expiry}")
        except ValueError as exc:
            err(f"access exception {item.get('id')}: invalid date: {exc}")

    solo_founder_items = [
        item
        for item in exceptions
        if isinstance(item, dict)
        and str(item.get("id", "")).startswith(
            "solo-founder-bootstrap-reviewer-"
        )
    ]
    solo_founder_exceptions = {
        item.get("repository"): item for item in solo_founder_items
    }
    if solo_founder_items and (
        len(solo_founder_items) != 3
        or set(solo_founder_exceptions)
        != {"bootstrap", "github-config", "infrastructure-live"}
    ):
        err(
            "solo-founder bootstrap reviewer exception must cover exactly bootstrap, "
            "github-config, and infrastructure-live"
        )
    for repository, item in solo_founder_exceptions.items():
        if (
            item.get("principal") != "robpearc"
            or item.get("role") != "pull"
            or item.get("approver") != "mindclade-founder"
        ):
            err(
                f"solo-founder bootstrap reviewer exception for {repository} differs "
                "from the approved same-human read-only scope"
            )
        try:
            created = date.fromisoformat(str(item.get("created_at")))
            expiry = date.fromisoformat(str(item.get("expires_at")))
            if (expiry - created).days > 90:
                err(
                    f"solo-founder bootstrap reviewer exception for {repository} "
                    "may not exceed 90 days"
                )
        except ValueError:
            pass  # The generic exception validation above reports the malformed date.
        if "not independent review" not in str(item.get("reason", "")):
            err(
                f"solo-founder bootstrap reviewer exception for {repository} must "
                "state that it is not independent review"
            )

try:
    expiry_workflow = yaml.safe_load(
        (ROOT / ".github/workflows/drift.yml").read_text(encoding="utf-8")
    )
    if not isinstance(expiry_workflow, dict):
        raise TerraformContractError("drift workflow: expected YAML object")
    validate_drift_access_expiry(expiry_workflow)
except (OSError, yaml.YAMLError, TerraformContractError) as exc:
    err(f"drift workflow access-expiry contract is invalid: {exc}")
solo_founder_runbook = (ROOT / "docs/solo-founder-reviewer.md").read_text(
    encoding="utf-8"
)
for fragment in (
    "2026-11-18 23:59 America/Detroit",
    "At **T-3**",
    "not independent review",
    "--update-roles-params=MEMBER=expiration=<approved-duration>",
):
    if fragment not in solo_founder_runbook:
        err(f"solo-founder reviewer runbook omits required control: {fragment}")

# Non-secret CI variable catalog references only managed repositories and carries valid JSON
# where a value is represented as a serialized object/array.
if set(ci_variables) != EXPECTED_REPOS:
    err(
        f"ci-variables must cover every managed repository: {sorted(set(ci_variables) ^ EXPECTED_REPOS)}"
    )
for repo, variables in ci_variables.items():
    if repo not in repos:
        err(f"ci-variables: unknown repository {repo}")
    if not isinstance(variables, dict):
        err(f"ci-variables: {repo} must map variable names to values")
        continue
    for name, value in variables.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(name)):
            err(
                f"ci-variables: {repo}/{name} is not an uppercase Actions variable name"
            )
        if str(name).startswith("GITHUB_"):
            err(f"ci-variables: {repo}/{name} uses GitHub's reserved GITHUB_ prefix")
        text = str(value)
        if text == "":
            err(
                f"ci-variables: {repo}/{name} is empty; use env:NAME for operator input"
            )
        if text.startswith("env:") and not re.fullmatch(r"env:[A-Z][A-Z0-9_]*", text):
            err(
                f"ci-variables: {repo}/{name} has malformed environment indirection {text!r}"
            )
        if text.startswith(("{", "[")):
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                err(f"ci-variables: {repo}/{name} contains invalid JSON: {exc}")
for repo, required in REQUIRED_CI_VARIABLES.items():
    variables = ci_variables.get(repo, {})
    for name, expected_value in required.items():
        if variables.get(name) != expected_value:
            err(f"ci-variables: {repo}/{name} must be {expected_value!r}")
environment_project_handoff = ci_variables.get("github-config", {}).get(
    "ENVIRONMENT_PROJECT_IDS"
)
if environment_project_handoff not in {"{}", "env:ENVIRONMENT_PROJECT_IDS"}:
    err(
        "ci-variables: github-config/ENVIRONMENT_PROJECT_IDS must be '{}' during initial "
        "governance or env:ENVIRONMENT_PROJECT_IDS after exact infrastructure outputs exist"
    )
for contract_derived_name in (
    "GCP_ORG_ID",
    "BILLING_ACCOUNT",
    "GH_ORGANIZATION",
    "GH_ORGANIZATION_ID",
    "GH_REPOSITORY_IDS_JSON",
    "BOOTSTRAP_FOLDER_ID",
    "AUTOMATION_SECRET_LOCATION",
):
    if contract_derived_name in ci_variables.get("bootstrap", {}):
        err(
            "ci-variables: bootstrap/"
            f"{contract_derived_name} must not be a free-form catalog input"
        )
legacy_signing_variables = {
    "ATTESTOR",
    "ATTESTOR_KEY",
    "BINAUTHZ_ATTESTOR_PROJECT",
    "BINAUTHZ_ATTESTOR_KEY_VERSION",
}
monorepo_variables = ci_variables.get("mindclade-internal-monorepo", {})
if legacy_signing_variables & set(monorepo_variables):
    err(
        "ci-variables: builder-scoped legacy signing variables are forbidden in the monorepo"
    )
for repo, variables in ci_variables.items():
    if {"BINAUTHZ_ATTESTOR_PROJECT", "BINAUTHZ_ATTESTOR_KEY_VERSION"} & set(variables):
        err(
            f"ci-variables: {repo} retains ambiguous legacy Binary Authorization variables"
        )
if "BUILDKITE_WIF_POOL_NAME" in ci_variables.get("infrastructure-live", {}):
    err(
        "ci-variables: Buildkite WIF pool must come from bootstrap platform_contract, not env input"
    )
for repository, variables in ci_variables.items():
    forbidden_buildkite = {
        name for name in variables if name.startswith("BUILDKITE_")
    } - ({"ENABLE_BUILDKITE_WIF"} if repository == "bootstrap" else set())
    if forbidden_buildkite:
        err(
            f"ci-variables: {repository} retains Buildkite authority variables: "
            f"{sorted(forbidden_buildkite)}"
        )
bazel_cache_variables = {
    repository: {name for name in variables if "BAZEL_CACHE" in name}
    for repository, variables in ci_variables.items()
}
expected_bazel_cache_variables = {
    ".github": set(),
    ".github-private": set(),
    "github-config": set(),
    "bootstrap": set(),
    "infrastructure-live": {"BAZEL_CACHE_IDENTITY_JSON"},
    "gitops": set(),
    "mindclade-internal-monorepo": {
        "WIF_PROVIDER_BAZEL_CACHE",
        "SA_BAZEL_CACHE_READER",
        "SA_BAZEL_CACHE_WRITER",
    },
}
if bazel_cache_variables != expected_bazel_cache_variables:
    err("ci-variables: Bazel cache variable inventory is not exact")

ci_variable_exporter = (ROOT / "scripts" / "export-ci-variables.py").read_text(
    encoding="utf-8"
)
required_export_fragments = {
    "bootstrap/TFSTATE_REPLICA_BUCKET": '"TFSTATE_REPLICA_BUCKET"',
    "infrastructure-live/WIF_POOL_GITHUB_NAME": '"WIF_POOL_GITHUB_NAME"',
    "infrastructure-live/WIF_PROVIDER_SIGNER": '"WIF_PROVIDER_SIGNER"',
    "infrastructure-live/ARTIFACT_RELEASE_IDENTITIES_JSON": '"ARTIFACT_RELEASE_IDENTITIES_JSON"',
    "infrastructure-live/ARTIFACT_SIGNER_PRINCIPAL": '"ARTIFACT_SIGNER_PRINCIPAL"',
    "infrastructure-live/ARTIFACT_SIGNER_JOB_WORKFLOW_REF": '"ARTIFACT_SIGNER_JOB_WORKFLOW_REF"',
    "infrastructure-live/PRODUCTION_QUALIFICATION_IDENTITY_JSON": '"PRODUCTION_QUALIFICATION_IDENTITY_JSON"',
    "infrastructure-live/BAZEL_CACHE_IDENTITY_JSON": '"BAZEL_CACHE_IDENTITY_JSON"',
    "github-config/DR_EVIDENCE_ENVIRONMENT_VARIABLES": '"DR_EVIDENCE_ENVIRONMENT_VARIABLES"',
    "monorepo/WIF_PROVIDER_SIGNER": '"WIF_PROVIDER_SIGNER"',
    "monorepo/WIF_PROVIDER_ARC_CANARY": '"WIF_PROVIDER_ARC_CANARY"',
    "monorepo/WIF_PROVIDER_ARC_BUILDER": '"WIF_PROVIDER_ARC_BUILDER"',
    "monorepo/WIF_PROVIDER_ARC_QUALIFICATION_READER": '"WIF_PROVIDER_ARC_QUALIFICATION_READER"',
    "monorepo/WIF_PROVIDER_ARC_QUALIFIER": '"WIF_PROVIDER_ARC_QUALIFIER"',
    "monorepo/WIF_PROVIDER_ARC_PROMOTER": '"WIF_PROVIDER_ARC_PROMOTER"',
    "monorepo/WIF_PROVIDER_BAZEL_CACHE": '"WIF_PROVIDER_BAZEL_CACHE"',
    "monorepo/SA_BAZEL_CACHE_READER": '"SA_BAZEL_CACHE_READER"',
    "monorepo/SA_BAZEL_CACHE_WRITER": '"SA_BAZEL_CACHE_WRITER"',
}
for name, fragment in required_export_fragments.items():
    if fragment not in ci_variable_exporter:
        err(f"ci-variable exporter must publish {name}")
if '"platform_contract"' not in ci_variable_exporter:
    err("ci-variable exporter must source bootstrap/platform_contract")
for fragment in (
    'SUPPORTED_BOOTSTRAP_CONTRACT_VERSIONS = {"1.2.0", "1.4.0", "1.5.0"}',
    '"replica_buckets"',
    'if enabled or buildkite.get("workload_identity_pool") is not None',
    '"workload_identity_pool"',
    '"principal"',
    '"repository_identities"',
    'selected["bootstrap"]["SECURITY_CONTACT"] = "env:SECURITY_CONTACT"',
    '"artifact_release_identities"',
    "artifact_release_contract(",
    "dr_evidence_environment_contract(",
    "production_qualification_identity_contract(",
    "bazel_cache_identity_contract(",
    "validate_applied_bazel_cache_handoff(",
    "load_applied_handoff(",
    "apply_applied_handoff(",
    '"1.3.0": APPLIED_HANDOFF_V13_VARIABLES',
    '"1.4.0": APPLIED_HANDOFF_V13_VARIABLES',
    'applied_handoff.contract_version != "1.4.0"',
    'choices=("bootstrap", "full")',
):
    if fragment not in ci_variable_exporter:
        err(f"ci-variable exporter omits staged bootstrap contract fragment: {fragment}")
if '"state_replica_buckets"' in ci_variable_exporter:
    err(
        "ci-variable exporter must use platform_contract, not bootstrap convenience outputs"
    )
if '"GITHUB_WIF_POOL_NAME"' in ci_variable_exporter:
    err("ci-variable exporter uses forbidden GITHUB_WIF_POOL_NAME")
if '"BOOTSTRAP_FOLDER_ID"' in ci_variable_exporter:
    err("ci-variable exporter must not publish the bootstrap adopt-existing folder input")
if '"AUTOMATION_SECRET_LOCATION"' in ci_variable_exporter:
    err("ci-variable exporter must not publish an unused bootstrap default as a repository variable")

try:
    validate_bazel_cache_ci_variable_contract(ROOT)
except TerraformContractError as exc:
    err(str(exc))

expected_preexisting_environments = {
    "bootstrap:bootstrap",
    "bootstrap:bootstrap-recovery-read",
    "bootstrap:break-glass",
    "bootstrap:plan",
    "github-config:governance",
    "github-config:plan",
    "gitops:break-glass",
    "gitops:development",
    "gitops:production",
    "gitops:staging",
    "infrastructure-live:break-glass",
    "infrastructure-live:development",
    "infrastructure-live:plan",
    "infrastructure-live:production",
    "infrastructure-live:staging",
    "mindclade-internal-monorepo:release",
}
try:
    validate_import_contract(ROOT)
    imports_document = load_terraform(ROOT / "imports.tf")
    environment_import_expression = local_value(
        imports_document,
        "preexisting_repository_environments",
        "declarative adoption imports",
    )
    if not isinstance(environment_import_expression, str):
        raise TerraformContractError(
            "declarative adoption imports: environment inventory is not an expression"
        )
    actual_preexisting_environments = literal_toset_strings(
        environment_import_expression,
        "declarative adoption environment inventory",
    )
except TerraformContractError as exc:
    err(str(exc))
    actual_preexisting_environments = set()
if actual_preexisting_environments != expected_preexisting_environments:
    err(
        "declarative environment imports differ from refreshed connected inventory: "
        f"{sorted(actual_preexisting_environments ^ expected_preexisting_environments)}"
    )
inventory_environments = {
    str(item.get("import_id"))
    for item in adoption_inventory.get("known_existing", [])
    if item.get("kind") == "repository_environment"
}
if inventory_environments != expected_preexisting_environments:
    err(
        "adoption inventory environment identities differ from declarative imports: "
        f"{sorted(inventory_environments ^ expected_preexisting_environments)}"
    )

unresolved_discovery = {
    str(item.get("resource_class")): str(item.get("reason"))
    for item in adoption_inventory.get("unresolved_discovery", [])
    if isinstance(item, dict)
}
branch_merge_protection_gap = unresolved_discovery.get(
    "branch_merge_protection", ""
)
for fragment in (
    "github-config/main has no branch protection",
    "effective rulesets are exactly active push-blocklist and tag-protection",
    "no-bypass baseline",
    "PRs 35 through 39",
    "Infrastructure-live PR 25",
    "zero reviews",
    "protected plan jobs were waiting",
    "before dependency and terminal CI qualification",
):
    if fragment not in branch_merge_protection_gap:
        err(f"branch merge-protection adoption blocker omits {fragment}")

try:
    validate_environment_handoff(ROOT)
except TerraformContractError as exc:
    err(str(exc))

# Every managed repository must actively restore GitHub's default subject. Merely declining to
# opt in leaves an out-of-band repository template untouched and breaks bootstrap's
# environment-shaped subjects just as effectively as opting in here would.
try:
    validate_oidc_module(ROOT)
except TerraformContractError as exc:
    err(str(exc))

# Bootstrap binds plan federation to the protected environment subject. Keep every
# github-config PR plan-capable entrypoint on that subject. Drift, scheduled IdP sync, and
# main-branch IdP dispatch use separately allowlisted @main workflow identities and never wait
# for an interactive review.
workflow_dir = ROOT / ".github" / "workflows"
workflow_docs = {
    name: yaml.safe_load((workflow_dir / f"{name}.yml").read_text(encoding="utf-8"))
    for name in ("plan", "apply", "drift", "idp-sync")
}
for workflow_name in ("plan", "apply"):
    plan_job = workflow_docs[workflow_name].get("jobs", {}).get("plan", {})
    if plan_job.get("environment") != "plan":
        err(f"{workflow_name}.yml plan job must use the protected plan environment")
    if "github.ref == 'refs/heads/main'" not in str(plan_job.get("if", "")):
        err(f"{workflow_name}.yml plan job must reject non-main manual dispatch")
drift_job = workflow_docs["drift"].get("jobs", {}).get("drift", {})
if drift_job.get("environment") is not None:
    err(
        "drift.yml must use the exact main-workflow WIF binding, not the interactive plan environment"
    )
if "github.ref == 'refs/heads/main'" not in str(drift_job.get("if", "")):
    err("drift.yml must reject manual dispatch from non-main refs")
try:
    validate_drift_readiness(workflow_docs["drift"])
except TerraformContractError as exc:
    err(str(exc))
drift_needs = drift_job.get("needs", [])
if "readiness" not in ([drift_needs] if isinstance(drift_needs, str) else drift_needs):
    err("drift.yml connected drift must depend on the readiness gate")
if "needs.readiness.outputs.enabled == 'true'" not in str(drift_job.get("if", "")):
    err("drift.yml connected drift must require explicit readiness activation")
artifact_job = workflow_docs["drift"].get("jobs", {}).get("drift-artifact-verify", {})
artifact_needs = artifact_job.get("needs", [])
if "readiness" not in (
    [artifact_needs] if isinstance(artifact_needs, str) else artifact_needs
):
    err("drift artifact verification must depend on the readiness gate")
if "needs.readiness.outputs.enabled == 'true'" not in str(artifact_job.get("if", "")):
    err("drift artifact verification must remain staged with connected drift")

idp_jobs = workflow_docs["idp-sync"].get("jobs", {})
if "export" in idp_jobs:
    err("idp-sync.yml must split PR and protected-main authentication paths")
idp_pr_job = idp_jobs.get("export_pr", {})
if idp_pr_job.get("environment") != "plan":
    err("idp-sync.yml export_pr job must use the protected plan environment")
idp_pr_condition = str(idp_pr_job.get("if", ""))
for guard in (
    "github.event_name == 'pull_request'",
    "github.event.pull_request.head.repo.full_name == github.repository",
):
    if guard not in idp_pr_condition:
        err(f"idp-sync.yml export_pr job is missing guard: {guard}")

idp_main_job = idp_jobs.get("export_main", {})
if idp_main_job.get("environment") is not None:
    err(
        "idp-sync.yml export_main must use exact @main workflow trust without an environment"
    )
idp_main_condition = str(idp_main_job.get("if", ""))
for guard in (
    "github.event_name == 'schedule'",
    "github.event_name == 'workflow_dispatch'",
    "github.ref == 'refs/heads/main'",
):
    if guard not in idp_main_condition:
        err(f"idp-sync.yml export_main job is missing guard: {guard}")

for job_name, job in (("export_pr", idp_pr_job), ("export_main", idp_main_job)):
    if job.get("permissions", {}).get("id-token") != "write":
        err(f"idp-sync.yml {job_name} must request id-token: write locally")
    serialized_steps = json.dumps(job.get("steps", []), sort_keys=True)
    for variable in ("WIF_PROVIDER_PLAN", "SA_GITHUB_CONFIG_PLAN"):
        if variable not in serialized_steps:
            err(f"idp-sync.yml {job_name} must authenticate with {variable}")

report_job = idp_jobs.get("report", {})
if report_job.get("needs") not in (["export_main"], "export_main"):
    err("idp-sync.yml scheduled report must depend only on export_main")

initial_import_path = ROOT / "docs" / "initial-import.md"
if initial_import_path.is_file():
    initial_import = initial_import_path.read_text(encoding="utf-8")
    if "protected `v5.0.0` workflow-contract tag" not in initial_import:
        err("initial-import.md must use the immutable v5.0.0 workflow-contract tag")
    if "protected `v1` workflow-contract tag" in initial_import:
        err("initial-import.md retains the stale v1 workflow-contract tag")

adoption = (ROOT / "docs" / "adoption.md").read_text(encoding="utf-8")
for fragment in (
    "`mindclade/.github`",
    "under `.github/workflows/`",
    "--stage bootstrap",
    "`BOOTSTRAP_FOLDER_ID` is an adopt-existing bootstrap input",
    "## One-time founder OAuth adoption",
    'export GITHUB_TOKEN="$(gh auth token)"',
    "use App tokens exclusively for normal plan/apply operation",
):
    if fragment not in adoption:
        err(f"adoption.md omits activation-safety contract: {fragment}")

# Repository hygiene is part of the policy compiler contract.
if (ROOT / "CODEOWNERS").exists():
    err("root CODEOWNERS is forbidden; use .github/CODEOWNERS")
if not (ROOT / ".github" / "CODEOWNERS").is_file():
    err(".github/CODEOWNERS is missing")
try:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    repository_paths = [
        ROOT / item.decode("utf-8") for item in listed.split(b"\0") if item
    ]
except (FileNotFoundError, subprocess.CalledProcessError):
    repository_paths = [path for path in ROOT.rglob("*") if ".git" not in path.parts]
for path in repository_paths:
    if path.name in {".terraform", ".terragrunt-cache"}:
        err(f"local tool cache committed/present: {path.relative_to(ROOT)}")
    if path.name.startswith("terraform.tfstate") or path.suffix == ".tfplan":
        err(f"local state/plan present: {path.relative_to(ROOT)}")

if errors:
    for message in sorted(set(errors)):
        print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

print(
    "catalog validation passed: "
    f"{len(repos)} repositories, {len(teams)} teams, {len(environments)} environments, "
    f"{len(rulesets)} rulesets, {len(properties)} custom properties, "
    f"{len(declared_control_apps)} control-plane Apps"
)
