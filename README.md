# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Mindclade GitHub Configuration

Authoritative GitHub Enterprise governance for Mindclade.

Canonical GitHub locations:
[enterprise](https://github.com/enterprises/mindclade),
[organization](https://github.com/mindclade),
[repository index](https://github.com/orgs/mindclade/repositories), and
[`mindclade/github-config`](https://github.com/mindclade/github-config).

## Owns

- repository inventory, visibility, custom properties, and lifecycle;
- teams and team-based access;
- protected environments;
- organization rulesets and mandatory ruleset workflows;
- GitHub Actions and OIDC policy;
- drift detection and documented manual controls.

It does not own reusable workflow implementations (`.github`), Google Cloud infrastructure
(`bootstrap` and `infrastructure-live`), Kubernetes desired state (`gitops`), or product source
(`mindclade-internal-monorepo`).

## Validate

Use the repository-pinned toolchain:

```bash
nix develop --command make validate
terraform init -input=false -backend=false
terraform validate -no-color
terraform test -no-color
```

Backend-disabled validation and tests do not mutate GitHub or cloud state.

## Apply

Pull requests run schema, policy, Terraform, security, and speculative-plan checks. The
credentialed plan job uses the protected `plan` environment. After merge, CI creates a new
plan for the exact `main` commit, stores it briefly with an integrity checksum, and applies
that exact plan only after the protected `governance` environment gate. Plan and apply use
separate GitHub Apps and separate Google Cloud identities; their private keys are environment
secrets and are never Terraform variables or plan values.

See [BLUEPRINT.md](BLUEPRINT.md), [adoption guidance](docs/adoption.md), and the
[enterprise platform blueprint](docs/MINDCLADE_ENTERPRISE_PLATFORM_FOUNDATION_BLUEPRINT.md).
