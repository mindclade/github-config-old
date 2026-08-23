<!-- mindclade-doc: reference@1 -->

# GitHub Actions policy

> **Audience:** Workflow authors and governance reviewers
> **Outcome:** Look up the organization restrictions, ownership boundary, and validation path
> for privileged GitHub Actions workflows.

## Ownership boundary

`github-config` declares organization Actions policy and attaches mandatory workflow rules.
The `.github` repository owns the required workflow implementations, contracts, and immutable
releases. Cloud IAM remains in `bootstrap` or `infrastructure-live`.

## Enforced controls

| Control | Current contract | Source of truth |
| --- | --- | --- |
| Repository coverage | All governed repositories | [`catalog/actions-policy.yaml`](../catalog/actions-policy.yaml) |
| Allowed actions | Selected allowlist only | [`catalog/actions-policy.yaml`](../catalog/actions-policy.yaml) |
| Default token permissions | Read | [`catalog/actions-policy.yaml`](../catalog/actions-policy.yaml) |
| Workflow PR approval | Disabled for `GITHUB_TOKEN` | [`catalog/actions-policy.yaml`](../catalog/actions-policy.yaml) |
| Composite-action references | Full commit SHA required | Catalog plus repository pin validators |
| Mandatory workflows | Immutable full-semver `.github` release | [`catalog/rulesets.yaml`](../catalog/rulesets.yaml) |
| Privileged cloud jobs | Protected environment and GitHub OIDC/WIF | [OIDC governance](oidc.md) |

GitHub-owned and verified-creator actions are not implicitly trusted; an action must match the
reviewed allowlist. Service-account JSON keys are not an accepted authentication path.

Action subpaths are separate allowlist identities. A repository-level entry such as
`actions/cache@*` does not authorize the reviewed `actions/cache/restore` and
`actions/cache/save` entry points; each subpath used by a workflow must be listed explicitly.
The same rule applies to actions invoked transitively by an allowlisted reusable workflow.
Mindclade's repository-home action is allowlisted only at its exact
`mindclade/.github/actions/validate-repository-home` subpath; adding another first-party action
requires its own reviewed catalog entry.

Workflow-release preflights compare connected tag governance to `RELEASE_TEAM_ID`. Terraform
derives that repository variable directly from the immutable Release-team resource; it is not a
catalog or operator input and grants no authority. Missing environment protections, an inactive
creation rule, a different bypass actor, or an API response that omits bypass evidence blocks
draft assembly and publication.

Nix cache publication uses the dedicated `nix-cache-publication` environment on only
`mindclade-internal-monorepo`. It requires protected main, reviewer eligibility from Platform or
Security, a five-minute wait, and no self-review. GitHub requires one eligible environment
reviewer, not one reviewer from each team. The environment is only an authorization boundary: no
cache endpoint, public key, token, or caller is cataloged while the cache activation contract is
blocked. A future activation must add non-secret endpoint/key variables and a scoped write-token
secret through protected operations after connected qualification; a signing key is forbidden.

The Bazel GCS cache uses `BAZEL_REMOTE_CACHE_STATE` as the server-side half of a separate dual
gate. It remains `blocked` even after the provider and reader/writer account names are handed off.
Governance permits `qualified-v1` only when that complete applied handoff exists; the monorepo
independently requires retained behavioral evidence, immutable module `v0.4.0`, and job-scoped
OIDC permission. The variable alone cannot mint a token, and workflow-level OIDC remains
forbidden.

Immutable workstation-image publication uses a separate
`workstation-image-publication` environment on only `mindclade-internal-monorepo`, with the same
Platform/Security reviewers, five-minute wait, protected-main requirement, and no self-review.
Its exact WIF provider permits only the reviewed `nixos-image.yml` caller and v5 reusable workflow.
The workflow may publish only a create-only raw-disk source object; Terraform retains exclusive
Compute Image and workstation rollout authority.

Changes to the allowlist, OIDC policy, required workflows, protected workflow paths, or token
permissions are security changes and require the owners declared by `CODEOWNERS`.

## Validate a change

From the repository root:

```sh
python3 scripts/validate-catalog.py
terraform test -no-color
```

Then review the Terraform plan for organization-wide widening, workflow replacement, or a
required check that will never report. A successful parser run does not prove the resulting
GitHub policy is least privilege.

## Related documentation

- [OIDC governance](oidc.md)
- [Repository classes](repository-classes.md)
- [Shared workflow trust model](https://github.com/mindclade/.github/blob/main/docs/workflow-trust.md)
- [Architecture](architecture.md)
