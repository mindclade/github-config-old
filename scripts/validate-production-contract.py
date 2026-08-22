#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# MINDCLADE CONFIDENTIAL - PROPRIETARY AND TRADE SECRET
# Copyright (c) 2026 Mindclade. All rights reserved.
"""Validate the Mindclade production repository contract.

This check intentionally uses only the Python standard library.
"""

from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "github-config"
CONTRACT = json.loads(
    '{"authority": ["github-enterprise-governance", "repositories", "teams", "access", "rulesets", "environments", "actions-policy", "oidc-policy"], "forbidden_authority": ["google-cloud-resources", "kubernetes-desired-state", "shared-workflow-implementation", "application-source"], "forbidden_paths": [".terraform", ".terragrunt-cache"], "repository_class": "enterprise-control", "required_paths": ["AGENTS.md", "catalog/repositories.yaml", "catalog/teams.yaml", "catalog/access.yaml", "catalog/environments.yaml", "modules/rulesets", "modules/repositories", "modules/teams"], "visibility": "private"}'
)
ERRORS = []


def error(msg):
    ERRORS.append(msg)


def repository_paths() -> list[Path]:
    """Return delivery paths in a checkout, or all paths in an exported tree.

    Include non-ignored untracked files: they are part of the proposed delivery even before
    the first commit and must not bypass credential, cache, symlink, or identity checks.
    """
    if (ROOT / ".git").exists():
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            capture_output=True,
        )
        return [
            ROOT / raw.decode("utf-8", errors="surrogateescape")
            for raw in result.stdout.split(b"\0")
            if raw
        ]
    return list(ROOT.rglob("*"))


TRACKED_PATHS = repository_paths()
TRACKED_RELATIVE = {p.relative_to(ROOT).as_posix() for p in TRACKED_PATHS}
LEGACY_GITHUB_IDENTITIES = (
    "Mind" + "clade/",
    "github.com/" + "Mind" + "clade",
    "/orgs/" + "Mind" + "clade",
)


def tracked_prefix_exists(relative: str) -> bool:
    prefix = relative.rstrip("/")
    return prefix in TRACKED_RELATIVE or any(
        path.startswith(prefix + "/") for path in TRACKED_RELATIVE
    )


repository_contract = (ROOT / "contracts/repository.yaml").read_text(
    "utf-8", errors="ignore"
)
for canonical_url in (
    "https://github.com/enterprises/mindclade",
    "https://github.com/mindclade",
    "https://github.com/orgs/mindclade/repositories",
    f"https://github.com/mindclade/{REPOSITORY}",
):
    if canonical_url not in repository_contract:
        error(f"repository contract omits canonical GitHub URL: {canonical_url}")
if not re.search(r"(?m)^\s{2}merge_queue:\s*false\s*$", repository_contract):
    error(
        "enterprise-control repository contract must not claim merge-queue enforcement"
    )

for rel in CONTRACT["required_paths"]:
    if not (ROOT / rel).exists():
        error(f"missing required path: {rel}")
for rel in CONTRACT["forbidden_paths"]:
    if tracked_prefix_exists(rel):
        error(f"forbidden tracked path present: {rel}")
for p in TRACKED_PATHS:
    relative = p.relative_to(ROOT)
    if any(
        part in {".terraform", ".terragrunt-cache", "__MACOSX", "__pycache__"}
        for part in relative.parts
    ):
        error(f"local/cache artifact is tracked: {relative}")
    if (
        p.name.startswith("._")
        or ".tfstate" in p.name
        or p.suffix in {".pyc", ".tfplan"}
    ):
        error(f"generated/sensitive artifact is tracked: {relative}")
    if p.is_symlink():
        error(f"symlink forbidden in delivery: {relative}")
    if p.is_file() and p.stat().st_size <= 2_000_000:
        text = p.read_text("utf-8", errors="ignore")
        if any(legacy in text for legacy in LEGACY_GITHUB_IDENTITIES):
            error(f"noncanonical GitHub organization identity in {relative}")

# GitHub Actions must be immutable and least privilege.
for p in (
    (ROOT / ".github/workflows").glob("*.y*ml")
    if (ROOT / ".github/workflows").exists()
    else []
):
    text = p.read_text("utf-8", errors="ignore")
    for use in re.findall(r"(?m)^\s*-?\s*uses:\s*([^#\s]+)", text):
        if use.startswith("./"):
            continue
        if not (
            re.search(r"@[0-9a-f]{40}$", use)
            or re.search(r"@sha256:[0-9a-f]{64}$", use)
            or re.fullmatch(
                r"mindclade/\.github/\.github/workflows/[^@]+@v[0-9]+\.[0-9]+\.[0-9]+",
                use,
            )
        ):
            error(
                f"workflow action is not immutable-pinned in {p.relative_to(ROOT)}: {use}"
            )
    if "permissions:" not in text:
        error(f"workflow lacks explicit permissions: {p.relative_to(ROOT)}")

# No obvious plaintext credentials. Values are intentionally conservative.
secret_patterns = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
]
for p in TRACKED_PATHS:
    if not p.is_file() or p.stat().st_size > 2_000_000:
        continue
    try:
        text = p.read_text("utf-8", errors="ignore")
    except OSError:
        continue
    for pattern in secret_patterns:
        if pattern.search(text):
            error(f"possible credential in {p.relative_to(ROOT)}")

if REPOSITORY == "bootstrap":
    for forbidden in ("modules/folders", "modules/governance"):
        if (ROOT / forbidden).exists():
            error(f"Ring-0 boundary violation: {forbidden}")
    combined = "\n".join(
        p.read_text("utf-8", errors="ignore") for p in ROOT.rglob("*.tf")
    )
    if re.search(r'module\s+"(?:folders|governance)"', combined):
        error("Ring-0 root still instantiates folders/governance")
elif REPOSITORY == "github-config":
    text = (ROOT / "catalog/repositories.yaml").read_text("utf-8", errors="ignore")
    for repo in (
        ".github",
        ".github-private",
        "bootstrap",
        "github-config",
        "infrastructure-live",
        "gitops",
        "mindclade-internal-monorepo",
    ):
        if repo not in text:
            error(f"repository catalog missing {repo}")
    for required_catalog in ("runner-groups.yaml", "github-apps.yaml"):
        if not (ROOT / "catalog" / required_catalog).is_file():
            error(f"GitHub governance catalog is missing {required_catalog}")
    if "default_branch" not in text or "main" not in text:
        error("catalog does not enforce main as the default branch")
    oidc_policy = (ROOT / "catalog/oidc-policy.yaml").read_text(
        "utf-8", errors="ignore"
    )
    if "repository_opt_in: false" not in oidc_policy:
        error(
            "managed repositories are not explicitly reset to GitHub default OIDC subjects"
        )
    if "require_immutable_default_subject: true" not in oidc_policy:
        error("catalog does not require GitHub immutable default OIDC subjects")
    immutable_adapter = ROOT / "scripts/enforce-immutable-oidc.py"
    if not immutable_adapter.is_file():
        error("missing immutable OIDC provider-gap adapter")
    for workflow_name, invocation in (
        ("plan.yml", "scripts/enforce-immutable-oidc.py"),
        ("apply.yml", "scripts/enforce-immutable-oidc.py --apply"),
        ("drift.yml", "scripts/enforce-immutable-oidc.py"),
    ):
        workflow = (ROOT / ".github/workflows" / workflow_name).read_text(
            "utf-8", errors="ignore"
        )
        if invocation not in workflow:
            error(f"{workflow_name} omits immutable OIDC enforcement: {invocation}")
    ci_variables = (ROOT / "modules/repositories/ci-variables.tf").read_text(
        "utf-8", errors="ignore"
    )
    if re.search(r"subject/repo:mindclade/", ci_variables):
        error(
            "legacy name-only GitHub OIDC principal remains in the CI-variable contract"
        )
    if (
        "subject/repo:mindclade@[0-9]+/mindclade-internal-monorepo@[0-9]+"
        not in ci_variables
    ):
        error(
            "artifact signer contract does not require immutable owner/repository IDs"
        )
    residency_catalog = (ROOT / "catalog/ci-variables.yaml").read_text(
        "utf-8", errors="ignore"
    )
    for required_location in (
        "RESIDENCY_PROFILE: us-only-v1",
        "GCP_REGION: us-central1",
        "STATE_BUCKET_LOCATION: US",
        "STATE_KMS_LOCATION: us",
        "STATE_REPLICA_LOCATION: us-east4",
        "STATE_REPLICA_KMS_LOCATION: us-east4",
        "PRIMARY_REGION: us-central1",
        "GPU_ZONE: us-central1-b",
        "DR_REGION: us-east4",
        "DR_GPU_ZONE: us-east4-b",
        "ARTIFACT_REGISTRY_HOST: us-central1-docker.pkg.dev",
        "ARTIFACT_REGISTRY_DR_HOST: us-east4-docker.pkg.dev",
    ):
        if required_location not in residency_catalog:
            error(f"U.S. residency CI-variable contract omits: {required_location}")
    if re.search(
        r"(?m)^\s+[A-Z0-9_]+:\s+(?:europe|asia|australia|northamerica|southamerica|me|africa)-",
        residency_catalog,
    ):
        error("CI-variable contract contains a non-U.S. deployable location")
elif REPOSITORY == "gitops":
    for p in list((ROOT / "applications").glob("*.yaml")) + list(
        (ROOT / "projects").glob("*.yaml")
    ):
        text = p.read_text("utf-8", errors="ignore")
        if re.search(
            r'(?m)^\s*(?:sourceRepos|destinations):\s*\[?\s*["\']?\*["\']?', text
        ):
            error(f"wildcard Argo authority in {p.relative_to(ROOT)}")
    for p in ROOT.rglob("*.y*ml"):
        # Negative policy fixtures intentionally contain denied examples.
        if "tests" in p.parts or "testdata" in p.parts:
            continue
        text = p.read_text("utf-8", errors="ignore")
        if re.search(
            r'(?i)(?:image|newName|newTag):?[^\n]*(?::latest|newTag:\s*["\']?latest)',
            text,
        ):
            error(f"mutable image tag in {p.relative_to(ROOT)}")
        if re.search(r"(?m)^kind:\s*Secret\s*$", text) and re.search(
            r"(?m)^\s*(?:data|stringData):\s*$", text
        ):
            error(f"plaintext Kubernetes Secret object in {p.relative_to(ROOT)}")
elif REPOSITORY == "infrastructure-live":
    for env in ("development", "staging", "production"):
        if not (ROOT / f"5-workloads/{env}").is_dir():
            error(f"missing workload environment {env}")
    for p in ROOT.rglob("*.hcl"):
        text = p.read_text("utf-8", errors="ignore")
        if "ANY_IDENTITY" in text:
            error(f"VPC-SC ANY_IDENTITY escape in {p.relative_to(ROOT)}")
        if re.search(r"(?<![0-9])0\.0\.0\.0/0(?![0-9])", text) and re.search(
            r"(?i)(master_authorized|control[_-]?plane|authorized[_-]?network)", text
        ):
            error(
                f"broad control-plane CIDR in live configuration: {p.relative_to(ROOT)}"
            )

if ERRORS:
    for msg in sorted(set(ERRORS)):
        print(f"ERROR: {msg}", file=sys.stderr)
    print(f"{len(set(ERRORS))} production contract violation(s)", file=sys.stderr)
    raise SystemExit(1)
print(f"{REPOSITORY}: production contract passed")
