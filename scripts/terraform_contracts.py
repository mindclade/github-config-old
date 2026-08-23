#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Semantic Terraform contract inspection for credential-free governance checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import hcl2


class TerraformContractError(ValueError):
    """Raised when Terraform source does not match a required semantic contract."""


@dataclass(frozen=True)
class RequiredStatusRulesetContract:
    """Expected behavior for one required-status-check organization ruleset."""

    path: str
    resource_name: str
    ruleset_name: str
    contexts: tuple[str, ...]
    repositories: tuple[str, ...] = ()
    language_profiles: tuple[str, ...] = ()
    lifecycle_condition: str | None = None
    integration_expression: str | None = None

    def __post_init__(self) -> None:
        if bool(self.repositories) == bool(self.language_profiles):
            raise ValueError(
                f"{self.ruleset_name}: exactly one ruleset selector must be configured"
            )


def load_terraform(path: Path) -> dict[str, Any]:
    """Parse an HCL file and return its structural representation."""

    try:
        with path.open(encoding="utf-8") as handle:
            parsed = hcl2.load(handle)
    except (OSError, ValueError) as exc:
        raise TerraformContractError(f"{path}: cannot parse Terraform: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TerraformContractError(f"{path}: Terraform document is not an object")
    return parsed


def _single(items: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise TerraformContractError(f"{label}: expected exactly one block")
    return items[0]


def _block(body: Mapping[str, Any], name: str, label: str) -> Mapping[str, Any]:
    return _single(body.get(name), f"{label}.{name}")


def _blocks(body: Mapping[str, Any], name: str, label: str) -> list[Mapping[str, Any]]:
    value = body.get(name)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TerraformContractError(f"{label}.{name}: expected block list")
    return value


def _attribute(body: Mapping[str, Any], name: str, label: str) -> Any:
    if name not in body:
        raise TerraformContractError(f"{label}: missing {name} attribute")
    return body[name]


def _string(body: Mapping[str, Any], name: str, label: str) -> str:
    value = _attribute(body, name, label)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        value = value[0]
    if not isinstance(value, str):
        raise TerraformContractError(f"{label}.{name}: expected string")
    return value


def _boolean(body: Mapping[str, Any], name: str, label: str) -> bool:
    value = _attribute(body, name, label)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], bool):
        value = value[0]
    if not isinstance(value, bool):
        raise TerraformContractError(f"{label}.{name}: expected boolean")
    return value


def _literal_list(body: Mapping[str, Any], name: str, label: str) -> list[Any]:
    value = _attribute(body, name, label)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, list):
        raise TerraformContractError(f"{label}.{name}: expected literal list")
    return value


def _normalize_expression(value: str) -> str:
    if value.startswith("${") and value.endswith("}"):
        value = value[2:-1]
    return re.sub(r"\s+", "", value).replace("None", "null")


def _strip_outer_parentheses(value: str) -> str:
    """Remove parser-added parentheses only when they enclose the whole expression."""

    while value.startswith("(") and value.endswith(")"):
        depth = 0
        wraps_all = True
        for index, character in enumerate(value):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    wraps_all = False
                    break
        if not wraps_all or depth != 0:
            break
        value = value[1:-1]
    return value


def _expression(body: Mapping[str, Any], name: str, label: str) -> str:
    return _normalize_expression(_string(body, name, label))


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise TerraformContractError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )


def resource(
    document: Mapping[str, Any], resource_type: str, resource_name: str, label: str
) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []
    for entry in document.get("resource", []):
        if not isinstance(entry, dict):
            continue
        typed = entry.get(resource_type, {})
        if isinstance(typed, dict) and isinstance(typed.get(resource_name), dict):
            matches.append(typed[resource_name])
    if len(matches) != 1:
        raise TerraformContractError(
            f"{label}: expected exactly one {resource_type}.{resource_name} resource"
        )
    return matches[0]


def output(document: Mapping[str, Any], output_name: str, label: str) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []
    for entry in document.get("output", []):
        if isinstance(entry, dict) and isinstance(entry.get(output_name), dict):
            matches.append(entry[output_name])
    if len(matches) != 1:
        raise TerraformContractError(f"{label}: expected exactly one {output_name} output")
    return matches[0]


def check(document: Mapping[str, Any], check_name: str, label: str) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []
    for entry in document.get("check", []):
        if isinstance(entry, dict) and isinstance(entry.get(check_name), dict):
            matches.append(entry[check_name])
    if len(matches) != 1:
        raise TerraformContractError(f"{label}: expected exactly one {check_name} check")
    return matches[0]


def local_value(document: Mapping[str, Any], name: str, label: str) -> Any:
    matches = [
        block[name]
        for block in document.get("locals", [])
        if isinstance(block, dict) and name in block
    ]
    if len(matches) != 1:
        raise TerraformContractError(f"{label}: expected exactly one local.{name}")
    value = matches[0]
    if isinstance(value, list) and len(value) == 1:
        if isinstance(value[0], list) or isinstance(value[0], str):
            return value[0]
    return value


def validate_github_actions_integration_id(root: Path) -> None:
    """Require the GitHub Actions App id to be one exact Terraform integer literal."""

    label = "GitHub Actions integration id"
    document = load_terraform(root / "modules/rulesets/locals.tf")
    value = local_value(document, "github_actions_integration_id", label)
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if type(value) is not int or value != 15368:
        raise TerraformContractError(
            f"{label}: local.github_actions_integration_id must be the literal integer 15368"
        )


def _local_mapping(document: Mapping[str, Any], name: str, label: str) -> Mapping[str, Any]:
    value = local_value(document, name, label)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        raise TerraformContractError(f"{label}: local.{name} must be an object")
    return value


def literal_toset_strings(expression: str, label: str) -> set[str]:
    """Decode a literal ``toset([string, ...])`` across hcl2 render versions."""

    normalized = expression
    if normalized.startswith("${") and normalized.endswith("}"):
        normalized = normalized[2:-1]
    match = re.fullmatch(r"\s*toset\(\[(?P<body>.*)\]\)\s*", normalized, re.DOTALL)
    if not match:
        raise TerraformContractError(f"{label}: expected a literal toset expression")
    body = match.group("body").strip()
    if not body:
        return set()
    values = {
        item.strip().strip("'\"")
        for item in body.split(",")
        if item.strip()
    }
    if any(not re.fullmatch(r"[A-Za-z0-9_.:-]+", item) for item in values):
        raise TerraformContractError(f"{label}: toset contains a non-literal value")
    return values


def _canonical_expression(value: str) -> str:
    return _normalize_expression(value).replace("'", '"').replace("False", "false")


def _validate_bypass(
    body: Mapping[str, Any], expected_for_each: str, label: str
) -> None:
    dynamic_blocks = _blocks(body, "dynamic", label)
    matches = [item["bypass_actors"] for item in dynamic_blocks if "bypass_actors" in item]
    if len(matches) != 1 or not isinstance(matches[0], dict):
        raise TerraformContractError(f"{label}: expected one dynamic bypass_actors block")
    bypass = matches[0]
    _expect(_expression(bypass, "for_each", label), expected_for_each, f"{label}.bypass")
    content = _block(bypass, "content", f"{label}.bypass")
    for name in ("actor_id", "actor_type", "bypass_mode"):
        _expect(
            _expression(content, name, f"{label}.bypass.content"),
            f"bypass_actors.value.{name}",
            f"{label}.bypass.content.{name}",
        )


def _validate_ref_condition(
    conditions: Mapping[str, Any], expected_include: Sequence[str], label: str
) -> None:
    ref_name = _block(conditions, "ref_name", label)
    _expect(_literal_list(ref_name, "include", f"{label}.ref_name"), list(expected_include), f"{label}.ref_name.include")
    _expect(_literal_list(ref_name, "exclude", f"{label}.ref_name"), [], f"{label}.ref_name.exclude")


def validate_required_status_ruleset(
    root: Path,
    contract: RequiredStatusRulesetContract,
    catalog_ruleset: Mapping[str, Any],
) -> None:
    """Validate one required-check resource from parsed HCL and catalog policy."""

    path = root / contract.path
    label = contract.ruleset_name
    body = resource(
        load_terraform(path),
        "github_organization_ruleset",
        contract.resource_name,
        label,
    )
    _expect(_string(body, "name", label), contract.ruleset_name, f"{label}.name")
    _expect(_string(body, "target", label), "branch", f"{label}.target")
    _expect(
        _expression(body, "enforcement", label),
        f'local.enforcement["{contract.ruleset_name}"]',
        f"{label}.enforcement",
    )
    _validate_bypass(body, "local.bypass_incident_response", label)

    conditions = _block(body, "conditions", label)
    _validate_ref_condition(conditions, ["~DEFAULT_BRANCH"], f"{label}.conditions")
    if contract.repositories:
        expected_repositories = list(contract.repositories)
        _expect(
            catalog_ruleset.get("repositories"),
            expected_repositories,
            f"catalog.{label}.repositories",
        )
        repository_name = _block(conditions, "repository_name", f"{label}.conditions")
        _expect(
            _literal_list(repository_name, "include", f"{label}.repository_name"),
            expected_repositories,
            f"{label}.repository_name.include",
        )
        _expect(
            _literal_list(repository_name, "exclude", f"{label}.repository_name"),
            [],
            f"{label}.repository_name.exclude",
        )
        if "repository_property" in conditions:
            raise TerraformContractError(f"{label}: unexpected repository_property selector")
    else:
        expected_profiles = list(contract.language_profiles)
        _expect(
            catalog_ruleset.get("language_profiles"),
            expected_profiles,
            f"catalog.{label}.language_profiles",
        )
        repository_property = _block(
            conditions, "repository_property", f"{label}.conditions"
        )
        include = _literal_list(
            repository_property, "include", f"{label}.repository_property"
        )
        if len(include) != 1 or not isinstance(include[0], dict):
            raise TerraformContractError(
                f"{label}.repository_property.include: expected one property selector"
            )
        _expect(
            include[0],
            {
                "name": "mindclade_language_profile",
                "property_values": expected_profiles,
                "source": "custom",
            },
            f"{label}.repository_property.include",
        )
        if "repository_name" in conditions:
            raise TerraformContractError(f"{label}: unexpected repository_name selector")

    rules = _block(body, "rules", label)
    status_checks = _block(rules, "required_status_checks", f"{label}.rules")
    required_checks = _blocks(
        status_checks, "required_check", f"{label}.status_checks"
    )
    contexts = [
        _string(item, "context", f"{label}.required_check")
        for item in required_checks
    ]
    _expect(contexts, list(contract.contexts), f"{label}.required_check.contexts")
    if contract.integration_expression is not None:
        integration_expressions = [
            _expression(item, "integration_id", f"{label}.required_check")
            for item in required_checks
        ]
        _expect(
            integration_expressions,
            [contract.integration_expression] * len(contract.contexts),
            f"{label}.required_check.integration_ids",
        )
    _expect(
        _boolean(status_checks, "strict_required_status_checks_policy", label),
        True,
        f"{label}.strict_required_status_checks_policy",
    )
    _expect(
        _boolean(status_checks, "do_not_enforce_on_create", label),
        True,
        f"{label}.do_not_enforce_on_create",
    )

    lifecycle = body.get("lifecycle")
    if contract.lifecycle_condition is None:
        if lifecycle:
            raise TerraformContractError(f"{label}: unexpected lifecycle block")
    else:
        lifecycle_body = _single(lifecycle, f"{label}.lifecycle")
        precondition = _block(lifecycle_body, "precondition", f"{label}.lifecycle")
        actual_condition = _strip_outer_parentheses(
            _expression(precondition, "condition", f"{label}.precondition")
        )
        expected_condition = _strip_outer_parentheses(
            _normalize_expression(contract.lifecycle_condition)
        )
        _expect(
            actual_condition,
            expected_condition,
            f"{label}.precondition.condition",
        )


def validate_release_tag_contracts(root: Path) -> None:
    """Validate staged tag creation and no-bypass immutability behavior."""

    creation_label = "release-tag-creation"
    creation = resource(
        load_terraform(root / "modules/rulesets/release-tag-creation.tf"),
        "github_organization_ruleset",
        "release_tag_creation",
        creation_label,
    )
    _expect(_string(creation, "name", creation_label), creation_label, f"{creation_label}.name")
    _expect(_string(creation, "target", creation_label), "tag", f"{creation_label}.target")
    _expect(
        _expression(creation, "enforcement", creation_label),
        'local.enforcement["release-tag-creation"]',
        f"{creation_label}.enforcement",
    )
    _validate_bypass(creation, "local.bypass_release_tag_creation", creation_label)
    creation_conditions = _block(creation, "conditions", creation_label)
    _validate_ref_condition(creation_conditions, ["refs/tags/v*"], f"{creation_label}.conditions")
    creation_repository = _block(
        creation_conditions, "repository_name", f"{creation_label}.conditions"
    )
    _expect(_literal_list(creation_repository, "include", creation_label), ["~ALL"], f"{creation_label}.repository_name.include")
    _expect(_literal_list(creation_repository, "exclude", creation_label), [], f"{creation_label}.repository_name.exclude")
    creation_rules = _block(creation, "rules", creation_label)
    _expect(_boolean(creation_rules, "creation", creation_label), True, f"{creation_label}.rules.creation")
    creation_lifecycle = _single(creation.get("lifecycle"), f"{creation_label}.lifecycle")
    creation_precondition = _block(creation_lifecycle, "precondition", f"{creation_label}.lifecycle")
    actual_creation_condition = _strip_outer_parentheses(
        _expression(creation_precondition, "condition", creation_label)
    )
    qualified_terms = (
        "var.release_tag_creation_control_qualified && "
        "var.release_signer_identity_qualified && "
        'local.enforcement["tag-protection"] == "active"'
    )
    expected_creation_conditions = {
        _normalize_expression(
            'local.enforcement["release-tag-creation"] != "active" || '
            + qualified_terms
        ),
        _normalize_expression(
            'local.enforcement["release-tag-creation"] != "active" || ('
            + qualified_terms
            + ")"
        ),
    }
    if actual_creation_condition not in expected_creation_conditions:
        raise TerraformContractError(
            "release-tag-creation.precondition.condition: qualification boundary changed"
        )

    bypasses = load_terraform(root / "modules/rulesets/bypass.tf")
    release_bypass = local_value(
        bypasses, "bypass_release_tag_creation", "release-tag-creation bypass"
    )
    _expect(
        release_bypass,
        [
            {
                "actor_id": "${var.release_team_id}",
                "actor_type": "Team",
                "bypass_mode": "always",
            }
        ],
        "release-tag-creation bypass actors",
    )

    protection_label = "tag-protection"
    protection = resource(
        load_terraform(root / "modules/rulesets/tag-protection.tf"),
        "github_organization_ruleset",
        "tag_protection",
        protection_label,
    )
    _expect(_string(protection, "name", protection_label), protection_label, f"{protection_label}.name")
    _expect(_string(protection, "target", protection_label), "tag", f"{protection_label}.target")
    _expect(
        _expression(protection, "enforcement", protection_label),
        'local.enforcement["tag-protection"]',
        f"{protection_label}.enforcement",
    )
    _validate_bypass(protection, "local.bypass_none", protection_label)
    protection_conditions = _block(protection, "conditions", protection_label)
    _validate_ref_condition(protection_conditions, ["refs/tags/v*"], f"{protection_label}.conditions")
    protection_repository = _block(
        protection_conditions, "repository_name", f"{protection_label}.conditions"
    )
    _expect(_literal_list(protection_repository, "include", protection_label), ["~ALL"], f"{protection_label}.repository_name.include")
    _expect(_literal_list(protection_repository, "exclude", protection_label), [], f"{protection_label}.repository_name.exclude")
    protection_rules = _block(protection, "rules", protection_label)
    for attribute in ("update", "deletion", "non_fast_forward"):
        _expect(_boolean(protection_rules, attribute, protection_label), True, f"{protection_label}.rules.{attribute}")
    if "creation" in protection_rules:
        raise TerraformContractError("tag-protection rules must not contain creation")
    pattern = _block(protection_rules, "tag_name_pattern", f"{protection_label}.rules")
    _expect(_string(pattern, "name", protection_label), "stable-semver-only", f"{protection_label}.pattern.name")
    _expect(_string(pattern, "operator", protection_label), "regex", f"{protection_label}.pattern.operator")
    parsed_pattern = _string(pattern, "pattern", protection_label).replace(
        "\\\\", "\\"
    )
    _expect(
        parsed_pattern,
        r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
        f"{protection_label}.pattern.pattern",
    )


def validate_environment_handoff(root: Path) -> None:
    """Validate the exact Terraform check enforcing complete environment handoff."""

    document = load_terraform(root / "modules/repositories/environments.tf")
    handoff = check(
        document,
        "environment_project_handoff_is_empty_or_complete",
        "environment project handoff",
    )
    assertion = _block(handoff, "assert", "environment project handoff")
    actual = _expression(assertion, "condition", "environment project handoff")
    required_map = (
        "toset(keys(var.environment_project_ids)) == local.project_required_environments && "
        "alltrue([for name in local.project_required_environments : "
        'trimspace(try(var.environment_project_ids[name], "")) != ""])'
    )
    expected = {
        _normalize_expression(
            "length(var.environment_project_ids) == 0 || " + required_map
        ),
        _normalize_expression(
            "length(var.environment_project_ids) == 0 || (" + required_map + ")"
        ),
    }
    if actual not in expected:
        raise TerraformContractError(
            "environment project handoff condition: complete-or-empty assertion changed"
        )


def validate_oidc_module(root: Path) -> None:
    """Validate immutable-default repository OIDC behavior from parsed HCL."""

    label = "repository OIDC subject"
    document = load_terraform(root / "modules/policies/oidc.tf")
    managed = resource(
        document,
        "github_actions_repository_oidc_subject_claim_customization_template",
        "managed",
        label,
    )
    expected = {
        "for_each": "var.managed_repository_ids",
        "repository": "each.key",
        "use_default": "!var.oidc_policy.repository_opt_in",
        "include_claim_keys": (
            "var.oidc_policy.repository_opt_in?"
            "var.oidc_policy.subject_claim_keys:null"
        ),
    }
    for name, expression in expected.items():
        _expect(_expression(managed, name, label), expression, f"{label}.{name}")
    format_output = output(document, "oidc_subject_format", label)
    _expect(
        _expression(format_output, "value", label),
        _normalize_expression(
            'var.oidc_policy.repository_opt_in ? join(":", '
            '[for key in var.oidc_policy.subject_claim_keys : "${key}=<value>"]) '
            ': "github-immutable-default"'
        ),
        "oidc_subject_format.value",
    )


def validate_import_contract(root: Path) -> None:
    """Validate adoption imports by parsed import and local blocks."""

    label = "declarative adoption imports"
    document = load_terraform(root / "imports.tf")
    imports = document.get("import", [])
    if not isinstance(imports, list) or not all(isinstance(item, dict) for item in imports):
        raise TerraformContractError(f"{label}: import blocks are malformed")
    normalized = [
        {
            name: _expression(item, name, label)
            for name in ("for_each", "to", "id")
            if name in item
        }
        for item in imports
    ]
    required = [
        {
            "to": 'module.repositories.github_repository.this[".github-private"]',
            "id": ".github-private",
        },
        {
            "for_each": "local.preexisting_bootstrap_actions_variables",
            "to": 'module.repositories.github_actions_variable.this["bootstrap:${each.value}"]',
            "id": "bootstrap:${each.value}",
        },
        {
            "for_each": "local.preexisting_repository_environments",
            "to": "module.repositories.github_repository_environment.this[each.value]",
            "id": "each.value",
        },
    ]
    for expected in required:
        if expected not in normalized:
            raise TerraformContractError(f"{label}: missing import {expected!r}")

    environment_expression = local_value(
        document, "preexisting_repository_environments", label
    )
    if not isinstance(environment_expression, str):
        raise TerraformContractError(
            f"{label}: preexisting_repository_environments must be a toset expression"
        )
    forbidden = {"BOOTSTRAP_FOLDER_ID", "AUTOMATION_SECRET_LOCATION"}
    bootstrap_variables = local_value(
        document, "preexisting_bootstrap_actions_variables", label
    )
    if not isinstance(bootstrap_variables, str):
        raise TerraformContractError(
            f"{label}: preexisting_bootstrap_actions_variables must be a toset expression"
        )
    retained = sorted(item for item in forbidden if item in bootstrap_variables)
    if retained:
        raise TerraformContractError(
            f"{label}: retains absent live variables {retained}"
        )


def validate_bazel_cache_ci_variable_contract(root: Path) -> None:
    """Validate the source-to-applied Bazel cache handoff from parsed HCL."""

    label = "repository Bazel cache CI-variable contract"
    document = load_terraform(root / "modules/repositories/ci-variables.tf")
    expected_routes = {
        "pull-request-read": {
            "access": "read",
            "event_name": "pull_request",
            "ref_policy": "pull-request-merge",
            "workflow_path": (
                "mindclade/mindclade-internal-monorepo/.github/workflows/presubmit.yml"
            ),
        },
        "trusted-main-write": {
            "access": "write",
            "event_name": "push",
            "ref_policy": "protected-main",
            "workflow_path": (
                "mindclade/mindclade-internal-monorepo/.github/workflows/presubmit.yml"
            ),
        },
        "merge-group-write": {
            "access": "write",
            "event_name": "merge_group",
            "ref_policy": "protected-merge-queue",
            "workflow_path": (
                "mindclade/mindclade-internal-monorepo/.github/workflows/presubmit.yml"
            ),
        },
        "nightly-write": {
            "access": "write",
            "event_name": "schedule",
            "ref_policy": "protected-main",
            "workflow_path": (
                "mindclade/mindclade-internal-monorepo/.github/workflows/nightly.yml"
            ),
        },
    }
    _expect(
        _local_mapping(document, "bazel_cache_expected_routes", label),
        expected_routes,
        f"{label}.expected_routes",
    )
    _expect(
        _canonical_expression(
            str(local_value(document, "bazel_cache_source_contract_raw", label))
        ),
        _canonical_expression(
            'try(var.ci_variables["infrastructure-live"]["BAZEL_CACHE_IDENTITY_JSON"], "")'
        ),
        f"{label}.source_contract_raw",
    )
    handoff = _local_mapping(document, "bazel_cache_handoff", label)
    expected_handoff = {
        "provider": (
            'try(var.ci_variables["mindclade-internal-monorepo"]'
            '["WIF_PROVIDER_BAZEL_CACHE"], "")'
        ),
        "reader": (
            'try(var.ci_variables["mindclade-internal-monorepo"]'
            '["SA_BAZEL_CACHE_READER"], "")'
        ),
        "writer": (
            'try(var.ci_variables["mindclade-internal-monorepo"]'
            '["SA_BAZEL_CACHE_WRITER"], "")'
        ),
    }
    actual_handoff = {
        name: _canonical_expression(str(value)) for name, value in handoff.items()
    }
    _expect(
        actual_handoff,
        {
            name: _canonical_expression(expression)
            for name, expression in expected_handoff.items()
        },
        f"{label}.handoff",
    )
    _expect(
        _canonical_expression(
            str(local_value(document, "bazel_cache_handoff_values", label))
        ),
        "values(local.bazel_cache_handoff)",
        f"{label}.handoff_values",
    )
    _expect(
        _canonical_expression(
            str(local_value(document, "bazel_remote_cache_state", label))
        ),
        _canonical_expression(
            'try(var.ci_variables["mindclade-internal-monorepo"]'
            '["BAZEL_REMOTE_CACHE_STATE"], "blocked")'
        ),
        f"{label}.activation_state",
    )

    source_check = check(document, "bazel_cache_source_contract_is_exact", label)
    source_assertion = _block(source_check, "assert", f"{label}.source")
    source_condition = _canonical_expression(
        _string(source_assertion, "condition", f"{label}.source")
    )
    required_source_terms = (
        (
            'contains(["","{}"],local.bazel_cache_source_contract_raw)',
            "contains([,{}],local.bazel_cache_source_contract_raw)",
        ),
        ("can(jsondecode(local.bazel_cache_source_contract_raw))",),
        (
            'toset(["workload_identity_provider","repository","repository_owner_id","repository_id","routes"])',
            "toset([workload_identity_provider,repository,repository_owner_id,repository_id,routes])",
        ),
        (
            'local.bazel_cache_source_contract.repository=="mindclade/mindclade-internal-monorepo"',
        ),
        (
            "toset(keys(local.bazel_cache_source_contract.routes))==toset(keys(local.bazel_cache_expected_routes))",
        ),
        (
            'toset(["access","event_name","principal","ref_policy","workflow_path"])',
            "toset([access,event_name,principal,ref_policy,workflow_path])",
        ),
        ("local.bazel_cache_source_contract.routes[route].access==expected.access",),
        (
            "local.bazel_cache_source_contract.routes[route].event_name==expected.event_name",
        ),
        (
            "local.bazel_cache_source_contract.routes[route].ref_policy==expected.ref_policy",
        ),
        (
            "local.bazel_cache_source_contract.routes[route].workflow_path==expected.workflow_path",
        ),
        ("/subject/bazel-cache:${route}",),
        (",false)",),
    )
    missing_source_terms = [
        alternatives[0]
        for alternatives in required_source_terms
        if not any(term in source_condition for term in alternatives)
    ]
    if missing_source_terms:
        raise TerraformContractError(
            f"{label}.source: assertion omits required terms {missing_source_terms}"
        )

    handoff_check = check(document, "bazel_cache_handoff_is_exact", label)
    handoff_assertion = _block(handoff_check, "assert", f"{label}.handoff")
    handoff_condition = _canonical_expression(
        _string(handoff_assertion, "condition", f"{label}.handoff")
    )
    required_handoff_terms = (
        'alltrue([forvalueinlocal.bazel_cache_handoff_values:value==""])',
        'alltrue([forvalueinlocal.bazel_cache_handoff_values:value!=""])',
        "local.bazel_cache_handoff.provider==try(local.bazel_cache_source_contract.workload_identity_provider,\"\")",
        '"bazel-cache-reader@${try(var.ci_variables["mindclade-internal-monorepo"]["CI_PROJECT_ID"],"")}.iam.gserviceaccount.com"',
        '"bazel-cache-writer@${try(var.ci_variables["mindclade-internal-monorepo"]["CI_PROJECT_ID"],"")}.iam.gserviceaccount.com"',
        "local.bazel_cache_handoff.reader!=local.bazel_cache_handoff.writer",
    )
    missing_handoff_terms = [
        term for term in required_handoff_terms if term not in handoff_condition
    ]
    if missing_handoff_terms:
        raise TerraformContractError(
            f"{label}.handoff: assertion omits required terms {missing_handoff_terms}"
        )

    activation_check = check(
        document, "bazel_remote_cache_activation_is_safe", label
    )
    activation_assertion = _block(
        activation_check, "assert", f"{label}.activation"
    )
    activation_condition = _canonical_expression(
        _string(activation_assertion, "condition", f"{label}.activation")
    )
    required_activation_terms = (
        (
            'contains(["blocked","qualified-v1"],local.bazel_remote_cache_state)',
            "contains([blocked,qualified-v1],local.bazel_remote_cache_state)",
        ),
        ('local.bazel_remote_cache_state=="blocked"',),
        (
            'alltrue([forvalueinlocal.bazel_cache_handoff_values:value!=""])',
        ),
        (
            '!contains(["","{}"],local.bazel_cache_source_contract_raw)',
            "!contains([,{}],local.bazel_cache_source_contract_raw)",
        ),
    )
    missing_activation_terms = [
        alternatives[0]
        for alternatives in required_activation_terms
        if not any(term in activation_condition for term in alternatives)
    ]
    if missing_activation_terms:
        raise TerraformContractError(
            f"{label}.activation: assertion omits required terms "
            f"{missing_activation_terms}"
        )


def validate_bootstrap_account_handoff_ci_variable_contract(root: Path) -> None:
    """Validate the applied bootstrap account record from parsed HCL."""

    label = "repository bootstrap account handoff CI-variable contract"
    document = load_terraform(root / "modules/repositories/ci-variables.tf")
    _expect(
        _canonical_expression(
            str(local_value(document, "bootstrap_account_handoff_raw", label))
        ),
        _canonical_expression(
            'try(var.ci_variables["infrastructure-live"]'
            '["BOOTSTRAP_ACCOUNT_HANDOFF_JSON"], "")'
        ),
        f"{label}.raw",
    )
    required_expression = _canonical_expression(
        str(local_value(document, "bootstrap_account_handoff_required", label))
    )
    required_alternatives = {
        _canonical_expression(
            '!contains(["", "{}"], local.bazel_cache_source_contract_raw)'
        ),
        "!contains([,{}],local.bazel_cache_source_contract_raw)",
    }
    if required_expression not in required_alternatives:
        raise TerraformContractError(
            f"{label}.required: bootstrap 1.5 activation expression differs"
        )
    expected_state_buckets = {
        "development": (
            'try(var.ci_variables["infrastructure-live"]'
            '["TFSTATE_BUCKET_DEVELOPMENT"], "")'
        ),
        "staging": (
            'try(var.ci_variables["infrastructure-live"]'
            '["TFSTATE_BUCKET_STAGING"], "")'
        ),
        "production": (
            'try(var.ci_variables["infrastructure-live"]'
            '["TFSTATE_BUCKET_PRODUCTION"], "")'
        ),
    }
    expected_service_accounts = {
        "plan": (
            'try(var.ci_variables["infrastructure-live"]'
            '["SA_TF_LIVE_PLAN"], "")'
        ),
        "foundation": (
            'try(var.ci_variables["infrastructure-live"]'
            '["SA_TF_LIVE_APPLY_FOUNDATION"], "")'
        ),
        "development": (
            'try(var.ci_variables["infrastructure-live"]'
            '["SA_TF_LIVE_APPLY_DEVELOPMENT"], "")'
        ),
        "staging": (
            'try(var.ci_variables["infrastructure-live"]'
            '["SA_TF_LIVE_APPLY_STAGING"], "")'
        ),
        "production": (
            'try(var.ci_variables["infrastructure-live"]'
            '["SA_TF_LIVE_APPLY_PRODUCTION"], "")'
        ),
    }
    for local_name, expected in (
        ("bootstrap_account_handoff_expected_state_buckets", expected_state_buckets),
        (
            "bootstrap_account_handoff_expected_service_accounts",
            expected_service_accounts,
        ),
    ):
        actual = {
            name: _canonical_expression(str(value))
            for name, value in _local_mapping(document, local_name, label).items()
        }
        _expect(
            actual,
            {
                name: _canonical_expression(expression)
                for name, expression in expected.items()
            },
            f"{label}.{local_name}",
        )

    handoff_check = check(document, "bootstrap_account_handoff_is_exact", label)
    assertion = _block(handoff_check, "assert", label)
    condition = _canonical_expression(_string(assertion, "condition", label))
    required_terms = (
        (
            '!local.bootstrap_account_handoff_required?local.bootstrap_account_handoff_raw==""',
            '!local.bootstrap_account_handoff_required?(local.bootstrap_account_handoff_raw=="")',
        ),
        ("can(jsondecode(local.bootstrap_account_handoff_raw))",),
        (
            'toset(["schema_version","bootstrap_contract_version",'
            '"bootstrap_source_commit","platform_contract_sha256",'
            '"state_location","state_buckets","service_accounts"])',
            "toset([schema_version,bootstrap_contract_version,bootstrap_source_commit,"
            "platform_contract_sha256,state_location,state_buckets,service_accounts])",
        ),
        ("local.bootstrap_account_handoff.schema_version==1",),
        (
            'contains(["1.5.0","1.6.0"],local.bootstrap_account_handoff.bootstrap_contract_version)',
            'contains([1.5.0,1.6.0],local.bootstrap_account_handoff.bootstrap_contract_version)',
        ),
        (
            'can(regex("^[0-9a-f]{40}$",local.bootstrap_account_handoff.bootstrap_source_commit))',
        ),
        (
            'can(regex("^sha256:[0-9a-f]{64}$",local.bootstrap_account_handoff.platform_contract_sha256))',
        ),
        ('local.bootstrap_account_handoff.state_location=="US"',),
        (
            'local.bootstrap_account_handoff.state_location=='
            'try(var.ci_variables["infrastructure-live"]["STATE_LOCATION"],"")',
        ),
        (
            "toset(keys(local.bootstrap_account_handoff.state_buckets))=="
            "toset(keys(local.bootstrap_account_handoff_expected_state_buckets))",
        ),
        (
            "local.bootstrap_account_handoff.state_buckets[name]==expected",
        ),
        (
            "toset(keys(local.bootstrap_account_handoff.service_accounts))=="
            "toset(keys(local.bootstrap_account_handoff_expected_service_accounts))",
        ),
        (
            "local.bootstrap_account_handoff.service_accounts[name]==expected",
        ),
        (",false)",),
    )
    missing = [
        alternatives[0]
        for alternatives in required_terms
        if not any(term in condition for term in alternatives)
    ]
    if missing:
        raise TerraformContractError(
            f"{label}: assertion omits required terms {missing}"
        )


def validate_drift_access_expiry(workflow: Mapping[str, Any]) -> None:
    """Validate the access-expiry job from parsed workflow YAML."""

    label = "drift access-expiry"
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict) or not isinstance(jobs.get("access-expiry"), dict):
        raise TerraformContractError(f"{label}: missing job")
    job = jobs["access-expiry"]
    _expect(job.get("if"), "github.ref == 'refs/heads/main'", f"{label}.if")
    _expect(
        job.get("permissions"),
        {"contents": "read", "issues": "write"},
        f"{label}.permissions",
    )
    steps = job.get("steps", [])
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise TerraformContractError(f"{label}: malformed steps")
    expiry_steps = [step for step in steps if step.get("id") == "expiry"]
    if len(expiry_steps) != 1:
        raise TerraformContractError(f"{label}: expected one expiry step")
    expiry_run = expiry_steps[0].get("run")
    if not isinstance(expiry_run, str) or (
        "scripts/check-access-expiry.py --warn-days 14" not in expiry_run
    ):
        raise TerraformContractError(f"{label}: expiry step omits the 14-day check")
    issue_steps = [
        step
        for step in steps
        if step.get("name") == "Open or update the renewal issue"
    ]
    if len(issue_steps) != 1 or issue_steps[0].get("if") != (
        "steps.expiry.outputs.state != 'clean'"
    ):
        raise TerraformContractError(f"{label}: renewal issue step is not fail-closed")
    failure_steps = [step for step in steps if step.get("name") == "Fail on expired access"]
    if len(failure_steps) != 1 or failure_steps[0].get("if") != (
        "steps.expiry.outputs.state == 'expired'"
    ):
        raise TerraformContractError(f"{label}: expired access does not select the failure step")
    failure_run = failure_steps[0].get("run")
    if not isinstance(failure_run, str) or not re.search(r"(^|\n)\s*exit 1\s*($|\n)", failure_run):
        raise TerraformContractError(f"{label}: expired access failure step does not exit 1")


def validate_drift_readiness(workflow: Mapping[str, Any]) -> None:
    """Validate the parsed connected-drift readiness job and fail-closed shell step."""

    label = "drift readiness"
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict) or not isinstance(jobs.get("readiness"), dict):
        raise TerraformContractError(f"{label}: missing job")
    job = jobs["readiness"]
    _expect(
        job.get("outputs"),
        {"enabled": "${{ steps.activation.outputs.enabled }}"},
        f"{label}.outputs",
    )
    steps = job.get("steps", [])
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise TerraformContractError(f"{label}: malformed steps")
    activation_steps = [step for step in steps if step.get("id") == "activation"]
    if len(activation_steps) != 1:
        raise TerraformContractError(f"{label}: expected one activation step")
    activation = activation_steps[0]
    _expect(
        activation.get("env"),
        {
            "CONNECTED_DRIFT_ENABLED": "${{ vars.GOVERNANCE_CONNECTED_DRIFT }}",
            "TF_PLAN_APP_ID": "${{ vars.TF_PLAN_APP_ID }}",
            "TF_GITHUB_PLAN_APP_PEM": "${{ secrets.TF_GITHUB_PLAN_APP_PEM }}",
        },
        f"{label}.activation.env",
    )
    run = activation.get("run")
    if not isinstance(run, str):
        raise TerraformContractError(f"{label}: activation step has no shell program")
    required_program = (
        'if [[ "$CONNECTED_DRIFT_ENABLED" != true ]]',
        'echo "enabled=false" >> "$GITHUB_OUTPUT"',
        'if [[ -z "$TF_PLAN_APP_ID" ]]',
        'if [[ -z "$TF_GITHUB_PLAN_APP_PEM" ]]',
        'if [[ "$missing" -ne 0 ]]',
        'echo "enabled=true" >> "$GITHUB_OUTPUT"',
    )
    missing = [statement for statement in required_program if statement not in run]
    if missing:
        raise TerraformContractError(
            f"{label}: activation program omits required statements: {missing}"
        )
