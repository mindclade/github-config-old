# Access Model

Mindclade access is team-based, catalog-driven, and least-privilege. Human lifecycle is owned by the corporate identity provider; `github-config` maps approved groups into GitHub teams and repository permissions.

## Repository classes

| Class | Scope | Baseline |
|---|---|---|
| `enterprise-control` | `.github`, `.github-private`, `github-config`, `bootstrap` | Strongest governance and smallest bypass surface |
| `production-control` | `infrastructure-live`, `gitops` | Protected deployment paths, two approvals, merge queue |
| `source-monorepo` | `mindclade-internal-monorepo` | Affected CI, CODEOWNERS, merge queue, release controls |
| `public-sdk` | Future public SDKs | Public contribution and release controls |
| `archive` | Retired repositories | Read-only, no deployment authority |

Rulesets target `mindclade_repository_class`, not repository names. New repositories inherit the correct policy only after their class, owner, criticality, data classification, lifecycle, CI profile, and production-authority properties are declared.

## Grants

Standing access is granted to teams with `pull`, `triage`, `push`, or `maintain`. Catalog-managed teams never receive repository `admin`; organization owners and narrowly scoped automation retain only the administrative capabilities required by their role.

Direct user grants are prohibited except documented, time-bounded emergency or temporary access in `catalog/access-exceptions.yaml`.

## Critical ownership

- Security owns `github-config` and GitHub policy.
- Infrastructure owns `bootstrap` and `infrastructure-live`.
- Platform owns `.github` and `gitops`.
- Engineering owns the monorepo; release and security retain review authority.

## Review gates

Production, governance, bootstrap, release, and break-glass operations use protected GitHub environments. Production-control and Ring-0 changes require independent qualified reviewers; self-review is disabled. During a genuine solo-founder period, any exception must be explicit, expiring, and followed by documented post-change review.

The temporary `bootstrap-reviewers` team implements that exception without placing the founder in
the broader `infrastructure` or `security` teams. It is standalone, receives only `pull` on
`bootstrap`, `github-config`, and `infrastructure-live`, and can review only the shared `plan`,
`bootstrap`, and `bootstrap-recovery-read` environments. The `plan` environment is shared by those
three repositories, so its read-only approval scope cannot be narrowed to `bootstrap` without a
separate WIF and environment migration.

`robpearc` and `mindclade-founder` represent the same human. Approval through those accounts is
therefore explicitly **not independent review**. It is a 90-day solo-founder exception expiring at
2026-11-18 23:59 America/Detroit, must be renewed or revoked through the protected procedure, and
requires qualified retrospective review when a second human becomes available. See
[`solo-founder-reviewer.md`](solo-founder-reviewer.md).
