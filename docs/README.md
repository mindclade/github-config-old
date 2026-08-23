<!-- mindclade-doc: documentation-home@1 -->

# Mindclade · GitHub configuration documentation

> **Platform Foundation · GitHub governance**  
> Understand, change, and recover Mindclade's catalog-driven GitHub Enterprise control plane.

## Choose your path

| If you need to... | Start with | You will... |
| --- | --- | --- |
| Understand the control plane | [Architecture](architecture.md) | Learn authority, compilation, trust, and failure boundaries |
| Import or adopt existing GitHub state | [Initial import](initial-import.md) | Preserve history, import resources, and activate protected apply |
| Change access safely | [Access model](access-model.md) | Understand IdP, team, repository, and environment grants |
| Operate manual enterprise controls | [Manual controls](enterprise-manual-controls.md) | Review settings Terraform cannot own |
| Respond to blocked emergency work | [GitHub break-glass](break-glass.md) | Use and revoke the smallest declared bypass |
| Recover a GitHub or IdP outage | [GitHub and IdP outage](github-idp-outage.md) | Preserve evidence, contain access, and restore the authoritative identity path |
| Qualify the three GitHub platform repositories | [GitHub platform qualification](github-platform-qualification.md) | Run native gates, cross-repository contracts, and separate source from connected evidence |

## Getting started

- [Initial import and activation](initial-import.md) — import the repository and qualify
  separate plan and apply identities.
- [Adopt an existing organization](adoption.md) — inventory and import resources without
  destructive recreation.
- [Preserve the canonical monorepo state identity](repository-rename.md) — keep the historical
  repository-key migration non-destructive and verify it by immutable repository ID.
- [Governance activation preflight](governance-activation.md) — sequence release, environment,
  import, reviewer, and ruleset evidence without bypass.
- [Monorepo required-check rollout](monorepo-required-check-rollout.md) — qualify affected Bazel,
  merge-group full validation, critical contexts, and evaluate-to-active promotion.
- [Protected merge-queue rollout](merge-queue-rollout.md) — qualify queues sequentially with
  exact temporary checks, immutable evidence, and protected staged promotion.
- [Onboard an engineer](onboarding.md) and [offboard an engineer](offboarding.md) — change
  access through the corporate identity path.

## Concepts and architecture

- [Architecture](architecture.md) — catalog compilation, trust separation, and failure domains.
- [Access model](access-model.md) — repository classes, grants, owners, and review gates.
- [OIDC governance](oidc.md) — GitHub claim policy and the cloud-trust change sequence.
- [GitHub App authority contracts](github-apps.md) — exact plan/apply/runtime permissions,
  installation selection, qualification, rotation, and revocation.
- [Repository estate operations](repository-operations.md) — dashboard evidence, conservative
  ref retention, protected deletion, activation, and rollback.
- [GitHub platform qualification](github-platform-qualification.md) — workflow adoption graph,
  expiring connected evidence, coordinated pin upgrades, and protected activation preparation.

## Operations

- [Enterprise manual controls](enterprise-manual-controls.md) — monthly review and remediation
  for controls outside the Terraform provider boundary.
- [GitHub break-glass](break-glass.md) — symptom-first emergency governance recovery.
- [GitHub and IdP outage](github-idp-outage.md) — separate provider outage, IdP outage, and
  compromise response while retaining independent approval.
- [`idp/` membership export](../idp/README.md) — generated membership shape, safety checks,
  and IdP ownership.

## Reference and governance

- [Repository classes](repository-classes.md) — policy class definitions and assignment rules.
- [GitHub Actions policy](actions-policy.md) — organization restrictions and required workflow
  ownership.
- [Enterprise reference module](../modules/enterprise/README.md) — deliberately inactive
  enterprise-account resource boundary.
- [Repository production blueprint](../BLUEPRINT.md) — compact authority and exclusion contract.
- [Governance validation](governance-validation.md) — semantic catalog, Terraform, and workflow
  checks plus deferred required-context readiness.
- [Enterprise platform blueprint](MINDCLADE_ENTERPRISE_PLATFORM_FOUNDATION_BLUEPRINT.md) —
  stable pointer to the canonical estate-wide contract.

## Source of truth

The catalog under `catalog/`, its JSON schemas, provider-free normalization in
`modules/catalog/`, Terraform resource modules, protected workflows, tests, and
`contracts/repository.yaml` are authoritative. Documentation explains those controls; it does
not grant access or override a reviewed plan.

## Validate documentation changes

Run from the repository root with no local Terraform cache in the tree:

```sh
nix develop --command make validate
```

Check local links, verify changed examples against the catalog and tests, and preview rendered
Markdown before merge. New pages follow the canonical
[Mindclade documentation templates](https://github.com/mindclade/.github/tree/main/docs/templates).
