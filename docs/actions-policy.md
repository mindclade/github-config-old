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
