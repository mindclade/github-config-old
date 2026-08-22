#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compare connected GitHub governance with the complete source catalog using GETs only."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


class AuditError(RuntimeError):
    pass


class AuditTransportError(AuditError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise AuditError(f"cannot load {path}: {error}") from error
    if not isinstance(document, dict):
        raise AuditError(f"{path} must contain a mapping")
    return document


class GitHubApi:
    """A deliberately GET-only gh client which never serializes its token."""

    def get(self, path: str) -> Any:
        if not path.startswith("/") and not path.startswith("https://api.github.com/"):
            raise AuditError(f"refusing non-API path: {path}")
        try:
            timeout = int(os.environ.get("GITHUB_API_TIMEOUT_SECONDS", "20"))
            if not 1 <= timeout <= 120:
                raise AuditError("GITHUB_API_TIMEOUT_SECONDS must be between 1 and 120")
            result = subprocess.run(
                ["gh", "api", "--method", "GET", path],
                check=True,
                text=True,
                capture_output=True,
                env=os.environ.copy(),
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise AuditError("gh is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise AuditTransportError(f"GET {path} timed out after {timeout}s") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or f"exit status {error.returncode}"
            if any(
                fragment in detail.lower()
                for fragment in ("error connecting", "timed out", "tls", "connection reset")
            ):
                raise AuditTransportError(f"GET {path} failed: {detail}") from error
            raise AuditError(f"GET {path} failed: {detail}") from error
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise AuditError(f"GET {path} returned invalid JSON") from error


def exact(label: str, actual: Any, expected: Any, errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def run_check(label: str, operation: Any, errors: list[str]) -> Any:
    """Keep auditing independent surfaces while preserving every denied endpoint as failure."""

    try:
        return operation()
    except AuditTransportError:
        raise
    except AuditError as error:
        errors.append(f"{label}: {error}")
        return None


def object_items(response: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict) and isinstance(response.get(key), list):
        items = [item for item in response[key] if isinstance(item, dict)]
        total = response.get("total_count")
        if isinstance(total, int) and total != len(items):
            raise AuditError(
                f"response {key} is paginated ({len(items)} of {total}); refusing partial evidence"
            )
        return items
    raise AuditError(f"response does not contain a {key} list")


def runtime_app_contracts(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    repository_names = {
        "pullRequests": "pull_requests",
    }
    organization_names = {
        "selfHostedRunners": "organization_self_hosted_runners",
    }
    result: dict[str, dict[str, Any]] = {}
    for name, app in document.items():
        permissions = {
            repository_names.get(key, key): value
            for key, value in app.get("repositoryPermissions", {}).items()
        }
        permissions.update(
            {
                organization_names.get(key, key): value
                for key, value in app.get("organizationPermissions", {}).items()
            }
        )
        result[name] = {
            "repositories": sorted(app.get("repositories", [])),
            "permissions": permissions,
        }
    return result


def control_app_contracts(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, app in document.get("apps", {}).items():
        permissions = dict(app.get("repository_permissions", {}))
        permissions.update(app.get("organization_permissions", {}))
        result[name] = {
            "repositories": sorted(app.get("repositories", [])),
            "permissions": permissions,
        }
    return result


def audit_repositories(
    api: GitHubApi,
    org: str,
    catalog: dict[str, Any],
    connected_ids: dict[str, int],
    errors: list[str],
) -> None:
    actual = object_items(api.get(f"/orgs/{org}/repos?per_page=100&type=all"), "repositories")
    by_name = {item.get("name"): item for item in actual}
    exact("repository inventory", sorted(by_name), sorted(catalog), errors)
    for name, desired in catalog.items():
        repository = by_name.get(name, {})
        exact(f"{name} visibility", repository.get("visibility"), desired.get("visibility"), errors)
        exact(f"{name} default branch", repository.get("default_branch"), "main", errors)
        exact(f"{name} archived", repository.get("archived"), desired.get("lifecycle") == "archive", errors)
        if name in connected_ids:
            exact(f"{name} immutable repository ID", repository.get("id"), connected_ids[name], errors)


def audit_organization(
    api: GitHubApi, org: str, connected_id: int | None, errors: list[str]
) -> None:
    actual = api.get(f"/orgs/{org}")
    expected = {
        "login": "mindclade",
        "default_repository_permission": "none",
        "members_can_create_repositories": False,
        "members_can_create_public_repositories": False,
        "members_can_create_private_repositories": False,
        "members_can_create_internal_repositories": False,
        "members_can_fork_private_repositories": False,
        # Repository deletion/transfer and visibility changes are the enterprise policy
        # ceiling. GitHub exposes them in this organization response but accepts no REST or
        # pinned-provider write for them, so this GET is the only honest evidence that an
        # enterprise owner has restricted both to organization owners.
        "members_can_delete_repositories": False,
        "members_can_change_repo_visibility": False,
        "members_can_create_pages": False,
        "members_can_create_public_pages": False,
        "members_can_create_private_pages": False,
        "web_commit_signoff_required": True,
    }
    for field, value in expected.items():
        exact(f"organization {field}", actual.get(field), value, errors)
    if connected_id is not None:
        exact("organization immutable ID", actual.get("id"), connected_id, errors)


def audit_teams(
    api: GitHubApi, org: str, catalog: dict[str, Any], errors: list[str]
) -> dict[str, int]:
    actual = object_items(api.get(f"/orgs/{org}/teams?per_page=100"), "teams")
    by_slug = {item.get("slug"): item for item in actual}
    exact("team inventory", sorted(by_slug), sorted(catalog), errors)
    ids: dict[str, int] = {}
    for name, desired in catalog.items():
        team = by_slug.get(name, {})
        if isinstance(team.get("id"), int):
            ids[name] = team["id"]
        exact(f"{name} team privacy", team.get("privacy"), desired.get("privacy"), errors)
        parent = team.get("parent")
        actual_parent = parent.get("slug") if isinstance(parent, dict) else None
        exact(f"{name} team parent", actual_parent, desired.get("parent"), errors)
    return ids


def audit_apps(
    api: GitHubApi,
    org: str,
    desired: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    installations = object_items(
        api.get(f"/orgs/{org}/installations?per_page=100"), "installations"
    )
    by_slug = {item.get("app_slug"): item for item in installations}
    exact("GitHub App installation inventory", sorted(by_slug), sorted(desired), errors)
    for name, contract in desired.items():
        installation = by_slug.get(name, {})
        exact(f"{name} repository selection", installation.get("repository_selection"), "selected", errors)
        exact(f"{name} permissions", installation.get("permissions", {}), contract["permissions"], errors)
        installation_id = installation.get("id")
        if not installation_id:
            continue
        selected = object_items(
            api.get(f"/user/installations/{installation_id}/repositories?per_page=100"),
            "repositories",
        )
        exact(
            f"{name} selected repositories",
            sorted(str(item.get("name")) for item in selected),
            contract["repositories"],
            errors,
        )


def audit_actions(
    api: GitHubApi, org: str, desired: dict[str, Any], errors: list[str]
) -> None:
    permissions = api.get(f"/orgs/{org}/actions/permissions")
    for field in ("enabled_repositories", "allowed_actions", "sha_pinning_required"):
        exact(f"Actions {field}", permissions.get(field), desired.get(field), errors)
    selected = api.get(f"/orgs/{org}/actions/permissions/selected-actions")
    exact("Actions github_owned_allowed", selected.get("github_owned_allowed"), desired.get("github_owned_allowed"), errors)
    exact("Actions verified_allowed", selected.get("verified_allowed"), desired.get("verified_creator_allowed"), errors)
    exact(
        "Actions allowed patterns",
        sorted(selected.get("patterns_allowed", [])),
        sorted(desired.get("allowed_action_patterns", [])),
        errors,
    )
    workflow = api.get(f"/orgs/{org}/actions/permissions/workflow")
    exact(
        "Actions default workflow permissions",
        workflow.get("default_workflow_permissions"),
        desired.get("default_workflow_permissions"),
        errors,
    )
    exact(
        "Actions pull-request approval",
        workflow.get("can_approve_pull_request_reviews"),
        desired.get("can_approve_pull_request_reviews"),
        errors,
    )


def expected_rulesets(
    rulesets: dict[str, Any], repositories: dict[str, Any]
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    organization: dict[str, dict[str, str]] = {}
    repository: dict[str, dict[str, dict[str, str]]] = {
        name: {} for name in repositories
    }
    for name, config in rulesets.items():
        target = "push" if name == "push-blocklist" else "tag" if name == "tag-protection" else "branch"
        shape = {"target": target, "enforcement": str(config["enforcement"])}
        if name == "merge-queue":
            for repository_name, repository_config in repositories.items():
                if repository_config.get("repository_class") in config.get("classes", []):
                    repository[repository_name][name] = shape
        else:
            organization[name] = shape
    return organization, repository


def ruleset_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        str(item.get("name")): {
            "target": str(item.get("target")),
            "enforcement": str(item.get("enforcement")),
        }
        for item in items
    }


def audit_rulesets(
    api: GitHubApi,
    org: str,
    rulesets: dict[str, Any],
    repositories: dict[str, Any],
    errors: list[str],
) -> None:
    expected_org, expected_repos = expected_rulesets(rulesets, repositories)
    actual_org = object_items(
        api.get(f"/orgs/{org}/rulesets?includes_parents=false&per_page=100"), "rulesets"
    )
    exact("organization rulesets", ruleset_summary(actual_org), expected_org, errors)
    for repository, expected in expected_repos.items():
        actual = object_items(
            api.get(
                f"/repos/{org}/{repository}/rulesets?includes_parents=false&per_page=100"
            ),
            "rulesets",
        )
        exact(f"{repository} repository rulesets", ruleset_summary(actual), expected, errors)


def audit_runner_groups(
    api: GitHubApi,
    org: str,
    desired: dict[str, Any],
    errors: list[str],
) -> None:
    groups = object_items(api.get(f"/orgs/{org}/actions/runner-groups"), "runner_groups")
    by_name = {item.get("name"): item for item in groups}
    exact("runner-group inventory", sorted(by_name), sorted(desired), errors)
    for name, contract in desired.items():
        group = by_name.get(name, {})
        exact(f"{name} visibility", group.get("visibility"), contract.get("visibility"), errors)
        exact(
            f"{name} allows public repositories",
            group.get("allows_public_repositories"),
            contract.get("allowsPublicRepositories"),
            errors,
        )
        exact(
            f"{name} workflow restriction",
            group.get("restricted_to_workflows"),
            contract.get("restrictedToWorkflows"),
            errors,
        )
        group_id = group.get("id")
        if not group_id:
            continue
        repositories = object_items(
            api.get(f"/orgs/{org}/actions/runner-groups/{group_id}/repositories"),
            "repositories",
        )
        exact(
            f"{name} selected repositories",
            sorted(str(item.get("name")) for item in repositories),
            sorted(contract.get("repositories", [])),
            errors,
        )
        workflow_response = api.get(
            f"/orgs/{org}/actions/runner-groups/{group_id}/selected-workflows"
        )
        workflows = workflow_response.get("selected_workflows", [])
        exact(
            f"{name} selected workflows",
            sorted(workflows),
            sorted(contract.get("workflows", [])),
            errors,
        )


def audit_environments(
    api: GitHubApi,
    org: str,
    repositories: dict[str, Any],
    environments: dict[str, Any],
    team_ids: dict[str, int],
    errors: list[str],
) -> None:
    for repository, config in repositories.items():
        response = api.get(f"/repos/{org}/{repository}/environments?per_page=100")
        actual = object_items(response, "environments")
        by_name = {item.get("name"): item for item in actual}
        expected_names = config.get("environments", [])
        exact(f"{repository} environments", sorted(by_name), sorted(expected_names), errors)
        for name in expected_names:
            expected = environments[name]
            environment = by_name.get(name, {})
            exact(f"{repository}/{name} wait timer", environment.get("wait_timer", 0), expected.get("wait_timer"), errors)
            exact(
                f"{repository}/{name} self review",
                environment.get("prevent_self_review", False),
                expected.get("prevent_self_review"),
                errors,
            )
            reviewers = {
                int(item.get("reviewer", {}).get("id"))
                for item in environment.get("protection_rules", [])
                if item.get("type") == "required_reviewers"
                for item in item.get("reviewers", [])
                if item.get("type") == "Team" and item.get("reviewer", {}).get("id")
            }
            expected_reviewers = {
                team_ids[name]
                for name in expected.get("reviewer_teams", [])
                if name in team_ids
            }
            exact(f"{repository}/{name} reviewer teams", reviewers, expected_reviewers, errors)
            branch = environment.get("deployment_branch_policy") or {}
            exact(
                f"{repository}/{name} protected branches",
                branch.get("protected_branches", False),
                expected.get("protected_branches"),
                errors,
            )
            exact(
                f"{repository}/{name} custom branch policies",
                branch.get("custom_branch_policies", False),
                expected.get("custom_branch_policies"),
                errors,
            )


def audit_custom_properties(
    api: GitHubApi, org: str, desired: dict[str, Any], errors: list[str]
) -> None:
    actual = object_items(api.get(f"/orgs/{org}/properties/schema"), "properties")
    by_name = {item.get("property_name"): item for item in actual}
    exact("custom-property inventory", sorted(by_name), sorted(desired), errors)
    fields = {
        "type": "value_type",
        "required": "required",
        "default_value": "default_value",
        "values": "allowed_values",
        "values_editable_by": "values_editable_by",
    }
    for name, contract in desired.items():
        item = by_name.get(name, {})
        for source, live in fields.items():
            actual_value = item.get(live)
            expected_value = contract.get(source)
            if source == "values":
                actual_value = sorted(actual_value or [])
                expected_value = sorted(expected_value or [])
            exact(f"custom property {name} {source}", actual_value, expected_value, errors)


def audit_repository_property_values(
    api: GitHubApi,
    org: str,
    repositories: dict[str, Any],
    errors: list[str],
) -> None:
    response = api.get(f"/orgs/{org}/properties/values?per_page=100")
    values = object_items(response, "repository_property_values")
    by_repository = {item.get("repository_name"): item for item in values}
    exact("repository custom-property coverage", sorted(by_repository), sorted(repositories), errors)
    fields = {
        "mindclade_repository_class": "repository_class",
        "mindclade_owner_team": "owner_team",
        "mindclade_criticality": "criticality",
        "mindclade_data_classification": "data_classification",
        "mindclade_production_authority": "production_authority",
        "mindclade_ci_profile": "ci_profile",
        "mindclade_language_profile": "language_profile",
        "mindclade_lifecycle": "lifecycle",
    }
    for repository, config in repositories.items():
        item = by_repository.get(repository, {})
        actual = {
            value.get("property_name"): value.get("value")
            for value in item.get("properties", [])
            if isinstance(value, dict)
        }
        expected = {name: config[field] for name, field in fields.items()}
        exact(f"{repository} custom-property values", actual, expected, errors)


def audit_oidc(
    api: GitHubApi,
    org: str,
    repositories: dict[str, Any],
    policy: dict[str, Any],
    errors: list[str],
) -> None:
    exact("OIDC repository opt-in policy", policy.get("repository_opt_in"), False, errors)
    for repository in repositories:
        actual = api.get(f"/repos/{org}/{repository}/actions/oidc/customization/sub")
        exact(f"{repository} OIDC use_default", actual.get("use_default"), True, errors)
        exact(
            f"{repository} OIDC immutable subject",
            actual.get("use_immutable_subject"),
            True,
            errors,
        )
        prefix = str(actual.get("sub_claim_prefix", ""))
        if not re.fullmatch(
            rf"repo:{re.escape(org)}@[0-9]+/{re.escape(repository)}@[0-9]+(?::.*)?",
            prefix,
        ):
            errors.append(
                f"{repository} OIDC subject prefix lacks immutable owner/repository IDs: {prefix!r}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", default=os.environ.get("ORGANIZATION", "mindclade"))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.organization != "mindclade":
        print("ERROR: organization must be mindclade", file=sys.stderr)
        return 2
    api = GitHubApi()
    errors: list[str] = []
    try:
        repositories = load_yaml(ROOT / "catalog/repositories.yaml")
        teams = load_yaml(ROOT / "catalog/teams.yaml")
        environments = load_yaml(ROOT / "catalog/environments.yaml")
        actions = load_yaml(ROOT / "catalog/actions-policy.yaml")
        rulesets = load_yaml(ROOT / "catalog/rulesets.yaml")
        runner_groups = load_yaml(ROOT / "catalog/runner-groups.yaml")
        properties = load_yaml(ROOT / "catalog/custom-properties.yaml")
        oidc = load_yaml(ROOT / "catalog/oidc-policy.yaml")
        adoption = load_yaml(ROOT / "catalog/adoption-inventory.yaml")
        apps = runtime_app_contracts(load_yaml(ROOT / "catalog/github-apps.yaml"))
        apps.update(control_app_contracts(load_yaml(ROOT / "catalog/control-plane-apps.yaml")))
    except AuditError as error:
        errors.append(str(error))
        repositories = teams = environments = actions = rulesets = runner_groups = properties = oidc = adoption = apps = {}

    known = adoption.get("known_existing", [])
    repository_ids = {
        str(item["name"]): int(item["connected_id"])
        for item in known
        if item.get("kind") == "repository" and item.get("connected_id")
    }
    organization_ids = [
        int(item["connected_id"])
        for item in known
        if item.get("kind") == "organization" and item.get("connected_id")
    ]
    organization_id = organization_ids[0] if len(organization_ids) == 1 else None

    try:
        run_check("organization", lambda: audit_organization(api, args.organization, organization_id, errors), errors)
        run_check("repositories", lambda: audit_repositories(api, args.organization, repositories, repository_ids, errors), errors)
        team_ids = run_check("teams", lambda: audit_teams(api, args.organization, teams, errors), errors) or {}
        run_check("Apps", lambda: audit_apps(api, args.organization, apps, errors), errors)
        run_check("Actions", lambda: audit_actions(api, args.organization, actions, errors), errors)
        run_check("rulesets", lambda: audit_rulesets(api, args.organization, rulesets, repositories, errors), errors)
        run_check("runner groups", lambda: audit_runner_groups(api, args.organization, runner_groups, errors), errors)
        run_check(
            "environments",
            lambda: audit_environments(api, args.organization, repositories, environments, team_ids, errors),
            errors,
        )
        run_check("custom properties", lambda: audit_custom_properties(api, args.organization, properties, errors), errors)
        run_check(
            "repository custom properties",
            lambda: audit_repository_property_values(api, args.organization, repositories, errors),
            errors,
        )
        run_check("OIDC", lambda: audit_oidc(api, args.organization, repositories, oidc, errors), errors)
    except AuditTransportError as error:
        errors.append(f"GitHub transport unavailable; remaining checks not attempted: {error}")

    evidence = {
        "schema_version": 1,
        "organization": args.organization,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "qualified": not errors,
        "errors": errors,
    }
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
