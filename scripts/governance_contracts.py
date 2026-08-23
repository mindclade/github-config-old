#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Pure governance invariants shared by catalog validation and regression tests."""

from __future__ import annotations

import re
from typing import Any, Mapping


EVIDENCE_GATED_RULESET_GATES = {
    "release-tag-creation": (
        "release_tag_creation_control_qualified",
        "release_signer_identity_qualified",
    ),
    "required-checks-bootstrap": ("bootstrap_verdict_observed",),
    "required-checks-github-config": ("github_config_verdict_observed",),
    "required-checks-go": (
        "monorepo_bazel_verdict_observed",
        "monorepo_merge_group_full_graph_observed",
        "rulesets_connected_audit",
    ),
    "required-checks-mixed": (
        "monorepo_bazel_verdict_observed",
        "monorepo_merge_group_full_graph_observed",
        "rulesets_connected_audit",
    ),
    "required-checks-infra-static": (
        "monorepo_merge_group_full_graph_observed",
        "rulesets_connected_audit",
    ),
    "required-checks-nix": ("nix_estate_qualified",),
    "ruleset-workflows": (
        "independent_reviewer_available",
        "v5_release_published",
        "release_environments_qualified",
    ),
}

GITHUB_ACTIONS_INTEGRATION_ID = 15368
MERGE_QUEUE_REQUIRED_STATUS_CHECK_CONTEXTS = {
    "required-checks-go": (
        "ci / build",
        "codeql-go / analyze (go)",
    ),
    "required-checks-mixed": (
        "python / build",
        "rust / build",
        "architecture",
        "Go registry + admission / live PostgreSQL and failure injection",
        "bazel / verdict",
    ),
    "required-checks-infra-static": ("infra-static",),
    "required-checks-gitops": (
        "contract",
        "lint",
        "schema",
        "policy",
        "exemptions",
        "promotion-integrity",
        "repository-invariants",
    ),
    "required-checks-tf": ("fmt", "validate", "plan"),
    "required-checks-tf-static-infrastructure-live": ("tflint", "checkov"),
}
MERGE_QUEUE_REPOSITORY_RULESETS = (
    (
        "mindclade-internal-monorepo",
        (
            "required-checks-go",
            "required-checks-mixed",
            "required-checks-infra-static",
        ),
    ),
    (
        "gitops",
        ("required-checks-gitops",),
    ),
    (
        "infrastructure-live",
        (
            "required-checks-tf",
            "required-checks-tf-static-infrastructure-live",
        ),
    ),
)
MERGE_QUEUE_ROLLOUT = tuple(
    (
        repository,
        tuple(
            context
            for ruleset in permanent_rulesets
            for context in MERGE_QUEUE_REQUIRED_STATUS_CHECK_CONTEXTS[ruleset]
        ),
        permanent_rulesets,
    )
    for repository, permanent_rulesets in MERGE_QUEUE_REPOSITORY_RULESETS
)
MERGE_QUEUE_EVIDENCE_FIELDS = (
    "positive_pull_request",
    "positive_merge_group",
    "intentional_negative_merge_group",
    "permanent_ruleset_audit",
)
MERGE_QUEUE_EVIDENCE_EXPECTATIONS = {
    "positive_pull_request": ("pull_request", "success"),
    "positive_merge_group": ("merge_group", "success"),
    "intentional_negative_merge_group": ("merge_group", "failure"),
    "permanent_ruleset_audit": ("workflow_dispatch", "success"),
}
MERGE_QUEUE_RUN_URL = re.compile(
    r"https://github\.com/mindclade/(?P<repository>[A-Za-z0-9_.-]+)/actions/runs/[1-9][0-9]*"
)

EXPECTED_RUNNER_GROUPS = {
    "mindclade-arc-artifact-authority": {
        "visibility": "selected",
        "allowsPublicRepositories": False,
        "restrictedToWorkflows": True,
        "repositories": ("mindclade-internal-monorepo",),
        "workflows": (
            "mindclade/.github/.github/workflows/reusable-arc-wif-canary.yml@v5.0.0",
            "mindclade/.github/.github/workflows/reusable-arc-oci-build.yml@v5.0.0",
            "mindclade/.github/.github/workflows/reusable-arc-oci-qualify.yml@v5.0.0",
            "mindclade/.github/.github/workflows/reusable-arc-qualification-attest.yml@v5.0.0",
        ),
    },
    "mindclade-arc-ci": {
        "visibility": "selected",
        "allowsPublicRepositories": False,
        "restrictedToWorkflows": True,
        "repositories": ("mindclade-internal-monorepo",),
        "workflows": (
            "mindclade/mindclade-internal-monorepo/.github/workflows/presubmit.yml@refs/heads/main",
        ),
    },
}


def dr_evidence_workflow_errors(
    workflow: Mapping[str, Any], v5_release_status: str | None
) -> list[str]:
    """Keep DR publication fail-closed until its immutable workflow release exists."""

    errors: list[str] = []
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, Mapping):
        return ["dr-evidence.yml jobs must be an object"]
    if v5_release_status == "blocked":
        if workflow.get("permissions") != {}:
            errors.append(
                "dr-evidence.yml must have no permissions while v5 publication is blocked"
            )
        if set(jobs) != {"activation-blocked"}:
            errors.append(
                "dr-evidence.yml must expose only the fail-closed job while v5 is blocked"
            )
        blocked_job = jobs.get("activation-blocked", {})
        if not isinstance(blocked_job, Mapping):
            errors.append("dr-evidence.yml blocked job must be an object")
            return errors
        if blocked_job.get("permissions") != {}:
            errors.append("dr-evidence.yml blocked job must have no permissions")
        if blocked_job.get("environment") is not None:
            errors.append(
                "dr-evidence.yml blocked job must not enter a protected cloud environment"
            )
        blocked_steps = str(blocked_job.get("steps", []))
        if "reusable-dr-evidence.yml" in blocked_steps or "id-token" in blocked_steps:
            errors.append(
                "dr-evidence.yml blocked job must not retain publication authority"
            )
        if "exit 1" not in blocked_steps:
            errors.append("dr-evidence.yml blocked job must fail explicitly")
    elif v5_release_status == "qualified":
        if workflow.get("permissions") != {"contents": "read", "id-token": "write"}:
            errors.append(
                "dr-evidence.yml active caller must have exact top-level permissions"
            )
        if set(jobs) != {"publish"}:
            errors.append(
                "dr-evidence.yml must expose only publish after v5 qualification"
            )
        publish_job = jobs.get("publish", {})
        if not isinstance(publish_job, Mapping):
            errors.append("dr-evidence.yml publish job must be an object")
            return errors
        if publish_job.get("uses") != (
            "mindclade/.github/.github/workflows/reusable-dr-evidence.yml@v5.0.0"
        ):
            errors.append(
                "dr-evidence.yml active caller must use the qualified immutable v5 workflow"
            )
        if publish_job.get("permissions") != {
            "actions": "read",
            "contents": "read",
            "id-token": "write",
        }:
            errors.append("dr-evidence.yml active caller job permissions are not exact")
        expected_inputs = {
            "report-path": "${{ inputs.report_path }}",
            "environment": "${{ inputs.environment }}",
            "primary-operator": "${{ github.actor }}",
            "observer-operator": "${{ inputs.observer_operator }}",
        }
        if publish_job.get("with") != expected_inputs:
            errors.append("dr-evidence.yml active caller inputs are not exact")
    else:
        errors.append("v5_release_published must be blocked or qualified")
    return errors


def runner_group_contract_errors(runner_groups: Mapping[str, Any]) -> list[str]:
    """Require distinct, least-privilege release and presubmit runner groups."""

    errors: list[str] = []
    if set(runner_groups) != set(EXPECTED_RUNNER_GROUPS):
        errors.append("ARC runner-group inventory is not exact")
        return errors
    for name, expected in EXPECTED_RUNNER_GROUPS.items():
        actual = runner_groups.get(name)
        if not isinstance(actual, Mapping):
            errors.append(f"ARC runner group {name}: contract must be an object")
            continue
        for field in (
            "visibility",
            "allowsPublicRepositories",
            "restrictedToWorkflows",
        ):
            if actual.get(field) != expected[field]:
                errors.append(f"ARC runner group {name}: {field} is not exact")
        for field in ("repositories", "workflows"):
            values = actual.get(field)
            if not isinstance(values, list) or set(values) != set(expected[field]):
                errors.append(f"ARC runner group {name}: {field} is not exact")
    return errors


def resting_ruleset_errors(
    rulesets: Mapping[str, Mapping[str, Any]],
    expected_enforcement: Mapping[str, str],
) -> list[str]:
    """Require fixed rules to match their resting state without freezing gated rules."""

    errors: list[str] = []
    for ruleset_name, expected in expected_enforcement.items():
        if ruleset_name in EVIDENCE_GATED_RULESET_GATES:
            continue
        actual = rulesets.get(ruleset_name, {}).get("enforcement")
        if actual != expected:
            errors.append(
                f"ruleset {ruleset_name}: resting enforcement must be {expected}; "
                "use the reviewed enforcement override only for a time-bounded rollout"
            )
    return errors


def evidence_gated_ruleset_errors(
    rulesets: Mapping[str, Mapping[str, Any]],
    activation_gates: Mapping[str, Any],
) -> list[str]:
    """Return fail-closed errors for evidence-gated ruleset promotion."""

    errors: list[str] = []
    for ruleset_name, required_gates in EVIDENCE_GATED_RULESET_GATES.items():
        enforcement = rulesets.get(ruleset_name, {}).get("enforcement")
        if enforcement not in {"evaluate", "active"}:
            errors.append(
                f"ruleset {ruleset_name}: enforcement must be evaluate or active"
            )
            continue
        if enforcement != "active":
            continue
        blocked_gates = [
            name for name in required_gates if activation_gates.get(name) != "qualified"
        ]
        if blocked_gates:
            errors.append(
                f"ruleset {ruleset_name}: active enforcement requires qualified gates "
                f"{list(required_gates)}; blocked: {blocked_gates}"
            )
    return errors


def required_check_readiness_errors(
    readiness: Mapping[str, Any],
    activation_gates: Mapping[str, Any],
    ruleset_contexts: Mapping[str, tuple[str, ...]],
) -> list[str]:
    """Return errors when deferred checks and activation evidence disagree."""

    errors: list[str] = []
    contexts = readiness.get("contexts", {})
    if not isinstance(contexts, dict):
        return ["required-check readiness contexts must be an object"]
    for name, raw_contract in contexts.items():
        if not isinstance(raw_contract, dict):
            errors.append(f"required-check readiness {name}: contract must be an object")
            continue
        target_ruleset = str(raw_contract.get("target_ruleset"))
        activation_gate = str(raw_contract.get("activation_gate"))
        status = raw_contract.get("status")
        actual_contexts = set(ruleset_contexts.get(target_ruleset, ()))
        candidate_context = raw_contract.get("candidate_context")
        required_events = set(raw_contract.get("required_events", []))
        observed_events = set(raw_contract.get("observed_events", []))
        intentional_negative_observed = raw_contract.get(
            "intentional_negative_observed"
        )
        qualified_context = raw_contract.get("qualified_context")
        if status == "blocked":
            if activation_gates.get(activation_gate) != "blocked":
                errors.append(
                    f"required-check readiness {name}: blocked status requires a blocked "
                    f"{activation_gate} gate"
                )
            if candidate_context in actual_contexts:
                errors.append(
                    f"required-check readiness {name}: candidate context must not be required "
                    "while connected evidence is blocked"
                )
            if qualified_context is not None:
                errors.append(
                    f"required-check readiness {name}: blocked status cannot name a qualified context"
                )
        elif status == "qualified":
            if activation_gates.get(activation_gate) != "qualified":
                errors.append(
                    f"required-check readiness {name}: qualified status requires a qualified "
                    f"{activation_gate} gate"
                )
            if qualified_context != candidate_context or qualified_context not in actual_contexts:
                errors.append(
                    f"required-check readiness {name}: candidate context must be the qualified "
                    f"context present in {target_ruleset}"
                )
            if observed_events != required_events:
                errors.append(
                    f"required-check readiness {name}: qualified status requires connected "
                    "evidence for every required event"
                )
            if intentional_negative_observed is not True:
                errors.append(
                    f"required-check readiness {name}: qualified status requires reviewed "
                    "intentional-negative evidence"
                )
        else:
            errors.append(
                f"required-check readiness {name}: status must be blocked or qualified"
            )
    return errors


def merge_queue_readiness_errors(readiness: Mapping[str, Any]) -> list[str]:
    """Require an exact, sequential, immutable merge-queue qualification record."""

    errors: list[str] = []
    if readiness.get("schema_version") != 1:
        errors.append("merge-queue readiness schema_version must be 1")
    rollout = readiness.get("rollout_order")
    if not isinstance(rollout, list):
        return errors + ["merge-queue readiness rollout_order must be an array"]
    expected_repositories = tuple(item[0] for item in MERGE_QUEUE_ROLLOUT)
    actual_repositories = tuple(
        item.get("repository") if isinstance(item, Mapping) else None
        for item in rollout
    )
    if actual_repositories != expected_repositories:
        errors.append(
            "merge-queue readiness repository order must be exactly "
            f"{list(expected_repositories)}"
        )
        return errors

    seen_unqualified = False
    seen_canary = False
    observed_run_urls: list[str] = []
    for raw_contract, (repository, contexts, rulesets) in zip(
        rollout, MERGE_QUEUE_ROLLOUT
    ):
        if not isinstance(raw_contract, Mapping):
            errors.append(f"merge-queue readiness {repository}: contract must be an object")
            continue
        if raw_contract.get("github_actions_integration_id") != GITHUB_ACTIONS_INTEGRATION_ID:
            errors.append(
                f"merge-queue readiness {repository}: GitHub Actions integration id must be "
                f"{GITHUB_ACTIONS_INTEGRATION_ID}"
            )
        if tuple(raw_contract.get("required_contexts", ())) != contexts:
            errors.append(
                f"merge-queue readiness {repository}: required contexts are not exact"
            )
        if tuple(raw_contract.get("permanent_rulesets", ())) != rulesets:
            errors.append(
                f"merge-queue readiness {repository}: permanent rulesets are not exact"
            )

        status = raw_contract.get("status")
        evidence = raw_contract.get("evidence")
        if status not in {"blocked", "canary_active", "canary_passed", "qualified"}:
            errors.append(
                f"merge-queue readiness {repository}: status must be blocked, "
                "canary_active, canary_passed, or qualified"
            )
            continue
        if not isinstance(evidence, Mapping):
            errors.append(
                f"merge-queue readiness {repository}: evidence must be an object"
            )
            continue
        if set(evidence) != set(MERGE_QUEUE_EVIDENCE_FIELDS):
            errors.append(
                f"merge-queue readiness {repository}: evidence fields are not exact"
            )

        present = {name for name in MERGE_QUEUE_EVIDENCE_FIELDS if evidence.get(name) is not None}
        expected_present = {
            "blocked": set(),
            "canary_active": set(),
            "canary_passed": set(MERGE_QUEUE_EVIDENCE_FIELDS[:3]),
            "qualified": set(MERGE_QUEUE_EVIDENCE_FIELDS),
        }[status]
        if present != expected_present:
            errors.append(
                f"merge-queue readiness {repository}: {status} evidence must be exactly "
                f"{sorted(expected_present)}"
            )

        run_urls: list[str] = []
        for field in sorted(present):
            record = evidence.get(field)
            if not isinstance(record, Mapping):
                errors.append(
                    f"merge-queue readiness {repository}: {field} evidence must be an object"
                )
                continue
            expected_event, expected_conclusion = MERGE_QUEUE_EVIDENCE_EXPECTATIONS[field]
            if record.get("subject_repository") != repository:
                errors.append(
                    f"merge-queue readiness {repository}: {field} subject repository is not exact"
                )
            if record.get("evidence_role") != field:
                errors.append(
                    f"merge-queue readiness {repository}: {field} evidence role is not exact"
                )
            if record.get("event_name") != expected_event:
                errors.append(
                    f"merge-queue readiness {repository}: {field} event must be {expected_event}"
                )
            if record.get("conclusion") != expected_conclusion:
                errors.append(
                    f"merge-queue readiness {repository}: {field} conclusion must be "
                    f"{expected_conclusion}"
                )
            run_url = record.get("run_url")
            match = MERGE_QUEUE_RUN_URL.fullmatch(run_url) if isinstance(run_url, str) else None
            expected_run_repository = (
                "github-config" if field == "permanent_ruleset_audit" else repository
            )
            if match is None or match.group("repository") != expected_run_repository:
                errors.append(
                    f"merge-queue readiness {repository}: {field} run repository must be "
                    f"{expected_run_repository}"
                )
            else:
                run_urls.append(run_url)
                observed_run_urls.append(run_url)
        if len(run_urls) != len(set(run_urls)):
            errors.append(
                f"merge-queue readiness {repository}: evidence run URLs must be unique"
            )

        if status == "qualified":
            if seen_unqualified:
                errors.append(
                    f"merge-queue readiness {repository}: a later repository cannot be "
                    "qualified before every predecessor"
                )
        elif status in {"canary_active", "canary_passed"}:
            if seen_unqualified or seen_canary:
                errors.append(
                    f"merge-queue readiness {repository}: only the first unqualified "
                    "repository may have an active canary"
                )
            seen_canary = True
            seen_unqualified = True
        else:
            seen_unqualified = True
    if len(observed_run_urls) != len(set(observed_run_urls)):
        errors.append("merge-queue readiness evidence run URLs must be globally unique")
    return errors
