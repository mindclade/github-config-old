#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Pure validators and renderers for the GitHub platform adoption contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml

REPOSITORIES = {".github", ".github-private", "github-config"}
EXPECTED_WORKFLOWS = {
    "reusable-nix-qualification": {
        "implementation": ".github/workflows/reusable-nix-qualification.yml",
        "permissions": {"contents": "read"},
    },
    "reusable-dr-evidence": {
        "implementation": ".github/workflows/reusable-dr-evidence.yml",
        "permissions": {
            "actions": "read",
            "contents": "read",
            "id-token": "write",
        },
    },
}
USES_RE = re.compile(
    r"(?m)^\s+uses:\s+mindclade/\.github/(\.github/workflows/[a-z0-9-]+\.yml)@([^\s#]+)"
)
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
SEMVER_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git_blob(root: Path, reference: str, path: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{reference}:{path}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def workflow_adoption_errors(
    graph: Mapping[str, Any],
    activation: Mapping[str, Any],
    *,
    workspace_root: Path | None = None,
    repository_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    producer = graph.get("producer", {})
    release = producer.get("release", {})
    release_status = release.get("status")
    release_version = release.get("version")
    release_source = release.get("source_commit")
    gates = activation.get("gates", {})
    publication_gate = release.get("publication_gate")
    if publication_gate not in gates:
        errors.append(f"producer release references unknown gate: {publication_gate}")
    if release_status == "candidate":
        if release_source is not None:
            errors.append("candidate producer release must not claim a source commit")
        if gates.get(publication_gate) != "blocked":
            errors.append("candidate producer release requires a blocked publication gate")
    elif release_status == "published":
        if not isinstance(release_source, str) or not SHA_RE.fullmatch(release_source):
            errors.append("published producer release requires its exact source commit")
        if gates.get(publication_gate) != "qualified":
            errors.append("published producer release requires a qualified publication gate")

    workflows = graph.get("workflows", {})
    if set(workflows) != set(EXPECTED_WORKFLOWS):
        errors.append("workflow adoption graph inventory is not exact")
    seen_consumers: set[tuple[str, str]] = set()
    for name, expected in EXPECTED_WORKFLOWS.items():
        contract = workflows.get(name, {})
        implementation = contract.get("implementation")
        required_permissions = contract.get("required_permissions")
        if implementation != expected["implementation"]:
            errors.append(f"{name}: producer implementation path is not exact")
        if required_permissions != expected["permissions"]:
            errors.append(f"{name}: required permissions are not least-privilege exact")
        for consumer in contract.get("consumers", []):
            repository = consumer.get("repository")
            caller = consumer.get("caller")
            key = (str(repository), str(caller))
            if key in seen_consumers:
                errors.append(f"duplicate workflow consumer: {repository}/{caller}")
            seen_consumers.add(key)
            if repository not in REPOSITORIES - {".github"}:
                errors.append(f"{name}: consumer repository is outside the platform scope")
            if consumer.get("permissions") != required_permissions:
                errors.append(f"{repository}/{caller}: consumer permissions drift")
            activation_gates = consumer.get("activation_gates", [])
            for gate in activation_gates:
                if gate not in gates:
                    errors.append(f"{repository}/{caller}: unknown activation gate {gate}")
            state = consumer.get("state")
            current = consumer.get("current_reference")
            desired = consumer.get("desired_reference")
            if desired != release_version:
                errors.append(f"{repository}/{caller}: desired reference differs from release")
            if state == "blocked":
                if current is not None:
                    errors.append(f"{repository}/{caller}: blocked caller has a reference")
            elif state == "candidate":
                if not isinstance(current, str) or not SHA_RE.fullmatch(current):
                    errors.append(f"{repository}/{caller}: candidate caller requires a commit SHA")
            elif state == "released":
                if current != desired or not SEMVER_RE.fullmatch(str(current)):
                    errors.append(f"{repository}/{caller}: released caller must use desired semver")
                blocked = [gate for gate in activation_gates if gates.get(gate) != "qualified"]
                if blocked:
                    errors.append(
                        f"{repository}/{caller}: released caller has blocked gates {blocked}"
                    )

            root: Path | None = None
            if workspace_root is not None:
                root = workspace_root / str(repository)
            elif repository == "github-config" and repository_root is not None:
                root = repository_root
            if root is None:
                continue
            caller_path = root / str(caller)
            if not caller_path.is_file():
                errors.append(f"{repository}/{caller}: caller file is missing")
                continue
            text = caller_path.read_text(encoding="utf-8")
            uses = USES_RE.findall(text)
            if state == "blocked":
                if uses or "activation-blocked:" not in text:
                    errors.append(f"{repository}/{caller}: blocked caller is not fail-closed")
                continue
            expected_use = [(str(implementation), str(current))]
            if uses != expected_use:
                errors.append(f"{repository}/{caller}: caller reference differs from graph")
            try:
                caller_yaml = load_yaml(caller_path) or {}
            except (OSError, yaml.YAMLError) as exc:
                errors.append(f"{repository}/{caller}: cannot parse caller: {exc}")
            else:
                if caller_yaml.get("permissions") != required_permissions:
                    errors.append(f"{repository}/{caller}: caller permissions differ from graph")

            if workspace_root is not None and isinstance(current, str) and SHA_RE.fullmatch(current):
                producer_root = workspace_root / ".github"
                if _git_blob(producer_root, current, str(implementation)) is None:
                    errors.append(
                        f"{repository}/{caller}: producer commit does not contain {implementation}"
                    )

    expected_consumers = {
        (".github-private", ".github/workflows/nix-qualification.yml"),
        ("github-config", ".github/workflows/nix-qualification.yml"),
        ("github-config", ".github/workflows/dr-evidence.yml"),
    }
    if seen_consumers != expected_consumers:
        errors.append("workflow adoption consumer inventory is not exact")
    return errors


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def connected_evidence_errors(
    evidence: Mapping[str, Any],
    activation: Mapping[str, Any],
    *,
    today: date | None = None,
) -> list[str]:
    errors: list[str] = []
    today = today or date.today()
    records = evidence.get("records", [])
    gates = activation.get("gates", {})
    fresh_gates: set[str] = set()
    seen: set[str] = set()
    max_age_days = int(evidence.get("max_age_days", 0))
    try:
        as_of = date.fromisoformat(str(evidence.get("as_of")))
    except ValueError:
        errors.append("connected evidence as_of is not a valid date")
        as_of = today
    if as_of > today:
        errors.append("connected evidence as_of cannot be in the future")
    for record in records:
        record_id = record.get("id")
        if record_id in seen:
            errors.append(f"duplicate connected evidence id: {record_id}")
        seen.add(record_id)
        gate = record.get("gate")
        if gate not in gates:
            errors.append(f"{record_id}: evidence references unknown gate {gate}")
        try:
            observed = _timestamp(record["observed_at"])
            expires = _timestamp(record["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{record_id}: invalid evidence timestamps: {exc}")
            continue
        if expires <= observed:
            errors.append(f"{record_id}: evidence expiry must follow observation")
        if (expires - observed).total_seconds() > max_age_days * 86400:
            errors.append(f"{record_id}: evidence lifetime exceeds max_age_days")
        if observed.date() > as_of:
            errors.append(f"{record_id}: evidence observation is later than as_of")
        if expires.date() >= today and record.get("outcome") == "success":
            fresh_gates.add(str(gate))
    for gate, status in gates.items():
        if status == "qualified" and gate not in fresh_gates:
            errors.append(f"qualified gate lacks fresh connected evidence: {gate}")
    return errors


def render_adoption_dashboard(
    graph: Mapping[str, Any],
    activation: Mapping[str, Any],
    *,
    policy_version: str,
    policy_manifest_sha256: str,
    rulesets: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> str:
    release = graph["producer"]["release"]
    lines = [
        "<!-- generated by scripts/render-workflow-adoption.py; do not edit -->",
        "",
        "# Shared workflow adoption",
        "",
        f"Producer release: `{release['version']}` ({release['status']}).",
        f"Policy bundle: `{policy_version}`; manifest SHA-256 `{policy_manifest_sha256}`.",
        "",
        "## Repository readiness",
        "",
        "| Repository | Platform role | Shared-workflow references | Required-check readiness |",
        "| --- | --- | --- | --- |",
    ]
    for repository in sorted(REPOSITORIES):
        if repository == ".github":
            role = "producer"
            references = f"{release['version']} ({release['status']})"
        else:
            role = "consumer"
            values = []
            for name, contract in sorted(graph["workflows"].items()):
                for consumer in contract["consumers"]:
                    if consumer["repository"] == repository:
                        values.append(
                            f"{name}={consumer['current_reference'] or 'blocked'}"
                        )
            references = "; ".join(values)
        readiness = []
        for ruleset, contract in sorted(rulesets.items()):
            if repository in contract.get("repositories", []):
                readiness.append(f"{ruleset}={contract.get('enforcement', 'unknown')}")
        lines.append(
            f"| `{repository}` | {role} | `{references}` | "
            f"`{'; '.join(readiness) or 'no repository-scoped required ruleset'}` |"
        )
    lines.extend(
        [
            "",
            "## Consumer contracts",
            "",
        "| Workflow | Consumer | Current | Desired | State | Gates | Permissions |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for name, contract in sorted(graph["workflows"].items()):
        for consumer in sorted(
            contract["consumers"], key=lambda value: (value["repository"], value["caller"])
        ):
            gates = ", ".join(
                f"{gate}={activation['gates'].get(gate, 'unknown')}"
                for gate in consumer["activation_gates"]
            )
            permissions = ", ".join(
                f"{key}:{value}" for key, value in sorted(consumer["permissions"].items())
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{name}`",
                        f"`{consumer['repository']}/{consumer['caller']}`",
                        f"`{consumer['current_reference'] or 'blocked'}`",
                        f"`{consumer['desired_reference']}`",
                        f"`{consumer['state']}`",
                        gates,
                        f"`{permissions}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            f"## Connected gate freshness (as of {evidence['as_of']})",
            "",
            "| Gate | State | Evidence | Freshness |",
            "| --- | --- | --- | --- |",
        ]
    )
    for gate, status in sorted(activation["gates"].items()):
        records = [record for record in evidence["records"] if record["gate"] == gate]
        identifiers = ", ".join(record["id"] for record in records) or "none"
        freshness = (
            ", ".join(
                f"{record['id']} expires {record['expires_at']}" for record in records
            )
            or "no connected evidence"
        )
        lines.append(f"| `{gate}` | `{status}` | `{identifiers}` | {freshness} |")
    lines.extend(
        [
            "",
            "Source validation proves only the checked-in contracts. A gate is connected-qualified",
            "only when an unexpired record exists in `catalog/connected-qualification-evidence.yaml`.",
            "",
        ]
    )
    return "\n".join(lines)
