#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
"""Validate Mindclade's GitHub governance catalog without cloud credentials."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml
from jsonschema import Draft202012Validator

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
    "staging",
    "production",
    "plan",
    "governance",
    "bootstrap",
    "release",
    "break-glass",
}
EXPECTED_RULESETS = {
    "baseline-all",
    "merge-queue",
    "protected-paths",
    "push-blocklist",
    "required-checks-go",
    "required-checks-mixed",
    "required-checks-tf",
    "required-checks-tf-static",
    "required-checks-tf-tests",
    "ruleset-workflows",
    "tag-protection",
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
    "bootstrap": {
        "GH_ORGANIZATION": "mindclade",
        "GH_ORGANIZATION_ID": "env:GH_ORGANIZATION_ID",
        "GH_REPOSITORY_IDS_JSON": "env:GH_REPOSITORY_IDS_JSON",
    },
    "gitops": {
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR",
    },
    "mindclade-internal-monorepo": {
        "BINAUTHZ_BUILD_ATTESTOR_PROJECT": "env:BINAUTHZ_BUILD_ATTESTOR_PROJECT",
        "BINAUTHZ_BUILD_ATTESTOR": "env:BINAUTHZ_BUILD_ATTESTOR",
        "BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT": "env:BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT",
        "BINAUTHZ_QUALIFICATION_ATTESTOR": "env:BINAUTHZ_QUALIFICATION_ATTESTOR",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR": "env:BINAUTHZ_DEPLOYMENT_ATTESTOR",
        "BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION": (
            "env:BINAUTHZ_DEPLOYMENT_ATTESTOR_KEY_VERSION"
        ),
        "SA_ARTIFACT_SIGNER": "env:SA_ARTIFACT_SIGNER",
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
for stem in ("repositories", "teams", "access", "environments"):
    data = load_yaml(f"{stem}.yaml")
    try:
        schema = json.loads((SCHEMA / f"{stem}.schema.json").read_text(encoding="utf-8"))
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
exceptions = load_yaml("access-exceptions.yaml") or []
ci_variables = load_yaml("ci-variables.yaml") or {}

if set(repos) != EXPECTED_REPOS:
    err(f"repository estate differs: {sorted(set(repos) ^ EXPECTED_REPOS)}")
if set(classes) != EXPECTED_CLASSES:
    err(f"repository classes differ: {sorted(set(classes) ^ EXPECTED_CLASSES)}")
if set(environments) != EXPECTED_ENVIRONMENTS:
    err(f"environment inventory differs: {sorted(set(environments) ^ EXPECTED_ENVIRONMENTS)}")
if set(access) != EXPECTED_REPOS:
    err(f"access catalog must cover every managed repository: {sorted(set(access) ^ EXPECTED_REPOS)}")
if set(rulesets) != EXPECTED_RULESETS:
    err(f"ruleset inventory differs from implementation: {sorted(set(rulesets) ^ EXPECTED_RULESETS)}")
if set(properties) != set(PROPERTY_FIELDS):
    err(f"custom-property inventory differs: {sorted(set(properties) ^ set(PROPERTY_FIELDS))}")

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
    if name in {"governance", "bootstrap", "production", "release", "break-glass"}:
        if not cfg.get("protected_branches"):
            err(f"environment {name}: protected_branches must be true")
        if not cfg.get("prevent_self_review"):
            err(f"environment {name}: prevent_self_review must be true")
        if not cfg.get("reviewer_teams"):
            err(f"environment {name}: at least one reviewer team is required")
    if cfg.get("protected_branches") and cfg.get("custom_branch_policies"):
        err(f"environment {name}: protected and custom branch policies are mutually exclusive")
plan_environment = environments.get("plan", {})
if plan_environment.get("protected_branches") or plan_environment.get("custom_branch_policies"):
    err("environment plan: branch filters must allow pull-request merge refs")
if "infrastructure" not in plan_environment.get("reviewer_teams", []):
    err("environment plan: infrastructure review is required")
if not plan_environment.get("prevent_self_review"):
    err("environment plan: self-review must be disabled")
for repository in ("bootstrap", "github-config", "infrastructure-live"):
    if "plan" not in repos.get(repository, {}).get("environments", []):
        err(f"{repository} must declare the protected plan environment")

# GitOps promotion jobs select an environment from the promotion target. Both pre-production
# rehearsal and production therefore need explicit protected-branch gates; otherwise a caller
# could name an environment that exists only as an unreviewed workflow string.
gitops_environments = set(repos.get("gitops", {}).get("environments", []))
for name in ("staging", "production"):
    cfg = environments.get(name, {})
    if name not in gitops_environments:
        err(f"gitops must declare the {name} promotion environment")
    if not cfg.get("protected_branches") or cfg.get("custom_branch_policies"):
        err(f"environment {name}: GitOps promotion must be restricted to protected branches")
    if not cfg.get("prevent_self_review"):
        err(f"environment {name}: GitOps promotion must prevent self-review")
if "platform" not in environments.get("staging", {}).get("reviewer_teams", []):
    err("environment staging: platform review is required for GitOps promotion")
if not {"platform", "security"}.issubset(
    set(environments.get("production", {}).get("reviewer_teams", []))
):
    err("environment production: platform and security review are required for GitOps promotion")

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
if not any(str(item).startswith("mindclade/.github/.github/workflows/") for item in patterns):
    err("actions policy: Mindclade shared workflows are not allowlisted")

# OIDC policy. Optional claims must not be required organization-wide.
subject_claims = set(oidc.get("subject_claim_keys", []))
wif_claims = set(oidc.get("required_wif_attribute_claims", []))
if subject_claims != UNIVERSAL_OIDC_CLAIMS:
    err(f"OIDC subject claims must be {sorted(UNIVERSAL_OIDC_CLAIMS)}, got {sorted(subject_claims)}")
if wif_claims != REQUIRED_WIF_CLAIMS:
    err(f"OIDC WIF claims must be {sorted(REQUIRED_WIF_CLAIMS)}, got {sorted(wif_claims)}")
if subject_claims & FORBIDDEN_ORG_SUBJECT_CLAIMS:
    err(f"OIDC subject requires optional claims: {sorted(subject_claims & FORBIDDEN_ORG_SUBJECT_CLAIMS)}")
for flag in (
    "repository_opt_in",
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
    err("ruleset-workflows.workflow_ref must be an immutable release tag such as refs/tags/v3.0.0")

# Time-bounded access exceptions.
if not isinstance(exceptions, list):
    err("access-exceptions.yaml must be a list")
else:
    seen_ids: set[str] = set()
    for item in exceptions:
        if not isinstance(item, dict):
            err("access exception must be an object")
            continue
        required = {"id", "principal", "repository", "role", "reason", "approver", "created_at", "expires_at"}
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

# Non-secret CI variable catalog references only managed repositories and carries valid JSON
# where a value is represented as a serialized object/array.
if set(ci_variables) != EXPECTED_REPOS:
    err(f"ci-variables must cover every managed repository: {sorted(set(ci_variables) ^ EXPECTED_REPOS)}")
for repo, variables in ci_variables.items():
    if repo not in repos:
        err(f"ci-variables: unknown repository {repo}")
    if not isinstance(variables, dict):
        err(f"ci-variables: {repo} must map variable names to values")
        continue
    for name, value in variables.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(name)):
            err(f"ci-variables: {repo}/{name} is not an uppercase Actions variable name")
        if str(name).startswith("GITHUB_"):
            err(f"ci-variables: {repo}/{name} uses GitHub's reserved GITHUB_ prefix")
        text = str(value)
        if text == "":
            err(f"ci-variables: {repo}/{name} is empty; use env:NAME for operator input")
        if text.startswith("env:") and not re.fullmatch(r"env:[A-Z][A-Z0-9_]*", text):
            err(f"ci-variables: {repo}/{name} has malformed environment indirection {text!r}")
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
legacy_signing_variables = {
    "ATTESTOR",
    "ATTESTOR_KEY",
    "BINAUTHZ_ATTESTOR_PROJECT",
    "BINAUTHZ_ATTESTOR_KEY_VERSION",
}
monorepo_variables = ci_variables.get("mindclade-internal-monorepo", {})
if legacy_signing_variables & set(monorepo_variables):
    err("ci-variables: builder-scoped legacy signing variables are forbidden in the monorepo")
for repo, variables in ci_variables.items():
    if {"BINAUTHZ_ATTESTOR_PROJECT", "BINAUTHZ_ATTESTOR_KEY_VERSION"} & set(variables):
        err(f"ci-variables: {repo} retains ambiguous legacy Binary Authorization variables")

ci_variable_exporter = (ROOT / "scripts" / "export-ci-variables.sh").read_text(encoding="utf-8")
required_export_fragments = {
    "infrastructure-live/WIF_POOL_GITHUB_NAME": "WIF_POOL_GITHUB_NAME: $github_wif_pool",
    "infrastructure-live/WIF_PROVIDER_SIGNER": "WIF_PROVIDER_SIGNER: $artifact_signer_wif_provider",
    "infrastructure-live/ARTIFACT_SIGNER_PRINCIPAL": (
        "ARTIFACT_SIGNER_PRINCIPAL: $artifact_signer_principal"
    ),
    "infrastructure-live/ARTIFACT_SIGNER_JOB_WORKFLOW_REF": (
        "ARTIFACT_SIGNER_JOB_WORKFLOW_REF: $artifact_signer_job_workflow_ref"
    ),
    "monorepo/WIF_PROVIDER_SIGNER": "WIF_PROVIDER_SIGNER: $artifact_signer_wif_provider",
}
for name, fragment in required_export_fragments.items():
    if fragment not in ci_variable_exporter:
        err(f"ci-variable exporter must publish {name}")
for output_name in (
    "artifact_signer_wif_provider",
    "artifact_signer_principal",
    "artifact_signer_job_workflow_ref",
):
    if f'output("{output_name}")' not in ci_variable_exporter:
        err(f"ci-variable exporter must source bootstrap/{output_name}")
if re.search(r"^\s*GITHUB_WIF_POOL_NAME:", ci_variable_exporter, re.MULTILINE):
    err("ci-variable exporter uses forbidden GITHUB_WIF_POOL_NAME")

# Bootstrap binds plan federation to the protected environment subject. Keep every
# github-config plan-capable entrypoint on that subject, while drift uses its separately
# allowlisted main-branch workflow identity and never waits for an interactive review.
workflow_dir = ROOT / ".github" / "workflows"
workflow_docs = {
    name: yaml.safe_load((workflow_dir / f"{name}.yml").read_text(encoding="utf-8"))
    for name in ("plan", "apply", "drift")
}
for workflow_name in ("plan", "apply"):
    plan_job = workflow_docs[workflow_name].get("jobs", {}).get("plan", {})
    if plan_job.get("environment") != "plan":
        err(f"{workflow_name}.yml plan job must use the protected plan environment")
    if "github.ref == 'refs/heads/main'" not in str(plan_job.get("if", "")):
        err(f"{workflow_name}.yml plan job must reject non-main manual dispatch")
drift_job = workflow_docs["drift"].get("jobs", {}).get("drift", {})
if drift_job.get("environment") is not None:
    err("drift.yml must use the exact main-workflow WIF binding, not the interactive plan environment")
if "github.ref == 'refs/heads/main'" not in str(drift_job.get("if", "")):
    err("drift.yml must reject manual dispatch from non-main refs")

initial_import_path = ROOT / "docs" / "initial-import.md"
if initial_import_path.is_file():
    initial_import = initial_import_path.read_text(encoding="utf-8")
    if "protected `v3.0.0` workflow-contract tag" not in initial_import:
        err("initial-import.md must use the immutable v3.0.0 workflow-contract tag")
    if "protected `v1` workflow-contract tag" in initial_import:
        err("initial-import.md retains the stale v1 workflow-contract tag")

# Repository hygiene is part of the policy compiler contract.
if (ROOT / "CODEOWNERS").exists():
    err("root CODEOWNERS is forbidden; use .github/CODEOWNERS")
if not (ROOT / ".github" / "CODEOWNERS").is_file():
    err(".github/CODEOWNERS is missing")
for path in ROOT.rglob("*"):
    if ".git" in path.parts:
        continue
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
    f"{len(rulesets)} rulesets, {len(properties)} custom properties"
)
