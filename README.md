# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
# Mindclade GitHub Configuration

Authoritative GitHub Enterprise governance for Mindclade.

## Owns

- repository inventory, visibility, custom properties, and lifecycle;
- teams and team-based access;
- protected environments;
- organization rulesets and mandatory ruleset workflows;
- GitHub Actions and OIDC policy;
- drift detection and documented manual controls.

It does not own reusable workflow implementations (`.github`), Google Cloud infrastructure (`bootstrap` and `infrastructure-live`), Kubernetes desired state (`gitops`), or product source (`mindclade-internal-monorepo`).

## Validate

```bash
make validate
terraform init -backend=false
terraform validate
terraform test
```

## Apply

Pull requests run schema, policy, Terraform, security, and speculative-plan checks. After merge, CI creates a new plan for the exact `main` commit, stores it briefly with an integrity checksum, and applies that exact plan only after the protected `governance` environment gate. Plan and apply use separate GitHub Apps and separate Google Cloud identities; their private keys are environment secrets and are never Terraform variables or plan values.

See [BLUEPRINT.md](BLUEPRINT.md), [docs/architecture.md](docs/architecture.md), and [docs/adoption.md](docs/adoption.md).
