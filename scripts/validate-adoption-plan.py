#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Fail closed when a Terraform plan would recreate known GitHub resources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "catalog/adoption-inventory.yaml"
DEFAULT_MEMBERSHIP = ROOT / "idp/team-members.json"


class AdoptionError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise AdoptionError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise AdoptionError(f"{path} must contain a mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdoptionError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise AdoptionError(f"{path} must contain a JSON object")
    return value


def inventory_errors(inventory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = inventory.get("known_existing", [])
    addresses = [str(item.get("terraform_address", "")) for item in entries]
    identities = [
        (str(item.get("kind", "")), str(item.get("import_id", "")))
        for item in entries
    ]
    if not entries:
        errors.append("known_existing is empty")
    if len(addresses) != len(set(addresses)):
        errors.append("known_existing contains a duplicate Terraform address")
    if len(identities) != len(set(identities)):
        errors.append("known_existing contains a duplicate kind/import_id identity")
    if inventory.get("qualification") == "qualified" and inventory.get(
        "unresolved_discovery"
    ):
        errors.append("qualification cannot be qualified while discovery is unresolved")
    return errors


def planned_changes(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("address")): item.get("change", {})
        for item in plan.get("resource_changes", [])
        if isinstance(item, dict) and item.get("address")
    }


def prior_state_ids(plan: dict[str, Any]) -> dict[str, str]:
    identities: dict[str, str] = {}

    def visit(module: dict[str, Any]) -> None:
        for resource in module.get("resources", []):
            if not isinstance(resource, dict) or not resource.get("address"):
                continue
            values = resource.get("values", {})
            if isinstance(values, dict) and values.get("id") is not None:
                identities[str(resource["address"])] = str(values["id"])
        for child in module.get("child_modules", []):
            if isinstance(child, dict):
                visit(child)

    root = plan.get("prior_state", {}).get("values", {}).get("root_module", {})
    if isinstance(root, dict):
        visit(root)
    return identities


def plan_errors(
    inventory: dict[str, Any],
    plan: dict[str, Any],
    state_addresses: set[str],
    *,
    allow_destructive: bool = False,
) -> list[str]:
    errors: list[str] = []
    changes = planned_changes(plan)
    state_ids = prior_state_ids(plan)
    for entry in inventory.get("known_existing", []):
        address = str(entry["terraform_address"])
        expected_id = str(entry["import_id"])
        if address in state_addresses:
            expected_state_id = str(entry.get("state_id", expected_id))
            actual_state_id = state_ids.get(address)
            if actual_state_id != expected_state_id:
                errors.append(
                    f"{address}: state identity is {actual_state_id!r}, expected "
                    f"{expected_state_id!r}"
                )
            continue
        change = changes.get(address)
        importing = change.get("importing", {}) if isinstance(change, dict) else {}
        imported_id = str(importing.get("id", "")) if isinstance(importing, dict) else ""
        if imported_id == expected_id:
            continue
        actions = change.get("actions", []) if isinstance(change, dict) else []
        if "create" in actions:
            errors.append(
                f"{address}: known-existing {entry['kind']} would be created instead of "
                f"imported as {expected_id}"
            )
        elif imported_id:
            errors.append(
                f"{address}: plan imports {imported_id}, expected immutable ID {expected_id}"
            )
        else:
            errors.append(
                f"{address}: known-existing resource is neither in state nor imported by the plan"
            )

    if not allow_destructive:
        for address, change in changes.items():
            actions = list(change.get("actions", []))
            if "delete" in actions:
                errors.append(
                    f"{address}: destructive action {actions} requires an explicit reviewed override"
                )
    return errors


def membership_errors(path: Path, catalog_teams: set[str], minimum: int) -> list[str]:
    if not path.is_file():
        return [f"{path.relative_to(ROOT)} is absent"]
    document = load_json(path)
    members = document.get("org_members", [])
    teams = document.get("team_members", {})
    errors: list[str] = []
    if not isinstance(members, list) or len(members) < minimum:
        errors.append(f"membership export must contain at least {minimum} organization member(s)")
    if not isinstance(teams, dict):
        errors.append("membership export team_members must be an object")
    elif set(teams) != catalog_teams:
        errors.append(
            "membership export must cover every catalog team exactly; difference: "
            + ", ".join(sorted(set(teams) ^ catalog_teams))
        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--plan-json", type=Path)
    parser.add_argument("--state-list", type=Path)
    parser.add_argument("--activation", action="store_true")
    parser.add_argument("--allow-destructive", action="store_true")
    parser.add_argument("--membership-export", type=Path, default=DEFAULT_MEMBERSHIP)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        inventory = load_yaml(args.inventory)
        errors = inventory_errors(inventory)
        if bool(args.plan_json) != bool(args.state_list):
            errors.append("--plan-json and --state-list must be provided together")
        if args.plan_json and args.state_list:
            plan = load_json(args.plan_json)
            try:
                state = {
                    line.strip()
                    for line in args.state_list.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
            except OSError as error:
                raise AdoptionError(f"cannot load {args.state_list}: {error}") from error
            errors.extend(
                plan_errors(
                    inventory,
                    plan,
                    state,
                    allow_destructive=args.allow_destructive,
                )
            )
        if args.activation:
            unresolved = inventory.get("unresolved_discovery", [])
            if inventory.get("qualification") != "qualified" or unresolved:
                errors.append(
                    "adoption inventory is not qualified: "
                    + ", ".join(
                        str(item.get("resource_class", "unknown")) for item in unresolved
                    )
                )
            mappings = load_yaml(ROOT / "idp/mappings.yaml")
            deferred = [
                name
                for name, config in mappings.get("groups", {}).items()
                if config.get("status") == "deferred"
            ]
            if deferred:
                errors.append("IdP team mappings remain deferred: " + ", ".join(sorted(deferred)))
            teams = set(load_yaml(ROOT / "catalog/teams.yaml"))
            minimum = int(mappings.get("membership_export", {}).get("minimum_org_members", 1))
            errors.extend(membership_errors(args.membership_export, teams, minimum))
    except (AdoptionError, KeyError, TypeError, ValueError) as error:
        errors = [str(error)]

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "adoption contract validated"
        + (" for production activation" if args.activation else " (source qualification only)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
