#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Pure governance invariants shared by catalog validation and regression tests."""

from __future__ import annotations

from typing import Any, Mapping


EVIDENCE_GATED_RULESET_GATES = {
    "release-tag-creation": ("release_tag_creation_control_qualified",),
    "required-checks-bootstrap": ("bootstrap_verdict_observed",),
    "required-checks-github-config": ("github_config_verdict_observed",),
    "required-checks-go": (
        "monorepo_bazel_verdict_observed",
        "monorepo_merge_group_full_graph_observed",
        "monorepo_affected_latency_qualified",
        "rulesets_connected_audit",
    ),
    "required-checks-mixed": (
        "monorepo_bazel_verdict_observed",
        "monorepo_merge_group_full_graph_observed",
        "monorepo_affected_latency_qualified",
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
