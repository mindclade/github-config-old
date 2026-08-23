#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Qualify the three-repository GitHub platform source without overstating live evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from platform_contracts import (
    connected_evidence_errors,
    load_yaml,
    render_adoption_dashboard,
    workflow_adoption_errors,
)

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = (".github", ".github-private", "github-config")
NATIVE_COMMANDS = {
    ".github": (
        ("nix", "develop", ".#ci", "--command", "make", "validate"),
        ("nix", "flake", "check", "--no-update-lock-file"),
    ),
    ".github-private": (
        ("nix", "develop", ".#ci", "--command", "make", "validate", "lint"),
        ("nix", "flake", "check", "--no-update-lock-file"),
    ),
    "github-config": (
        ("nix", "develop", ".#ci", "--command", "make", "validate", "test"),
        ("nix", "flake", "check", "--no-update-lock-file"),
    ),
}


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def repository_record(root: Path) -> dict[str, Any]:
    head = git(root, "rev-parse", "HEAD")
    try:
        origin_main = git(root, "rev-parse", "origin/main")
    except subprocess.CalledProcessError:
        origin_main = None
    return {
        "path": str(root),
        "head": head,
        "branch": git(root, "branch", "--show-current") or "detached",
        "clean": not bool(git(root, "status", "--porcelain=v1")),
        "origin_main": origin_main,
        "head_contains_origin_main": (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", str(origin_main), head],
                cwd=root,
                check=False,
                capture_output=True,
            ).returncode
            == 0
            if origin_main
            else False
        ),
    }


def run_native(
    workspace: Path, output: Path, skip: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for repository in REPOSITORIES:
        for index, command in enumerate(NATIVE_COMMANDS[repository], start=1):
            record: dict[str, Any] = {
                "repository": repository,
                "command": list(command),
                "status": "not-run" if skip else "running",
            }
            if skip:
                records.append(record)
                continue
            try:
                result = subprocess.run(
                    command,
                    cwd=workspace / repository,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                combined = result.stdout + result.stderr
                log = logs / f"{repository.lstrip('.') or 'github'}-{index}.log"
                log.write_text(combined, encoding="utf-8")
                record.update(
                    {
                        "status": "passed" if result.returncode == 0 else "failed",
                        "returncode": result.returncode,
                        "log": str(log.relative_to(output)),
                    }
                )
                if result.returncode != 0:
                    errors.append(f"{repository}: command failed: {' '.join(command)}")
            except OSError as exc:
                record.update({"status": "failed", "error": str(exc)})
                errors.append(f"{repository}: cannot execute {' '.join(command)}: {exc}")
            records.append(record)
    return records, errors


def policy_distribution_errors(workspace: Path) -> list[str]:
    canonical = workspace / ".github" / "contracts" / "policy-bundle" / "manifest.json"
    if not canonical.is_file():
        return ["canonical policy manifest is missing"]
    errors: list[str] = []
    tool = workspace / ".github" / "tools" / "policy_bundle.py"
    canonical_result = subprocess.run(
        [sys.executable, str(tool), "--source-root", str(workspace / ".github"), "verify"],
        check=False,
        capture_output=True,
        text=True,
    )
    if canonical_result.returncode != 0:
        errors.append(".github: canonical policy bundle verification failed")
    manifest = json.loads(canonical.read_text(encoding="utf-8"))
    validator_digest = next(
        artifact["sha256"]
        for artifact in manifest["artifacts"]
        if artifact["name"] == "repository-home-validator"
    )
    action_pattern = re.compile(
        r"mindclade/\.github/actions/validate-repository-home@([^\s#]+)"
    )
    consumer_workflows = {
        ".github-private": ".github/workflows/validate.yml",
        "github-config": ".github/workflows/production-contract.yml",
    }
    for repository in (".github-private", "github-config"):
        target = workspace / repository / "contracts" / "policy-bundle" / "manifest.json"
        if not target.is_file() or target.read_bytes() != canonical.read_bytes():
            errors.append(f"{repository}: policy manifest differs from .github")
            continue
        result = subprocess.run(
            [
                sys.executable,
                str(tool),
                "--source-root",
                str(workspace / ".github"),
                "verify",
                "--repository",
                repository,
                "--target-root",
                str(workspace / repository),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"{repository}: declared policy distribution verification failed")
        workflow = workspace / repository / consumer_workflows[repository]
        matches = action_pattern.findall(workflow.read_text(encoding="utf-8"))
        if len(matches) != 1:
            errors.append(f"{repository}: repository-home action pin is not exact")
            continue
        reference = matches[0]
        try:
            blob = subprocess.run(
                [
                    "git",
                    "show",
                    f"{reference}:actions/validate-repository-home/validate.py",
                ],
                cwd=workspace / ".github",
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            errors.append(f"{repository}: repository-home action pin is unavailable")
            continue
        if hashlib.sha256(blob).hexdigest() != validator_digest:
            errors.append(
                f"{repository}: repository-home action pin differs from the policy manifest"
            )
    return errors


def documentation_errors(workspace: Path, graph: Any, activation: Any) -> list[str]:
    errors: list[str] = []
    config = workspace / "github-config"
    evidence = load_yaml(config / "catalog" / "connected-qualification-evidence.yaml")
    rulesets = load_yaml(config / "catalog" / "rulesets.yaml")
    manifest_path = config / "contracts" / "policy-bundle" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_dashboard = render_adoption_dashboard(
        graph,
        activation,
        policy_version=manifest["version"],
        policy_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        rulesets=rulesets,
        evidence=evidence,
    )
    dashboard = workspace / "github-config" / "docs" / "workflow-adoption.md"
    if not dashboard.is_file() or dashboard.read_text(encoding="utf-8") != expected_dashboard:
        errors.append("github-config workflow adoption dashboard is stale")
    for repository in REPOSITORIES:
        readme = workspace / repository / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        if "Brand source: mindclade/.github-private" in text:
            errors.append(f"{repository}: README retains obsolete brand-source authority")
        if "Brand distribution: mindclade/.github-private" not in text:
            errors.append(f"{repository}: README omits the brand distribution contract")
    return errors


def markdown_report(report: dict[str, Any]) -> str:
    source = report["source_qualification"]
    connected = report["connected_qualification"]
    lines = [
        "# GitHub platform qualification",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Source qualification: **{source['status']}**",
        f"Connected qualification: **{connected['status']}**",
        "",
        "Source qualification and connected evidence are intentionally separate. A successful",
        "local gate does not prove GitHub settings, runners, WIF, protected approvals, or releases.",
        "",
        "## Repositories",
        "",
        "| Repository | Commit | Branch | Clean | Contains origin/main |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, record in report["repositories"].items():
        lines.append(
            f"| `{name}` | `{record['head']}` | `{record['branch']}` | "
            f"`{str(record['clean']).lower()}` | "
            f"`{str(record['head_contains_origin_main']).lower()}` |"
        )
    lines.extend(["", "## Source findings", ""])
    if source["errors"]:
        lines.extend(f"- {message}" for message in source["errors"])
    else:
        lines.append("- No source-contract errors.")
    lines.extend(["", "## Connected blockers", ""])
    if connected["blockers"]:
        lines.extend(f"- {message}" for message in connected["blockers"])
    else:
        lines.append("- No connected-evidence blockers.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, default=ROOT.parent)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".qualification")
    parser.add_argument("--skip-native", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REPOSITORIES if not (workspace / name / ".git").exists()]
    if missing:
        print(f"missing workspace repositories: {missing}", file=sys.stderr)
        return 2

    catalog = workspace / "github-config" / "catalog"
    graph = load_yaml(catalog / "workflow-adoption.yaml")
    activation = load_yaml(catalog / "governance-activation.yaml")
    evidence = load_yaml(catalog / "connected-qualification-evidence.yaml")
    source_errors = workflow_adoption_errors(
        graph, activation, workspace_root=workspace
    )
    source_errors.extend(policy_distribution_errors(workspace))
    source_errors.extend(documentation_errors(workspace, graph, activation))
    native, native_errors = run_native(workspace, output, args.skip_native)
    source_errors.extend(native_errors)
    if args.skip_native:
        source_errors.append("native gates were not run (--skip-native)")

    evidence_errors = connected_evidence_errors(evidence, activation)
    blocked_gates = sorted(
        gate for gate, status in activation["gates"].items() if status != "qualified"
    )
    connected_blockers = evidence_errors + [f"gate remains blocked: {gate}" for gate in blocked_gates]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace),
        "repositories": {
            name: repository_record(workspace / name) for name in REPOSITORIES
        },
        "native_gates": native,
        "source_qualification": {
            "status": "qualified" if not source_errors else "failed",
            "errors": sorted(set(source_errors)),
        },
        "connected_qualification": {
            "status": "qualified" if not connected_blockers else "blocked",
            "blockers": sorted(set(connected_blockers)),
            "evidence_records": len(evidence.get("records", [])),
        },
    }
    (output / "github-platform-qualification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "github-platform-qualification.md").write_text(
        markdown_report(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "source": report["source_qualification"]["status"],
                "connected": report["connected_qualification"]["status"],
                "report": str(output / "github-platform-qualification.json"),
            },
            sort_keys=True,
        )
    )
    return 0 if not source_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
