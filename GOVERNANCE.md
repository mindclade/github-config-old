<!-- mindclade-doc: governance@1 -->

# Mindclade governance · `github-config`

| Document control | Value |
| --- | --- |
| Owner | Mindclade Platform |
| Version | 1.0 |
| Last reviewed | August 21, 2026 |
| Authority | GitHub Enterprise repositories, teams, access, rulesets, environments, applications, and policy |

## Authority boundary

The catalog and Terraform in this repository are the authoritative desired
state for the scopes listed in
[contracts/repository.yaml](contracts/repository.yaml). This repository does
not own cloud resources, Kubernetes desired state, shared workflow
implementations, or application source.

## Decisions and approvals

Routine catalog changes require passing checks, one approval, and code-owner
review. Changes to organization policy, rulesets, teams, access, applications,
OIDC claims, environments, bypass, or repository visibility require Security
approval. Destructive or estate-wide changes require an explicit plan review
and two qualified approvals.

## Evidence and application

Pull requests record affected managed objects, access and trust impact,
destructive actions, rollout, rollback, and exact validation commands. A plan
is review evidence; only the protected apply environment may authorize
mutation. Manual enterprise controls are recorded in
[docs/enterprise-manual-controls.md](docs/enterprise-manual-controls.md).

## Exceptions and review

Every bypass or temporary access exception has a named recipient, owner,
approver, reason, exact scope, start, expiry, and review record. Exceptions
never waive security, confidentiality, licensing, or audit requirements.

Terraform drift is checked automatically. Access, installed applications,
rulesets, bypass use, and manual controls are reviewed on the cadence defined
by the organization governance policy:
[`mindclade/.github/GOVERNANCE.md`](https://github.com/mindclade/.github/blob/main/GOVERNANCE.md).

