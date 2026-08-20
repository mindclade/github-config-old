<!-- mindclade-doc: reference@1 -->

# Repository classes

> **Audience:** Repository owners and governance reviewers
> **Outcome:** Select and verify the policy class that matches a repository's authority and
> lifecycle without introducing repository-name-specific governance.

## Class contract

Classes are declared in [`catalog/repository-classes.yaml`](../catalog/repository-classes.yaml)
and assigned through [`catalog/repositories.yaml`](../catalog/repositories.yaml). Organization
rulesets target the `mindclade_repository_class` custom property.

| Class | Intended scope | Minimum approvals | Code-owner review | Merge queue |
| --- | --- | ---: | --- | --- |
| `enterprise-control` | `.github`, `.github-private`, `github-config`, `bootstrap` | 2 | Required | No |
| `production-control` | `infrastructure-live`, `gitops` | 2 | Required | Yes |
| `source-monorepo` | Product, model, build, and release source | 1 | Required | Yes |
| `public-sdk` | Approved public SDK repositories | 1 | Required | No |
| `archive` | Retired read-only repositories | 0 | No | No |

The table summarizes current catalog values; the catalog remains authoritative.

## Assign or change a class

1. Confirm the repository's authority boundary, visibility, criticality, data classification,
   lifecycle, CI profile, language profile, owner team, and production authority.
2. Update the catalog entry and all required custom properties in one reviewed change.
3. Treat any class change as a security change because it can alter ruleset targeting and merge
   requirements.
4. Review the plan for removed protections, bypass changes, and unexpected custom-property
   defaults.

Do not hard-code a repository name into a ruleset when a class or another reviewed custom
property expresses the policy boundary.

## Verify

```sh
python3 scripts/validate-catalog.py
terraform test -no-color
```

After apply, confirm the repository reports the intended custom properties and receives the
expected rulesets. See the [access model](access-model.md) for grants and ownership.
