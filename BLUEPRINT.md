# Mindclade · `github-config` production blueprint

**Repository class:** `enterprise-control`  
**Visibility:** `private`  
**Default branch:** `main`

## Authoritative responsibilities

- `github-enterprise-governance`
- `repositories`
- `teams`
- `access`
- `rulesets`
- `environments`
- `actions-policy`
- `oidc-policy`

## Explicit exclusions

- `google-cloud-resources`
- `kubernetes-desired-state`
- `shared-workflow-implementation`
- `application-source`

## Operating invariant

All changes are pull-request reviewed, subject to CODEOWNERS and required checks, merged through the configured queue for protected repositories, and performed by narrowly scoped identities. Live-system qualification evidence is separate from source completeness.
