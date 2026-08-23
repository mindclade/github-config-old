#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Prepare coordinated immutable shared-workflow pin upgrades after v5 qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml

from platform_contracts import connected_evidence_errors, load_yaml, workflow_adoption_errors

ROOT = Path(__file__).resolve().parents[1]
HEADER = """# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

---
"""


class UpgradeError(ValueError):
    """The requested pin upgrade is not qualified or exact."""


def qualified_upgrade_errors(
    graph: dict[str, Any], evidence: dict[str, Any], activation: dict[str, Any]
) -> list[str]:
    errors = connected_evidence_errors(evidence, activation)
    release = graph.get("producer", {}).get("release", {})
    if release.get("status") != "published":
        errors.append("v5 producer release is not published")
    if not re.fullmatch(r"[a-f0-9]{40}", str(release.get("source_commit", ""))):
        errors.append("v5 producer release has no exact source commit")
    if activation.get("gates", {}).get(release.get("publication_gate")) != "qualified":
        errors.append("v5 publication gate is not qualified")
    for contract in graph.get("workflows", {}).values():
        for consumer in contract.get("consumers", []):
            if consumer.get("state") != "candidate":
                continue
            for gate in consumer.get("activation_gates", []):
                if activation.get("gates", {}).get(gate) != "qualified":
                    errors.append(
                        f"{consumer.get('repository')}/{consumer.get('caller')}: "
                        f"activation gate is blocked: {gate}"
                    )
    return errors


def prepare(workspace: Path, write: bool) -> dict[str, Any]:
    config = workspace / "github-config"
    catalog = config / "catalog"
    graph_path = catalog / "workflow-adoption.yaml"
    graph = load_yaml(graph_path)
    activation = load_yaml(catalog / "governance-activation.yaml")
    evidence = load_yaml(catalog / "connected-qualification-evidence.yaml")
    errors = qualified_upgrade_errors(graph, evidence, activation)
    if errors:
        raise UpgradeError("; ".join(sorted(set(errors))))
    plans: list[dict[str, Any]] = []
    updated_graph = json.loads(json.dumps(graph))
    for name, contract in updated_graph["workflows"].items():
        for consumer in contract["consumers"]:
            if consumer["state"] != "candidate":
                continue
            repository = consumer["repository"]
            path = workspace / repository / consumer["caller"]
            if not path.is_file():
                raise UpgradeError(f"missing consumer caller: {repository}/{consumer['caller']}")
            old = (
                f"mindclade/.github/{contract['implementation']}@"
                f"{consumer['current_reference']}"
            )
            new = (
                f"mindclade/.github/{contract['implementation']}@"
                f"{consumer['desired_reference']}"
            )
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise UpgradeError(f"caller does not contain exactly one expected pin: {path}")
            plans.append(
                {
                    "workflow": name,
                    "repository": repository,
                    "caller": consumer["caller"],
                    "from": consumer["current_reference"],
                    "to": consumer["desired_reference"],
                }
            )
            if write:
                path.write_text(text.replace(old, new), encoding="utf-8")
                consumer["current_reference"] = consumer["desired_reference"]
                consumer["state"] = "released"
    if write and plans:
        graph_path.write_text(
            HEADER + yaml.safe_dump(updated_graph, sort_keys=False), encoding="utf-8"
        )
        remaining = workflow_adoption_errors(
            updated_graph, activation, repository_root=config
        )
        if remaining:
            raise UpgradeError("prepared upgrade violates adoption graph: " + "; ".join(remaining))
    return {"release": graph["producer"]["release"], "changes": plans, "written": write}


def check_eligibility(root: Path) -> dict[str, Any]:
    graph = load_yaml(root / "catalog" / "workflow-adoption.yaml")
    activation = load_yaml(root / "catalog" / "governance-activation.yaml")
    evidence = load_yaml(root / "catalog" / "connected-qualification-evidence.yaml")
    errors = qualified_upgrade_errors(graph, evidence, activation)
    if errors:
        raise UpgradeError("; ".join(sorted(set(errors))))
    return {"release": graph["producer"]["release"], "eligible": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=ROOT.parent)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--eligibility-only", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            check_eligibility(ROOT)
            if args.eligibility_only
            else prepare(args.workspace_root.resolve(), args.write)
        )
    except (OSError, yaml.YAMLError, UpgradeError) as exc:
        print(f"workflow pin upgrade blocked: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
