#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Compile a reviewed governance rollout phase into exact Terraform overrides."""

from __future__ import annotations

import argparse
import json
import sys


PHASES = ("normal", "adopt-evaluate", "promote-core")
ACTIVE_BRANCH_RULESETS = (
    "baseline-all",
    "merge-queue",
    "protected-paths",
    "release-authority-paths",
    "required-checks-gitops",
    "required-checks-tf",
    "required-checks-tf-static",
    "required-checks-tf-tests",
)
CORE_RULESETS = {"baseline-all", "protected-paths"}


def overrides_for_phase(phase: str) -> dict[str, str]:
    if phase not in PHASES:
        raise ValueError(f"unknown rollout phase {phase!r}")
    if phase == "normal":
        return {}
    if phase == "adopt-evaluate":
        return {name: "evaluate" for name in ACTIVE_BRANCH_RULESETS}
    return {
        name: "active" if name in CORE_RULESETS else "evaluate"
        for name in ACTIVE_BRANCH_RULESETS
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    args = parser.parse_args()
    try:
        overrides = overrides_for_phase(args.phase)
    except ValueError as exc:
        print(f"governance rollout rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(overrides, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
