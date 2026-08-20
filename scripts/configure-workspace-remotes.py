#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Validate or configure sibling Git clones from the repository catalog."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class GitError(RuntimeError):
    """Raised when a required Git operation fails."""


def run_git(
    repository: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run Git without invoking a shell."""
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise GitError(detail)
    return result


def git_value(repository: Path, *arguments: str) -> str:
    """Return trimmed Git output, or an empty string for an unset value."""
    result = run_git(repository, *arguments, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    """Load and minimally validate the repository catalog."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot read repository catalog {path}: {error}") from error

    if not isinstance(raw, dict):
        raise ValueError(f"repository catalog {path} must be a mapping")

    catalog: dict[str, dict[str, Any]] = {}
    for name, settings in raw.items():
        if not isinstance(name, str) or not REPOSITORY_NAME.fullmatch(name):
            raise ValueError(f"unsafe repository name in catalog: {name!r}")
        if not isinstance(settings, dict):
            raise ValueError(f"catalog entry {name!r} must be a mapping")
        catalog[name] = settings
    return catalog


def remote_urls(repository: Path, remote: str, *, push: bool = False) -> list[str]:
    """Return every configured or effective URL for a remote."""
    arguments = ["remote", "get-url", "--all"]
    if push:
        arguments.append("--push")
    arguments.append(remote)
    output = git_value(repository, *arguments)
    return output.splitlines() if output else []


def configuration_problems(
    repository: Path, expected_url: str, branch: str
) -> list[str]:
    """Describe deviations from the catalog-derived local configuration."""
    remotes = git_value(repository, "remote").splitlines()
    if "origin" not in remotes:
        return ["origin is missing"]

    problems: list[str] = []
    fetch_urls = remote_urls(repository, "origin")
    push_urls = remote_urls(repository, "origin", push=True)
    branch_remote = git_value(repository, "config", "--get", f"branch.{branch}.remote")
    branch_merge = git_value(repository, "config", "--get", f"branch.{branch}.merge")

    if fetch_urls != [expected_url]:
        problems.append(f"origin fetch URL is {fetch_urls or ['<missing>']}")
    if push_urls != [expected_url]:
        problems.append(f"origin push URL is {push_urls or ['<missing>']}")
    if branch_remote != "origin":
        problems.append(f"{branch}.remote is {branch_remote or '<missing>'}")
    if branch_merge != f"refs/heads/{branch}":
        problems.append(f"{branch}.merge is {branch_merge or '<missing>'}")
    return problems


def apply_configuration(repository: Path, expected_url: str, branch: str) -> None:
    """Converge origin and default-branch tracking without touching other remotes."""
    remotes = git_value(repository, "remote").splitlines()
    if "origin" not in remotes:
        run_git(repository, "remote", "add", "origin", expected_url)
    else:
        run_git(
            repository,
            "config",
            "--replace-all",
            "remote.origin.url",
            expected_url,
        )

    # Preserve the usual behavior in which pushes follow the fetch URL. If an
    # explicit push URL exists, make that override canonical as well.
    explicit_push_urls = git_value(
        repository, "config", "--get-all", "remote.origin.pushurl"
    )
    if explicit_push_urls:
        run_git(
            repository,
            "config",
            "--replace-all",
            "remote.origin.pushurl",
            expected_url,
        )

    run_git(
        repository,
        "config",
        "--replace-all",
        f"branch.{branch}.remote",
        "origin",
    )
    run_git(
        repository,
        "config",
        "--replace-all",
        f"branch.{branch}.merge",
        f"refs/heads/{branch}",
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line options."""
    config_repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "Validate local sibling clones against catalog/repositories.yaml. "
            "Check-only mode is the default."
        ),
        epilog=(
            "examples:\n"
            "  configure-workspace-remotes.py\n"
            "  configure-workspace-remotes.py --apply\n"
            "  configure-workspace-remotes.py --workspace /path/to/clones --apply"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=config_repository / "catalog/repositories.yaml",
        help="repository catalog (default: %(default)s)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=config_repository.parent,
        help="directory containing sibling clones (default: %(default)s)",
    )
    parser.add_argument(
        "--organization",
        default="mindclade",
        help="GitHub organization used for canonical HTTPS URLs (default: %(default)s)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply corrections; without this flag the command only reports drift",
    )
    return parser.parse_args()


def main() -> int:
    """Validate or converge all locally available catalog repositories."""
    arguments = parse_arguments()
    catalog_path = arguments.catalog.expanduser().resolve()
    workspace = arguments.workspace.expanduser().resolve()

    try:
        catalog = load_catalog(catalog_path)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    unresolved = False
    for name, settings in sorted(catalog.items()):
        repository = workspace / name
        if not repository.exists():
            print(f"SKIP  {name}: not cloned under {workspace}")
            continue

        top_level = run_git(repository, "rev-parse", "--show-toplevel", check=False)
        if top_level.returncode != 0:
            print(
                f"ERROR {name}: {repository} is not a Git repository", file=sys.stderr
            )
            unresolved = True
            continue
        if Path(top_level.stdout.strip()).resolve() != repository.resolve():
            print(
                f"ERROR {name}: {repository} is not the clone root",
                file=sys.stderr,
            )
            unresolved = True
            continue

        branch = settings.get("default_branch", "main")
        if not isinstance(branch, str) or not branch:
            print(f"ERROR {name}: invalid default_branch {branch!r}", file=sys.stderr)
            unresolved = True
            continue

        expected_url = f"https://github.com/{arguments.organization}/{name}.git"

        try:
            problems = configuration_problems(repository, expected_url, branch)
            fixed = False
            if problems and arguments.apply:
                print(f"DRIFT {name}: {'; '.join(problems)}")
                apply_configuration(repository, expected_url, branch)
                problems = configuration_problems(repository, expected_url, branch)
                if not problems:
                    print(f"FIXED {name}")
                    fixed = True

            if problems:
                print(f"DRIFT {name}: {'; '.join(problems)}")
                unresolved = True
            elif not fixed:
                print(f"OK    {name}")

            for remote in git_value(repository, "remote").splitlines():
                if remote == "origin":
                    continue
                urls = remote_urls(repository, remote)
                print(f"KEEP  {name}: secondary remote {remote} -> {urls}")
        except GitError as error:
            print(f"ERROR {name}: {error}", file=sys.stderr)
            unresolved = True

    if unresolved and not arguments.apply:
        print(
            "Remote drift found; rerun with --apply to correct supported settings.",
            file=sys.stderr,
        )
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
