#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Prepare the exact DR evidence caller only after every activation gate is evidenced."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml

from platform_contracts import connected_evidence_errors, load_yaml

ROOT = Path(__file__).resolve().parents[1]
CALLER = ROOT / ".github" / "workflows" / "dr-evidence.yml"
GRAPH = ROOT / "catalog" / "workflow-adoption.yaml"


class ActivationError(ValueError):
    """The DR caller cannot be activated safely."""


def active_caller(reference: str) -> str:
    return f"""---
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

name: Publish DR evidence

on:
  workflow_dispatch:
    inputs:
      report_path:
        description: Repository-relative path to the completed report v2.
        required: true
        type: string
      environment:
        description: Protected drill environment.
        required: true
        type: choice
        options:
          - scratch
          - staging
      observer_operator:
        description: GitHub login of the independent drill observer.
        required: true
        type: string

permissions:
  actions: read
  contents: read
  id-token: write

jobs:
  publish:
    uses: mindclade/.github/.github/workflows/reusable-dr-evidence.yml@{reference}
    with:
      report-path: ${{{{ inputs.report_path }}}}
      environment: ${{{{ inputs.environment }}}}
      primary-operator: ${{{{ github.actor }}}}
      observer-operator: ${{{{ inputs.observer_operator }}}}
"""


def find_consumer(graph: dict[str, Any]) -> dict[str, Any]:
    consumers = graph["workflows"]["reusable-dr-evidence"]["consumers"]
    matches = [value for value in consumers if value["repository"] == "github-config"]
    if len(matches) != 1:
        raise ActivationError("DR adoption contract must have exactly one github-config consumer")
    return matches[0]


def activation_errors(
    graph: dict[str, Any], evidence: dict[str, Any], activation: dict[str, Any]
) -> list[str]:
    errors = connected_evidence_errors(evidence, activation)
    release = graph["producer"]["release"]
    consumer = find_consumer(graph)
    if release["status"] != "published":
        errors.append("v5 release is not published")
    if release["source_commit"] is None:
        errors.append("v5 release source commit is not recorded")
    for gate in consumer["activation_gates"]:
        if activation["gates"].get(gate) != "qualified":
            errors.append(f"DR activation gate is blocked: {gate}")
    return errors


def prepare(root: Path, write: bool) -> bool:
    catalog = root / "catalog"
    graph_path = catalog / "workflow-adoption.yaml"
    caller_path = root / ".github" / "workflows" / "dr-evidence.yml"
    graph = load_yaml(graph_path)
    evidence = load_yaml(catalog / "connected-qualification-evidence.yaml")
    activation = load_yaml(catalog / "governance-activation.yaml")
    consumer = find_consumer(graph)
    errors = activation_errors(graph, evidence, activation)
    if errors:
        if write:
            raise ActivationError("; ".join(sorted(set(errors))))
        text = caller_path.read_text(encoding="utf-8")
        if consumer["state"] != "blocked" or "activation-blocked:" not in text:
            raise ActivationError("unqualified DR caller is not fail-closed")
        return False
    expected = active_caller(consumer["desired_reference"])
    if write:
        caller_path.write_text(expected, encoding="utf-8")
        raw = graph_path.read_text(encoding="utf-8")
        workflow_marker = "  reusable-dr-evidence:\n"
        before, marker, section = raw.partition(workflow_marker)
        if not marker or section.count("        current_reference: null") != 1:
            raise ActivationError("cannot update the exact DR graph reference")
        section = section.replace(
            "        current_reference: null",
            f"        current_reference: {consumer['desired_reference']}",
            1,
        ).replace("        state: blocked", "        state: released", 1)
        graph_path.write_text(before + marker + section, encoding="utf-8")
    elif caller_path.read_text(encoding="utf-8") != expected:
        raise ActivationError("qualified DR caller has not been prepared")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        active = prepare(args.root.resolve(), args.write)
    except (OSError, yaml.YAMLError, ActivationError) as exc:
        print(f"DR workflow activation blocked: {exc}", file=sys.stderr)
        return 1
    print("DR workflow activation is qualified" if active else "DR workflow remains safely blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
