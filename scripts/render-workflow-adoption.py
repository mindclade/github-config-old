#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Render or verify the machine-owned shared-workflow adoption dashboard."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from platform_contracts import load_yaml, render_adoption_dashboard

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "workflow-adoption.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    graph = load_yaml(ROOT / "catalog" / "workflow-adoption.yaml")
    activation = load_yaml(ROOT / "catalog" / "governance-activation.yaml")
    evidence = load_yaml(ROOT / "catalog" / "connected-qualification-evidence.yaml")
    rulesets = load_yaml(ROOT / "catalog" / "rulesets.yaml")
    manifest_path = ROOT / "contracts" / "policy-bundle" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = render_adoption_dashboard(
        graph,
        activation,
        policy_version=manifest["version"],
        policy_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        rulesets=rulesets,
        evidence=evidence,
    )
    if args.write:
        TARGET.write_text(expected, encoding="utf-8")
        print(f"rendered {TARGET.relative_to(ROOT)}")
        return 0
    if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected:
        print(
            "workflow adoption dashboard is stale; rerun with --write",
            file=sys.stderr,
        )
        return 1
    print("workflow adoption dashboard is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
