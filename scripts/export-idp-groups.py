#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Project Cloud Identity membership into governed GitHub organization membership."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
MAPPINGS_PATH = ROOT / "idp/mappings.yaml"


def load_mapping_contract(path: Path = MAPPINGS_PATH) -> dict[str, Any]:
    """Load the sole directory-group mapping contract.

    Keeping these values in YAML makes review, schema validation, the exporter, and connected
    qualification consume one source. In particular, no script may derive a privileged group
    address from a GitHub team key.
    """

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(f"cannot load {path}: {error}") from error
    if not isinstance(document, dict):
        raise RuntimeError(f"{path} must contain a mapping")
    return document


MAPPING_CONTRACT = load_mapping_contract()
OUTPUT = ROOT / str(MAPPING_CONTRACT["membership_export"]["path"])
TEAM_GROUPS = {
    name: str(config["directory_group"])
    for name, config in MAPPING_CONTRACT["groups"].items()
    if config.get("status") == "mapped"
}
DEFERRED_TEAMS = {
    name
    for name, config in MAPPING_CONTRACT["groups"].items()
    if config.get("status") == "deferred"
}
ORGANIZATION_ADMIN_GROUP = str(MAPPING_CONTRACT["organization_admin_group"])
INDEPENDENT_REVIEW_TEAMS = {"legal", "platform", "security"}


class ExportError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print, check, or explicitly apply the IdP membership projection."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="exit 3 when committed data is stale"
    )
    mode.add_argument(
        "--apply", action="store_true", help="atomically update idp/team-members.json"
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="deprecated alias for the default print mode",
    )
    parser.add_argument(
        "--domain", default=os.environ.get("IDP_DOMAIN", "mindclade.com")
    )
    parser.add_argument("--customer-id", default=os.environ.get("IDP_CUSTOMER_ID", ""))
    parser.add_argument(
        "--billing-project",
        default=os.environ.get("IDP_BILLING_PROJECT", ""),
        help="quota project for Cloud Identity API requests",
    )
    return parser.parse_args()


def gcloud_json(arguments: list[str], billing_project: str = "") -> Any:
    command = ["gcloud", *arguments, "--format=json"]
    if billing_project:
        command.append(f"--billing-project={billing_project}")
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as error:
        raise ExportError(
            "gcloud not found on PATH; install the Google Cloud SDK"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (
            error.stderr.strip()
            or error.stdout.strip()
            or f"exit status {error.returncode}"
        )
        raise ExportError(f"gcloud {' '.join(arguments)} failed: {detail}") from error
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExportError(
            f"gcloud {' '.join(arguments)} returned invalid JSON: {error}"
        ) from error


def customer_id(explicit: str, billing_project: str = "") -> str:
    if explicit:
        return explicit
    organizations = gcloud_json(["organizations", "list"], billing_project)
    for organization in organizations:
        value = organization.get("owner", {}).get("directoryCustomerId")
        if value:
            return str(value)
    raise ExportError(
        "could not determine Cloud Identity customer id; set IDP_CUSTOMER_ID"
    )


def group_members(group: str, billing_project: str = "") -> list[dict[str, str]]:
    try:
        described = gcloud_json(
            ["identity", "groups", "describe", group], billing_project
        )
    except ExportError as error:
        raise ExportError(
            f"required directory group {group} could not be resolved; refusing a partial export: {error}"
        ) from error
    group_name = described.get("name")
    if not group_name:
        raise ExportError(f"required directory group {group} has no immutable name")
    memberships = gcloud_json(
        ["identity", "groups", "memberships", "list", f"--group-email={group}"],
        billing_project,
    )
    members: list[dict[str, str]] = []
    for membership in memberships:
        if membership.get("type") != "USER":
            continue
        email = membership.get("preferredMemberKey", {}).get("id")
        if not email:
            raise ExportError(
                f"group {group} returned a user membership without an email"
            )
        roles = {role.get("name") for role in membership.get("roles", [])}
        members.append(
            {
                "email": str(email),
                "role": "maintainer" if "MANAGER" in roles else "member",
            }
        )
    return members


def github_login(email: str, billing_project: str = "") -> str | None:
    user = gcloud_json(
        ["identity", "users", "describe", email], billing_project
    )
    value = user.get("customSchemas", {}).get("github", {}).get("login")
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def build_document(
    domain: str, billing_project: str = ""
) -> tuple[dict[str, Any], list[str]]:
    roles: dict[str, str] = {}
    logins: dict[str, str | None] = {}
    unmapped: set[str] = set()
    teams: dict[str, list[dict[str, str]]] = {}

    if DEFERRED_TEAMS:
        print(
            "::warning::directory group addresses are not yet verified for catalog teams: "
            + ", ".join(sorted(DEFERRED_TEAMS)),
            file=sys.stderr,
        )

    def resolve(email: str) -> str | None:
        if email not in logins:
            logins[email] = github_login(email, billing_project)
        if logins[email] is None:
            unmapped.add(email)
        return logins[email]

    for team, pattern in TEAM_GROUPS.items():
        group = pattern.format(domain=domain)
        print(f"  {team} ← {group}", file=sys.stderr)
        team_members: list[dict[str, str]] = []
        for member in group_members(group, billing_project):
            login = resolve(member["email"])
            if login is None:
                continue
            roles.setdefault(login, "member")
            team_members.append({"username": login, "role": member["role"]})
        teams[team] = sorted(team_members, key=lambda item: item["username"])

    admin_group = ORGANIZATION_ADMIN_GROUP.format(domain=domain)
    print(f"  org admins ← {admin_group}", file=sys.stderr)
    for member in group_members(admin_group, billing_project):
        login = resolve(member["email"])
        if login is not None:
            roles[login] = "admin"

    document = {
        "org_members": [
            {"username": login, "role": role} for login, role in sorted(roles.items())
        ],
        "team_members": dict(sorted(teams.items())),
    }
    if not document["org_members"]:
        raise ExportError(
            "the export contains no organization members; refusing a likely destructive projection"
        )
    validate_independent_review_membership(document)
    return document, sorted(unmapped)


def empty_team_regressions(
    current: dict[str, Any], generated: dict[str, Any]
) -> list[str]:
    regressions = []
    for team, members in current.get("team_members", {}).items():
        if members and not generated.get("team_members", {}).get(team, []):
            regressions.append(f"{team} (had {len(members)})")
    return regressions


def validate_independent_review_membership(document: dict[str, Any]) -> None:
    """Require independently staffed Legal, Platform, and Security approval groups."""
    if not INDEPENDENT_REVIEW_TEAMS.issubset(TEAM_GROUPS):
        # A deferred mapping is already a production-activation blocker. Do not guess the
        # directory group or turn ordinary read-only exports into a substitute mapping.
        return
    team_members = document.get("team_members", {})
    populations: dict[str, set[str]] = {}
    for team in sorted(INDEPENDENT_REVIEW_TEAMS):
        members = team_members.get(team, [])
        populations[team] = {str(member.get("username", "")) for member in members}
        populations[team].discard("")
        if not populations[team]:
            raise ExportError(
                f"independent approval team {team} has no resolvable GitHub members"
            )
    for left in sorted(INDEPENDENT_REVIEW_TEAMS):
        for right in sorted(INDEPENDENT_REVIEW_TEAMS):
            if left >= right:
                continue
            overlap = populations[left] & populations[right]
            if overlap:
                raise ExportError(
                    f"independent approval teams {left} and {right} overlap: "
                    + ", ".join(sorted(overlap))
                )


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    try:
        directory_customer = customer_id(args.customer_id, args.billing_project)
        print(
            f"Exporting from directory {directory_customer} ({args.domain})...",
            file=sys.stderr,
        )
        document, unmapped = build_document(args.domain, args.billing_project)
        generated = render(document)
        current_document = (
            json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.is_file() else None
        )
        regressions = (
            empty_team_regressions(current_document, document)
            if current_document is not None
            else []
        )
        if regressions:
            print(
                "::error::this export would empty a team that currently has members:",
                file=sys.stderr,
            )
            for regression in regressions:
                print(f"  - {regression}", file=sys.stderr)
            if args.apply and os.environ.get("IDP_ALLOW_TEAM_EMPTY") != "1":
                raise ExportError(
                    "set IDP_ALLOW_TEAM_EMPTY=1 only after confirming the removals"
                )
            print(
                "::warning::read-only mode; no membership file was changed",
                file=sys.stderr,
            )
        if unmapped:
            print(
                f"::warning::{len(unmapped)} directory user(s) have no linked GitHub login and were omitted:",
                file=sys.stderr,
            )
            for email in unmapped:
                print(f"  {email}", file=sys.stderr)

        count = len(document["org_members"])
        if args.check:
            if current_document is None:
                raise ExportError(
                    "idp/team-members.json does not exist; use --apply after review"
                )
            current = render(current_document)
            if current == generated:
                print(f"idp/team-members.json is current ({count} org member(s)).")
                return 0
            sys.stdout.writelines(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    generated.splitlines(keepends=True),
                    fromfile="idp/team-members.json",
                    tofile="generated projection",
                )
            )
            print("::error::idp/team-members.json is stale", file=sys.stderr)
            return 3
        if args.apply:
            atomic_write(OUTPUT, generated)
            print(
                f"Wrote idp/team-members.json — {count} org member(s), "
                f"{len(document['team_members'])} team(s)."
            )
        else:
            sys.stdout.write(generated)
        return 0
    except (ExportError, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
