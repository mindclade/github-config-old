#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Check or enforce immutable GitHub Actions OIDC subjects.

The pinned GitHub Terraform provider manages custom subject claims and each
repository's ``use_default`` flag, but it does not yet model GitHub's
``use_immutable_subject`` field. This narrow REST adapter closes that provider
gap without taking ownership of any other OIDC setting.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
API_VERSION = "2026-03-10"


class OIDCError(RuntimeError):
    """An authoritative input or GitHub API operation failed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or enforce immutable GitHub Actions OIDC subjects."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="set the catalog-declared organization and repository policy",
    )
    parser.add_argument(
        "--organization",
        default=os.environ.get("ORGANIZATION", "mindclade"),
    )
    return parser.parse_args()


def top_level_keys(path: Path) -> list[str]:
    """Read top-level mapping keys from the repository catalog's constrained YAML."""
    keys: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw[0].isspace() or raw.startswith(("#", "---")):
            continue
        match = re.fullmatch(r"([^:#][^:]*)\s*:\s*", raw)
        if match:
            keys.append(match.group(1).strip().strip('"\''))
    if not keys:
        raise OIDCError(f"no top-level keys found in {path}")
    return keys


def oidc_policy(path: Path) -> tuple[list[str], bool, bool]:
    """Read the three OIDC values this adapter is authorized to enforce."""
    claims: list[str] = []
    repository_opt_in: bool | None = None
    immutable_required: bool | None = None
    in_claims = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "---")):
            continue
        if raw == "subject_claim_keys:":
            in_claims = True
            continue
        if raw and not raw[0].isspace():
            in_claims = False
            key, separator, value = raw.partition(":")
            if not separator:
                continue
            normalized = value.strip().lower()
            if key == "repository_opt_in":
                repository_opt_in = normalized == "true"
            elif key == "require_immutable_default_subject":
                immutable_required = normalized == "true"
        elif in_claims and stripped.startswith("- "):
            claims.append(stripped[2:].strip())

    if not claims:
        raise OIDCError(f"subject_claim_keys is empty in {path}")
    if repository_opt_in is None or immutable_required is None:
        raise OIDCError(f"required OIDC policy keys are missing from {path}")
    if not immutable_required:
        raise OIDCError("catalog does not require immutable OIDC subjects")
    return claims, repository_opt_in, immutable_required


def gh_api(
    path: str,
    *,
    method: str = "GET",
    typed_fields: tuple[str, ...] = (),
    raw_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Call GitHub through gh without placing a credential in argv or output."""
    command = [
        "gh",
        "api",
        path,
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
    ]
    if method != "GET":
        command.extend(("--method", method))
    for field in typed_fields:
        command.extend(("--field", field))
    for field in raw_fields:
        command.extend(("--raw-field", field))

    environment = os.environ.copy()
    environment.setdefault("GODEBUG", "http2client=0")
    last_error = "unknown GitHub API failure"
    for attempt in range(1, 5):
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )
        if result.returncode == 0:
            if not result.stdout.strip():
                return {}
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as error:
                raise OIDCError(f"GitHub returned invalid JSON for {path}: {error}") from error
        last_error = result.stderr.strip() or f"exit status {result.returncode}"
        if attempt < 4:
            time.sleep(attempt)
    raise OIDCError(f"GitHub API {method} {path} failed: {last_error}")


def organization_expected(actual: dict[str, Any], claims: list[str]) -> list[str]:
    errors: list[str] = []
    if actual.get("include_claim_keys") != claims:
        errors.append(
            "organization include_claim_keys does not match catalog: "
            f"{actual.get('include_claim_keys')!r}"
        )
    if actual.get("use_immutable_subject") is not True:
        errors.append("organization use_immutable_subject is not true")
    return errors


def repository_expected(
    repository: str,
    actual: dict[str, Any],
    *,
    organization: str,
    use_default: bool,
    claims: list[str],
) -> list[str]:
    errors: list[str] = []
    if actual.get("use_default") is not use_default:
        errors.append(
            f"{repository}: use_default is {actual.get('use_default')!r}, "
            f"expected {use_default!r}"
        )
    if not use_default and actual.get("include_claim_keys") != claims:
        errors.append(f"{repository}: custom claims do not match catalog")
    if actual.get("use_immutable_subject") is not True:
        errors.append(f"{repository}: use_immutable_subject is not true")

    prefix = actual.get("sub_claim_prefix", "")
    expected_prefix = re.compile(
        rf"^repo:{re.escape(organization)}@[0-9]+/"
        rf"{re.escape(repository)}@[0-9]+$"
    )
    if not expected_prefix.fullmatch(prefix):
        errors.append(f"{repository}: immutable sub_claim_prefix is absent or malformed")
    return errors


def apply_policy(
    organization: str,
    repositories: list[str],
    claims: list[str],
    repository_opt_in: bool,
) -> None:
    gh_api(
        f"orgs/{organization}/actions/oidc/customization/sub",
        method="PUT",
        typed_fields=("use_immutable_subject=true",),
        raw_fields=tuple(f"include_claim_keys[]={claim}" for claim in claims),
    )

    use_default = not repository_opt_in
    for repository in repositories:
        raw_fields = (
            ()
            if use_default
            else tuple(f"include_claim_keys[]={claim}" for claim in claims)
        )
        gh_api(
            f"repos/{organization}/{repository}/actions/oidc/customization/sub",
            method="PUT",
            typed_fields=(
                f"use_default={str(use_default).lower()}",
                "use_immutable_subject=true",
            ),
            raw_fields=raw_fields,
        )


def check_policy(
    organization: str,
    repositories: list[str],
    claims: list[str],
    repository_opt_in: bool,
) -> list[str]:
    errors = organization_expected(
        gh_api(f"orgs/{organization}/actions/oidc/customization/sub"), claims
    )
    use_default = not repository_opt_in
    for repository in repositories:
        actual = gh_api(
            f"repos/{organization}/{repository}/actions/oidc/customization/sub"
        )
        errors.extend(
            repository_expected(
                repository,
                actual,
                organization=organization,
                use_default=use_default,
                claims=claims,
            )
        )
    return errors


def main() -> int:
    args = parse_args()
    try:
        repositories = top_level_keys(ROOT / "catalog/repositories.yaml")
        claims, repository_opt_in, _ = oidc_policy(ROOT / "catalog/oidc-policy.yaml")
        if args.apply:
            apply_policy(args.organization, repositories, claims, repository_opt_in)
        errors = check_policy(
            args.organization, repositories, claims, repository_opt_in
        )
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print(
                f"immutable OIDC policy failed for {len(errors)} condition(s)",
                file=sys.stderr,
            )
            return 1
        action = "enforced and verified" if args.apply else "verified"
        print(
            f"immutable OIDC policy {action}: {len(repositories)} repositories"
        )
        return 0
    except (OIDCError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
