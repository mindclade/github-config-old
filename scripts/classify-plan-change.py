#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Decide whether a github-config event requires the connected Terraform plan."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SHA = re.compile(r"^[0-9a-f]{40}$")
CONTROL_PATHS = {
    ".github/workflows/apply.yml",
    ".github/workflows/drift.yml",
    ".github/workflows/plan.yml",
    "scripts/classify-plan-change.py",
    "scripts/enforce-immutable-oidc.py",
    "scripts/governance-rollout.py",
    "scripts/validate-adoption-plan.py",
}
TRUST_PREFIXES = ("catalog/", "idp/")


def requires_connected_plan(paths: list[str]) -> bool:
    for raw in paths:
        path = Path(raw).as_posix()
        name = Path(path).name
        if (
            path in CONTROL_PATHS
            or path.startswith(TRUST_PREFIXES)
            or name == ".terraform.lock.hcl"
            or path.endswith(".tf")
            or path.endswith(".tf.json")
        ):
            return True
    return False


def changed_paths(base: str, head: str) -> list[str]:
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError("pull-request base and head must be full lowercase commit SHAs")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git diff could not establish changed paths"
        raise ValueError(detail)
    return [line for line in result.stdout.splitlines() if line]


def decide(
    event_name: str,
    event_action: str,
    base: str,
    head: str,
    draft: bool = False,
) -> bool:
    if event_name != "pull_request":
        return True
    if event_action in {"closed", "converted_to_draft"} or draft:
        return False
    return requires_connected_plan(changed_paths(base, head))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-action", default="")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    try:
        decision = decide(
            args.event_name,
            args.event_action,
            args.base,
            args.head,
            args.draft,
        )
    except ValueError as exc:
        print(f"connected-plan scope detection failed: {exc}", file=sys.stderr)
        return 1
    print("true" if decision else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
