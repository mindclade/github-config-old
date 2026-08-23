#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compile a reviewed governance rollout into exact, fail-closed Terraform inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from governance_contracts import (
    MERGE_QUEUE_EVIDENCE_FIELDS,
    MERGE_QUEUE_ROLLOUT,
    merge_queue_readiness_errors,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS = ROOT / "catalog/merge-queue-readiness.yaml"
READINESS_SCHEMA = ROOT / "catalog/schema/merge-queue-readiness.schema.json"
PHASES = ("normal", "adopt-evaluate", "promote-core", "merge-queue")
MERGE_QUEUE_STAGES = ("canary", "promote", "finalize", "rollback")
ACTIVE_BRANCH_RULESETS = (
    "baseline-all",
    "merge-queue",
    "protected-paths",
    "release-authority-paths",
    "required-checks-tf-static",
    "required-checks-tf-tests",
)
CORE_RULESETS = {"baseline-all", "protected-paths"}
ROLLOUT_REPOSITORIES = tuple(item[0] for item in MERGE_QUEUE_ROLLOUT)
REPOSITORY_CONTEXTS = {
    repository: contexts for repository, contexts, _ in MERGE_QUEUE_ROLLOUT
}
REPOSITORY_RULESETS = {
    repository: rulesets for repository, _, rulesets in MERGE_QUEUE_ROLLOUT
}


def load_readiness(path: Path = DEFAULT_READINESS) -> dict[str, Any]:
    """Load the versioned rollout contract without accepting an empty document."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("merge-queue readiness must be an object")
    return data


def _validated_rollout(
    readiness: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    try:
        schema = json.loads(READINESS_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load merge-queue readiness schema: {exc}") from exc
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(readiness),
        key=lambda issue: tuple(str(item) for item in issue.absolute_path),
    )
    if schema_errors:
        issue = schema_errors[0]
        location = "/".join(str(item) for item in issue.absolute_path) or "<root>"
        raise ValueError(
            f"invalid merge-queue readiness schema at {location}: {issue.message}"
        )
    errors = merge_queue_readiness_errors(readiness)
    if errors:
        raise ValueError("invalid merge-queue readiness: " + "; ".join(errors))
    return {
        str(item["repository"]): item
        for item in readiness["rollout_order"]
    }


def _base_merge_queue_inputs(
    contracts: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    queue_overrides: dict[str, str] = {}
    ruleset_overrides: dict[str, str] = {}
    canary_checks: dict[str, list[str]] = {}
    for repository in ROLLOUT_REPOSITORIES:
        status = contracts[repository]["status"]
        queue_overrides[repository] = (
            "active"
            if status in {"canary_active", "canary_passed", "qualified"}
            else "evaluate"
        )
        for ruleset in REPOSITORY_RULESETS[repository]:
            ruleset_overrides[ruleset] = (
                "active" if status == "qualified" else "evaluate"
            )
        if status in {"canary_active", "canary_passed"}:
            canary_checks[repository] = list(REPOSITORY_CONTEXTS[repository])
    return queue_overrides, ruleset_overrides, canary_checks


def _validate_merge_queue_stage(
    repository: str,
    stage: str,
    contracts: Mapping[str, Mapping[str, Any]],
) -> None:
    if repository not in ROLLOUT_REPOSITORIES:
        raise ValueError(f"unknown merge-queue repository {repository!r}")
    if stage not in MERGE_QUEUE_STAGES:
        raise ValueError(f"unknown merge-queue stage {stage!r}")
    expected_statuses = {
        "canary": {"canary_active"},
        "promote": {"canary_passed"},
        "finalize": {"qualified"},
        "rollback": {"canary_active", "canary_passed", "qualified"},
    }[stage]
    actual_status = contracts[repository]["status"]
    if actual_status not in expected_statuses:
        expected = ", ".join(sorted(expected_statuses))
        raise ValueError(
            f"merge-queue {repository} {stage} requires status {expected}, "
            f"found {actual_status}"
        )
    selected_index = ROLLOUT_REPOSITORIES.index(repository)
    for predecessor in ROLLOUT_REPOSITORIES[:selected_index]:
        if contracts[predecessor]["status"] != "qualified":
            raise ValueError(
                f"merge-queue {repository} cannot advance before {predecessor} is qualified"
            )
    for successor in ROLLOUT_REPOSITORIES[selected_index + 1 :]:
        if contracts[successor]["status"] != "blocked":
            raise ValueError(
                f"merge-queue {repository} cannot advance while {successor} is not blocked"
            )


def bundle_for_rollout(
    phase: str,
    *,
    repository: str | None = None,
    stage: str | None = None,
    readiness: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the complete Terraform input bundle for one reviewed rollout action."""

    if phase not in PHASES:
        raise ValueError(f"unknown rollout phase {phase!r}")
    contracts = _validated_rollout(
        readiness if readiness is not None else load_readiness()
    )
    queue_overrides, ruleset_overrides, canary_checks = _base_merge_queue_inputs(
        contracts
    )

    if phase != "merge-queue":
        if repository is not None or stage is not None:
            raise ValueError(
                "merge-queue repository and stage are valid only for phase merge-queue"
            )
        if phase in {"adopt-evaluate", "promote-core"} and any(
            contract["status"] != "blocked" for contract in contracts.values()
        ):
            raise ValueError(
                f"phase {phase} cannot run after a merge-queue rollout has advanced"
            )
        if phase == "adopt-evaluate":
            ruleset_overrides.update(
                {name: "evaluate" for name in ACTIVE_BRANCH_RULESETS}
            )
            queue_overrides = {
                repository_name: "evaluate"
                for repository_name in ROLLOUT_REPOSITORIES
            }
            canary_checks = {}
        elif phase == "promote-core":
            ruleset_overrides.update(
                {
                    name: "active" if name in CORE_RULESETS else "evaluate"
                    for name in ACTIVE_BRANCH_RULESETS
                }
            )
            queue_overrides = {
                repository_name: "evaluate"
                for repository_name in ROLLOUT_REPOSITORIES
            }
            canary_checks = {}
    else:
        if repository is None or stage is None:
            raise ValueError("phase merge-queue requires an exact repository and stage")
        _validate_merge_queue_stage(repository, stage, contracts)
        selected_rulesets = REPOSITORY_RULESETS[repository]
        if stage == "rollback":
            queue_overrides[repository] = "evaluate"
            ruleset_overrides.update({name: "evaluate" for name in selected_rulesets})
            canary_checks.pop(repository, None)
            return {
                "ruleset_enforcement_overrides": ruleset_overrides,
                "merge_queue_repository_enforcement_overrides": queue_overrides,
                "merge_queue_canary_required_checks": canary_checks,
            }
        queue_overrides[repository] = "active"
        selected_enforcement = "evaluate" if stage == "canary" else "active"
        ruleset_overrides.update(
            {name: selected_enforcement for name in selected_rulesets}
        )
        if stage in {"canary", "promote"}:
            canary_checks[repository] = list(REPOSITORY_CONTEXTS[repository])

    return {
        "ruleset_enforcement_overrides": ruleset_overrides,
        "merge_queue_repository_enforcement_overrides": queue_overrides,
        "merge_queue_canary_required_checks": canary_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--repository", choices=ROLLOUT_REPOSITORIES)
    parser.add_argument("--stage", choices=MERGE_QUEUE_STAGES)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    args = parser.parse_args()
    try:
        bundle = bundle_for_rollout(
            args.phase,
            repository=args.repository,
            stage=args.stage,
            readiness=load_readiness(args.readiness),
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"governance rollout rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(bundle, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
