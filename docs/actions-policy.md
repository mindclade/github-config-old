<!-- mindclade-doc: reference@1 -->

# GitHub Actions policy

> **Audience:** Workflow authors and governance reviewers
> **Outcome:** Understand which repository owns Actions policy and which controls are
> mandatory for privileged workflows.

`github-config` declares organization Actions policy and attaches mandatory workflow rules.
The `.github` repository owns the workflow implementations and immutable releases.

Privileged workflows use explicit permissions, immutable third-party action SHAs, protected
environments, and GitHub OIDC with Google Cloud Workload Identity Federation. Service-account
JSON keys are not an accepted authentication path. Mandatory workflow implementations are
referenced by the immutable full-semver tag in `catalog/rulesets.yaml`.

Changes to Actions allowlists, OIDC policy, required workflows, or protected workflow paths
are security changes and require the owners identified by `CODEOWNERS`.

See [OIDC governance](oidc.md), the
[shared workflow trust model](https://github.com/mindclade/.github/blob/main/docs/workflow-trust.md),
and [architecture](architecture.md).
