#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compare connected GitHub governance with the complete source catalog using GETs only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

import yaml

from governance_contracts import (
    GITHUB_ACTIONS_INTEGRATION_ID,
    MERGE_QUEUE_REQUIRED_STATUS_CHECK_CONTEXTS,
    MERGE_QUEUE_ROLLOUT,
)


ROOT = Path(__file__).resolve().parents[1]
SEMVER_TAG = re.compile(
    r"^v(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)$"
)
ROLLOUT_BUNDLE_KEYS = {
    "merge_queue_canary_required_checks",
    "merge_queue_repository_enforcement_overrides",
    "ruleset_enforcement_overrides",
}
ENFORCEMENT_MODES = {"active", "evaluate", "disabled"}
ROLLOUT_CONTEXTS = {
    repository: contexts for repository, contexts, _ in MERGE_QUEUE_ROLLOUT
}
ROLLOUT_PERMANENT_RULESETS = {
    ruleset
    for _, _, rulesets in MERGE_QUEUE_ROLLOUT
    for ruleset in rulesets
}


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


def load_rollout_bundle(
    path: Path,
    rulesets: Mapping[str, Any],
    repositories: Mapping[str, Any],
) -> dict[str, Any]:
    """Load and validate one exact compiler-produced rollout bundle."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot load rollout bundle {path}: {error}") from error
    return validate_rollout_bundle(document, rulesets, repositories)


def validate_rollout_bundle(
    document: Any,
    rulesets: Mapping[str, Any],
    repositories: Mapping[str, Any],
) -> dict[str, Any]:
    """Reject partial, unknown, or internally inconsistent rollout inputs."""

    if not isinstance(document, Mapping):
        raise AuditError("rollout bundle must be an object")
    if set(document) != ROLLOUT_BUNDLE_KEYS:
        raise AuditError(
            "rollout bundle fields must be exactly "
            f"{sorted(ROLLOUT_BUNDLE_KEYS)}"
        )

    ruleset_overrides = document["ruleset_enforcement_overrides"]
    queue_overrides = document["merge_queue_repository_enforcement_overrides"]
    canary_checks = document["merge_queue_canary_required_checks"]
    for label, value in (
        ("ruleset_enforcement_overrides", ruleset_overrides),
        ("merge_queue_repository_enforcement_overrides", queue_overrides),
        ("merge_queue_canary_required_checks", canary_checks),
    ):
        if not isinstance(value, Mapping):
            raise AuditError(f"rollout bundle {label} must be an object")

    known_rulesets = set(rulesets)
    if not set(ruleset_overrides).issubset(known_rulesets):
        raise AuditError("rollout bundle overrides an unknown ruleset")
    if not ROLLOUT_PERMANENT_RULESETS.issubset(ruleset_overrides):
        raise AuditError(
            "rollout bundle must explicitly set every merge-queue permanent ruleset"
        )
    if any(
        not isinstance(value, str) or value not in ENFORCEMENT_MODES
        for value in ruleset_overrides.values()
    ):
        raise AuditError("rollout bundle contains an invalid ruleset enforcement mode")

    merge_queue = rulesets.get("merge-queue", {})
    merge_queue_classes = (
        set(merge_queue.get("classes", []))
        if isinstance(merge_queue, Mapping)
        else set()
    )
    eligible_repositories = {
        name
        for name, config in repositories.items()
        if isinstance(config, Mapping)
        and config.get("repository_class") in merge_queue_classes
    }
    if set(queue_overrides) != eligible_repositories:
        raise AuditError(
            "rollout bundle merge-queue repository overrides must name exactly "
            f"{sorted(eligible_repositories)}"
        )
    if any(
        not isinstance(value, str) or value not in ENFORCEMENT_MODES
        for value in queue_overrides.values()
    ):
        raise AuditError("rollout bundle contains an invalid merge-queue enforcement mode")

    if len(canary_checks) > 1 or not set(canary_checks).issubset(eligible_repositories):
        raise AuditError(
            "rollout bundle canary checks may name at most one eligible repository"
        )
    for repository, contexts in canary_checks.items():
        if not isinstance(contexts, list) or tuple(contexts) != ROLLOUT_CONTEXTS.get(
            repository
        ):
            raise AuditError(
                f"rollout bundle canary contexts for {repository} are not exact"
            )
        if queue_overrides[repository] != "active":
            raise AuditError(
                f"rollout bundle canary repository {repository} must be active"
            )

    global_merge_queue_enforcement = ruleset_overrides.get(
        "merge-queue",
        merge_queue.get("enforcement") if isinstance(merge_queue, Mapping) else None,
    )
    if global_merge_queue_enforcement == "disabled" and canary_checks:
        raise AuditError("rollout bundle cannot configure a canary while merge queue is disabled")

    return {
        "ruleset_enforcement_overrides": dict(ruleset_overrides),
        "merge_queue_repository_enforcement_overrides": dict(queue_overrides),
        "merge_queue_canary_required_checks": {
            name: list(contexts) for name, contexts in canary_checks.items()
        },
    }


def rollout_bundle_sha256(bundle: Mapping[str, Any]) -> str:
    canonical = json.dumps(bundle, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


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
        contract = {
            "repositories": sorted(app.get("repositories", [])),
            "permissions": permissions,
        }
        if "events" in app:
            contract["events"] = sorted(app.get("events", []))
        result[name] = contract
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


def audit_repository_tags(
    api: GitHubApi,
    org: str,
    repositories: dict[str, Any],
    errors: list[str],
    exceptions: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, list[str]]:
    """Inventory tags and allow only exact, unexpired recovery exceptions."""

    inventory: dict[str, list[str]] = {}
    current_date = today or datetime.now(timezone.utc).date()
    tag_exceptions = {
        (str(item.get("repository")), str(item.get("ref"))): item
        for item in (exceptions or {}).get("tag_refs", [])
        if isinstance(item, dict)
    }
    observed_exceptions: set[tuple[str, str]] = set()
    for repository in sorted(repositories):
        tags: list[str] = []
        seen_tags: set[str] = set()
        page = 1
        while True:
            response = api.get(
                f"/repos/{org}/{repository}/tags?per_page=100&page={page}"
            )
            if not isinstance(response, list):
                raise AuditError(f"{repository}: tag response page {page} is not a list")
            for item in response:
                if not isinstance(item, dict):
                    errors.append(f"{repository}: tag entry is not an object")
                    continue
                tag = item.get("name")
                if not isinstance(tag, str) or not tag:
                    errors.append(f"{repository}: malformed tag name {tag!r}")
                    continue
                if tag in seen_tags:
                    raise AuditError(
                        f"{repository}: repeated tag {tag!r} across paginated evidence"
                    )
                seen_tags.add(tag)
                tags.append(tag)
                if not SEMVER_TAG.fullmatch(tag):
                    ref = f"refs/tags/{tag}"
                    key = (repository, ref)
                    exception = tag_exceptions.get(key)
                    if exception is None:
                        errors.append(
                            f"{repository}: non-stable-SemVer tag {tag!r} is forbidden; "
                            "integrate or remove rescue, reconcile, backup, and temporary refs"
                        )
                        continue
                    observed_exceptions.add(key)
                    try:
                        expires_on = date.fromisoformat(str(exception.get("expires_on")))
                    except ValueError:
                        errors.append(f"{repository}: {ref} exception expiry is invalid")
                        continue
                    if current_date > expires_on:
                        errors.append(
                            f"{repository}: {ref} exception expired on {expires_on.isoformat()}"
                        )
                    ref_evidence = api.get(
                        f"/repos/{org}/{repository}/git/ref/tags/{quote(tag, safe='')}"
                    )
                    ref_object = (
                        ref_evidence.get("object")
                        if isinstance(ref_evidence, dict)
                        else None
                    )
                    actual_sha = (
                        ref_object.get("sha") if isinstance(ref_object, dict) else None
                    )
                    exact(
                        f"{repository} temporary tag {ref} object",
                        actual_sha,
                        exception.get("object_sha"),
                        errors,
                    )
            if len(response) < 100:
                break
            page += 1
        inventory[repository] = sorted(tags)
    for key in sorted(set(tag_exceptions) - observed_exceptions):
        errors.append(f"temporary tag exception was not observed: {key[0]} {key[1]}")
    return inventory


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
        if "events" in contract:
            exact(
                f"{name} events",
                sorted(installation.get("events", [])),
                contract["events"],
                errors,
            )
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
    rulesets: dict[str, Any],
    repositories: dict[str, Any],
    rollout_bundle: Mapping[str, Any] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    organization: dict[str, dict[str, str]] = {}
    repository: dict[str, dict[str, dict[str, str]]] = {
        name: {} for name in repositories
    }
    ruleset_overrides = (
        rollout_bundle.get("ruleset_enforcement_overrides", {})
        if rollout_bundle is not None
        else {}
    )
    queue_overrides = (
        rollout_bundle.get("merge_queue_repository_enforcement_overrides", {})
        if rollout_bundle is not None
        else {}
    )
    for name, config in rulesets.items():
        target = (
            "push"
            if name == "push-blocklist"
            else "tag"
            if name in {"release-tag-creation", "tag-protection"}
            else "branch"
        )
        effective_enforcement = str(
            ruleset_overrides.get(name, config["enforcement"])
        )
        if name == "merge-queue":
            for repository_name, repository_config in repositories.items():
                if repository_config.get("repository_class") in config.get("classes", []):
                    repository_enforcement = (
                        "disabled"
                        if effective_enforcement == "disabled"
                        else str(
                            queue_overrides.get(
                                repository_name,
                                effective_enforcement,
                            )
                        )
                    )
                    repository[repository_name][name] = {
                        "target": target,
                        "enforcement": repository_enforcement,
                    }
        else:
            organization[name] = {
                "target": target,
                "enforcement": effective_enforcement,
            }
    return organization, repository


def ruleset_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        str(item.get("name")): {
            "target": str(item.get("target")),
            "enforcement": str(item.get("enforcement")),
        }
        for item in items
    }


def ruleset_bypass_summary(item: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "actor_id": actor.get("actor_id"),
                "actor_type": actor.get("actor_type"),
                "bypass_mode": actor.get("bypass_mode"),
            }
            for actor in item.get("bypass_actors", [])
            if isinstance(actor, dict)
        ],
        key=lambda actor: (
            str(actor["actor_type"]),
            str(actor["actor_id"]),
            str(actor["bypass_mode"]),
        ),
    )


def _canonical_conditions(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    result: dict[str, Any] = {}
    for name, condition in value.items():
        if not isinstance(condition, Mapping):
            result[str(name)] = condition
            continue
        if name in {"ref_name", "repository_name"}:
            normalized = {
                "exclude": sorted(condition.get("exclude", [])),
                "include": sorted(condition.get("include", [])),
            }
            if name == "repository_name":
                normalized["protected"] = bool(condition.get("protected", False))
            result[str(name)] = normalized
            continue
        if name == "repository_property":
            include = []
            for item in condition.get("include", []):
                if not isinstance(item, Mapping):
                    include.append(item)
                    continue
                include.append(
                    {
                        "name": item.get("name"),
                        "property_values": sorted(item.get("property_values", [])),
                        "source": item.get("source"),
                    }
                )
            result[str(name)] = {
                "exclude": condition.get("exclude", []),
                "include": sorted(
                    include,
                    key=lambda item: json.dumps(item, sort_keys=True),
                ),
            }
            continue
        result[str(name)] = dict(condition)
    return result


def _canonical_rules(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    result: list[Any] = []
    for rule in value:
        if not isinstance(rule, Mapping):
            result.append(rule)
            continue
        normalized = dict(rule)
        parameters = normalized.get("parameters")
        if rule.get("type") == "required_status_checks" and isinstance(
            parameters, Mapping
        ):
            normalized_parameters = dict(parameters)
            checks = parameters.get("required_status_checks")
            if isinstance(checks, list):
                normalized_parameters["required_status_checks"] = sorted(
                    [dict(check) if isinstance(check, Mapping) else check for check in checks],
                    key=lambda check: json.dumps(check, sort_keys=True),
                )
            normalized["parameters"] = normalized_parameters
        result.append(normalized)
    return sorted(result, key=lambda rule: json.dumps(rule, sort_keys=True))


def _incident_response_bypass(
    team_ids: Mapping[str, int], errors: list[str]
) -> list[dict[str, Any]]:
    missing = sorted({"platform", "security"} - set(team_ids))
    if missing:
        errors.append(
            "rollout rulesets: immutable incident-response team ids are absent: "
            + ", ".join(missing)
        )
    return sorted(
        [
            {
                "actor_id": team_ids[name],
                "actor_type": "Team",
                "bypass_mode": "pull_request",
            }
            for name in ("platform", "security")
            if name in team_ids
        ],
        key=lambda actor: str(actor["actor_id"]),
    )


def _required_status_checks_rule(contexts: tuple[str, ...] | list[str]) -> dict[str, Any]:
    return {
        "parameters": {
            "do_not_enforce_on_create": True,
            "required_status_checks": [
                {
                    "context": context,
                    "integration_id": GITHUB_ACTIONS_INTEGRATION_ID,
                }
                for context in contexts
            ],
            "strict_required_status_checks_policy": True,
        },
        "type": "required_status_checks",
    }


def _permanent_ruleset_conditions(config: Mapping[str, Any]) -> dict[str, Any]:
    conditions: dict[str, Any] = {
        "ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}
    }
    repositories = config.get("repositories")
    language_profiles = config.get("language_profiles")
    if isinstance(repositories, list):
        conditions["repository_name"] = {
            "exclude": [],
            "include": repositories,
            "protected": False,
        }
    elif isinstance(language_profiles, list):
        conditions["repository_property"] = {
            "exclude": [],
            "include": [
                {
                    "name": "mindclade_language_profile",
                    "property_values": language_profiles,
                    "source": "custom",
                }
            ],
        }
    else:
        raise AuditError("rollout permanent ruleset has no exact repository condition")
    return conditions


def _ruleset_detail(
    api: GitHubApi,
    path_prefix: str,
    by_name: Mapping[str, Mapping[str, Any]],
    name: str,
    errors: list[str],
) -> dict[str, Any] | None:
    ruleset_id = by_name.get(name, {}).get("id")
    if not isinstance(ruleset_id, int):
        errors.append(f"{name}: connected ruleset detail id is absent")
        return None
    detail = api.get(f"{path_prefix}/{ruleset_id}")
    if not isinstance(detail, dict):
        errors.append(f"{name}: connected ruleset detail is not an object")
        return None
    return detail


def audit_rollout_permanent_rulesets(
    api: GitHubApi,
    org: str,
    actual_org: list[dict[str, Any]],
    rulesets: Mapping[str, Mapping[str, Any]],
    team_ids: Mapping[str, int],
    errors: list[str],
) -> None:
    """Read back exact live composition for every permanent merge-queue gate."""

    by_name = {
        str(item.get("name")): item
        for item in actual_org
        if isinstance(item, Mapping)
    }
    expected_bypass = _incident_response_bypass(team_ids, errors)
    for name, contexts in MERGE_QUEUE_REQUIRED_STATUS_CHECK_CONTEXTS.items():
        detail = _ruleset_detail(
            api, f"/orgs/{org}/rulesets", by_name, name, errors
        )
        if detail is None:
            continue
        config = rulesets.get(name)
        if not isinstance(config, Mapping):
            errors.append(f"{name}: source ruleset contract is absent")
            continue
        exact(
            f"{name} conditions",
            _canonical_conditions(detail.get("conditions")),
            _canonical_conditions(_permanent_ruleset_conditions(config)),
            errors,
        )
        exact(
            f"{name} bypass actors",
            ruleset_bypass_summary(detail),
            expected_bypass,
            errors,
        )
        exact(
            f"{name} rules",
            _canonical_rules(detail.get("rules")),
            _canonical_rules([_required_status_checks_rule(contexts)]),
            errors,
        )


def audit_merge_queue_ruleset(
    api: GitHubApi,
    org: str,
    repository: str,
    actual: list[dict[str, Any]],
    team_ids: Mapping[str, int],
    canary_contexts: list[str],
    errors: list[str],
) -> None:
    """Read back exact repository-local queue, canary, scope, and bypass policy."""

    by_name = {
        str(item.get("name")): item
        for item in actual
        if isinstance(item, Mapping)
    }
    detail = _ruleset_detail(
        api,
        f"/repos/{org}/{repository}/rulesets",
        by_name,
        "merge-queue",
        errors,
    )
    if detail is None:
        return
    exact(
        f"{repository} merge-queue conditions",
        _canonical_conditions(detail.get("conditions")),
        {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
        errors,
    )
    exact(
        f"{repository} merge-queue bypass actors",
        ruleset_bypass_summary(detail),
        _incident_response_bypass(team_ids, errors),
        errors,
    )
    expected_rules: list[dict[str, Any]] = []
    if canary_contexts:
        expected_rules.append(_required_status_checks_rule(canary_contexts))
    expected_rules.append(
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
        }
    )
    exact(
        f"{repository} merge-queue rules",
        _canonical_rules(detail.get("rules")),
        _canonical_rules(expected_rules),
        errors,
    )


def audit_release_tag_rulesets(
    api: GitHubApi,
    org: str,
    actual_org: list[dict[str, Any]],
    team_ids: dict[str, int],
    errors: list[str],
) -> None:
    """Verify the detailed composition which list-ruleset responses do not expose."""

    by_name = {str(item.get("name")): item for item in actual_org}
    details: dict[str, dict[str, Any]] = {}
    for name in ("release-tag-creation", "tag-protection"):
        ruleset_id = by_name.get(name, {}).get("id")
        if not isinstance(ruleset_id, int):
            errors.append(f"{name}: connected ruleset detail id is absent")
            continue
        detail = api.get(f"/orgs/{org}/rulesets/{ruleset_id}")
        if not isinstance(detail, dict):
            errors.append(f"{name}: connected ruleset detail is not an object")
            continue
        details[name] = detail
        conditions = detail.get("conditions", {})
        ref_name = conditions.get("ref_name", {})
        repository_name = conditions.get("repository_name", {})
        exact(
            f"{name} ref conditions",
            {
                "exclude": ref_name.get("exclude"),
                "include": ref_name.get("include"),
            },
            {"exclude": [], "include": ["refs/tags/v*"]},
            errors,
        )
        exact(
            f"{name} repository conditions",
            {
                "exclude": repository_name.get("exclude"),
                "include": repository_name.get("include"),
                "protected": bool(repository_name.get("protected", False)),
            },
            {"exclude": [], "include": ["~ALL"], "protected": False},
            errors,
        )

    creation = details.get("release-tag-creation")
    if creation is not None:
        expected_bypass = (
            [
                {
                    "actor_id": team_ids["release"],
                    "actor_type": "Team",
                    "bypass_mode": "always",
                }
            ]
            if "release" in team_ids
            else []
        )
        if "release" not in team_ids:
            errors.append("release-tag-creation: immutable Release team id is absent")
        exact(
            "release-tag-creation bypass actors",
            ruleset_bypass_summary(creation),
            expected_bypass,
            errors,
        )
        exact(
            "release-tag-creation rules",
            creation.get("rules"),
            [{"type": "creation"}],
            errors,
        )

    protection = details.get("tag-protection")
    if protection is not None:
        exact(
            "tag-protection bypass actors",
            ruleset_bypass_summary(protection),
            [],
            errors,
        )
        expected_rules = [
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
        ]
        actual_rules = sorted(
            [rule for rule in protection.get("rules", []) if isinstance(rule, dict)],
            key=lambda rule: str(rule.get("type")),
        )
        exact("tag-protection rules", actual_rules, expected_rules, errors)


def audit_rulesets(
    api: GitHubApi,
    org: str,
    rulesets: dict[str, Any],
    repositories: dict[str, Any],
    team_ids: dict[str, int],
    errors: list[str],
    rollout_bundle: Mapping[str, Any] | None = None,
) -> None:
    expected_org, expected_repos = expected_rulesets(
        rulesets, repositories, rollout_bundle
    )
    actual_org = object_items(
        api.get(f"/orgs/{org}/rulesets?includes_parents=false&per_page=100"), "rulesets"
    )
    exact("organization rulesets", ruleset_summary(actual_org), expected_org, errors)
    audit_release_tag_rulesets(api, org, actual_org, team_ids, errors)
    audit_rollout_permanent_rulesets(
        api, org, actual_org, rulesets, team_ids, errors
    )
    canary_checks = (
        rollout_bundle.get("merge_queue_canary_required_checks", {})
        if rollout_bundle is not None
        else {}
    )
    for repository, expected in expected_repos.items():
        actual = object_items(
            api.get(
                f"/repos/{org}/{repository}/rulesets?includes_parents=false&per_page=100"
            ),
            "rulesets",
        )
        exact(f"{repository} repository rulesets", ruleset_summary(actual), expected, errors)
        if "merge-queue" in expected:
            audit_merge_queue_ruleset(
                api,
                org,
                repository,
                actual,
                team_ids,
                list(canary_checks.get(repository, [])),
                errors,
            )


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
    exceptions: dict[str, Any] | None = None,
) -> None:
    environment_exceptions = {
        (str(item.get("repository")), str(item.get("name"))): item
        for item in (exceptions or {}).get("repository_environments", [])
        if isinstance(item, dict)
    }
    for repository, config in repositories.items():
        response = api.get(f"/repos/{org}/{repository}/environments?per_page=100")
        actual = object_items(response, "environments")
        by_name = {item.get("name"): item for item in actual}
        expected_names = list(config.get("environments", [])) + [
            name
            for exception_repository, name in environment_exceptions
            if exception_repository == repository
        ]
        exact(f"{repository} environments", sorted(by_name), sorted(expected_names), errors)
        for name in config.get("environments", []):
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
        for (exception_repository, name), contract in environment_exceptions.items():
            if exception_repository != repository or name not in by_name:
                continue
            environment = api.get(f"/repos/{org}/{repository}/environments/{name}")
            exact(
                f"{repository}/{name} platform protection rules",
                len(environment.get("protection_rules", [])),
                contract.get("allowed_protection_rules"),
                errors,
            )
            exact(
                f"{repository}/{name} platform wait timer",
                environment.get("wait_timer", 0),
                0,
                errors,
            )
            exact(
                f"{repository}/{name} platform self review",
                environment.get("prevent_self_review", False),
                False,
                errors,
            )
            secrets = object_items(
                api.get(
                    f"/repos/{org}/{repository}/environments/{name}/secrets?per_page=100"
                ),
                "secrets",
            )
            variables = object_items(
                api.get(
                    f"/repos/{org}/{repository}/environments/{name}/variables?per_page=100"
                ),
                "variables",
            )
            exact(
                f"{repository}/{name} platform secrets",
                len(secrets),
                contract.get("allowed_secrets"),
                errors,
            )
            exact(
                f"{repository}/{name} platform variables",
                len(variables),
                contract.get("allowed_variables"),
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
    parser.add_argument("--rollout-bundle", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.organization != "mindclade":
        print("ERROR: organization must be mindclade", file=sys.stderr)
        return 2
    api = GitHubApi()
    errors: list[str] = []
    rollout_bundle: dict[str, Any] | None = None
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
        connected_exceptions = load_yaml(
            ROOT / "catalog/connected-resource-exceptions.yaml"
        )
        apps = runtime_app_contracts(load_yaml(ROOT / "catalog/github-apps.yaml"))
        apps.update(control_app_contracts(load_yaml(ROOT / "catalog/control-plane-apps.yaml")))
    except AuditError as error:
        errors.append(str(error))
        repositories = teams = environments = actions = rulesets = runner_groups = properties = oidc = adoption = connected_exceptions = apps = {}

    if args.rollout_bundle is not None:
        try:
            rollout_bundle = load_rollout_bundle(
                args.rollout_bundle, rulesets, repositories
            )
        except AuditError as error:
            errors.append(str(error))

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
    tag_inventory: dict[str, list[str]] = {}

    try:
        run_check("organization", lambda: audit_organization(api, args.organization, organization_id, errors), errors)
        run_check("repositories", lambda: audit_repositories(api, args.organization, repositories, repository_ids, errors), errors)
        tag_inventory = run_check(
            "release tags",
            lambda: audit_repository_tags(
                api,
                args.organization,
                repositories,
                errors,
                connected_exceptions,
            ),
            errors,
        ) or {}
        team_ids = run_check("teams", lambda: audit_teams(api, args.organization, teams, errors), errors) or {}
        run_check("Apps", lambda: audit_apps(api, args.organization, apps, errors), errors)
        run_check("Actions", lambda: audit_actions(api, args.organization, actions, errors), errors)
        run_check(
            "rulesets",
            lambda: audit_rulesets(
                api,
                args.organization,
                rulesets,
                repositories,
                team_ids,
                errors,
                rollout_bundle,
            ),
            errors,
        )
        run_check("runner groups", lambda: audit_runner_groups(api, args.organization, runner_groups, errors), errors)
        run_check(
            "environments",
            lambda: audit_environments(
                api,
                args.organization,
                repositories,
                environments,
                team_ids,
                errors,
                connected_exceptions,
            ),
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
        "release_tags": tag_inventory,
        "connected_resource_exceptions": connected_exceptions,
        "rollout_bundle": rollout_bundle,
        "rollout_bundle_sha256": (
            rollout_bundle_sha256(rollout_bundle)
            if rollout_bundle is not None
            else None
        ),
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
