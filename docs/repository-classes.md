<!-- mindclade-doc: reference@1 -->

# Repository classes

> **Audience:** Repository owners and governance reviewers
> **Outcome:** Assign the correct policy class without creating repository-name-specific
> governance.

Classes are declared in `catalog/repository-classes.yaml` and assigned in
`catalog/repositories.yaml`. Organization rulesets target the
`mindclade_repository_class` custom property, so a newly cataloged repository inherits its
class policy without a repository-name edit.

| Class | Intended scope | Baseline |
| --- | --- | --- |
| `enterprise-control` | `.github`, `github-config`, `bootstrap` | Smallest bypass surface and protected control-plane paths |
| `production-control` | `infrastructure-live`, `gitops` | Protected deployment paths, independent approval, merge queue |
| `source-monorepo` | Internal product and build source | Affected CI, ownership, merge queue, release controls |
| `public-sdk` | Approved future public SDKs | Public contribution and release controls |
| `archive` | Retired repositories | Read-only and no deployment authority |

Class changes are security changes. Before assigning a class, also declare owner, criticality,
data classification, lifecycle, CI profile, language profile, and production authority. Run
`python3 scripts/validate-catalog.py` and review the resulting Terraform plan.

See [access model](access-model.md) for grants and ownership.
