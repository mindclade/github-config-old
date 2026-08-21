# Enterprise manual controls

This repository declaratively manages the Mindclade organization surface that is safe to
apply through the organization GitHub App. Enterprise-account controls that lack reliable
provider coverage or require a human enterprise-owner credential remain explicit manual
controls rather than being hidden behind an unaudited PAT.

The canonical account surfaces are the
[Mindclade enterprise](https://github.com/enterprises/mindclade), the
[Mindclade organization](https://github.com/mindclade), and its
[repository index](https://github.com/orgs/mindclade/repositories).

A scheduled drift/review issue is the evidence trail for these settings. Reviewers record the
observed value, any drift, the actor from the audit log, and the remediation.

## Why these controls are manual

- Some enterprise authentication and audit settings are not represented by the pinned GitHub
  Terraform provider.
- Enterprise-owner credentials are recovery-grade human credentials and are not placed in
  ordinary CI.
- A control that cannot be safely planned, reviewed, and applied with a short-lived scoped
  identity is documented rather than simulated as code.

`modules/enterprise/` is a reference implementation for a future separate state and protected
enterprise-credential workflow. It is deliberately not instantiated by the organization root.
Do not run it until that separate trust path has been reviewed and imported safely.

## Monthly checklist

### Identity

| Control | Expected |
|---|---|
| Enterprise SSO | Enabled and enforced |
| Identity provider | Expected tenant and non-expiring certificate path |
| SCIM | Enabled; deprovisioning verified |
| Team synchronization | IdP groups match `catalog/teams.yaml` and `idp/mappings.yaml` |
| Recovery owners | At least two independent, strongly authenticated owners |
| Recovery codes | Stored outside Git in the company credential vault |

### Audit

| Control | Expected |
|---|---|
| Audit-log streaming | Enabled to the central logging destination owned by `infrastructure-live` |
| Stream health | Healthy; no silent pause or delivery gap |
| Retention | Matches Mindclade's security and trust commitments |
| Export access | Limited to security/incident responders |

The optional organization webhook is a low-latency signal, not the audit record. It remains
disabled until an audited endpoint and non-persisted secret-delivery path exist.

### Enterprise policy ceiling

| Control | Expected |
|---|---|
| Repository visibility changes | Restricted to approved owners |
| Repository deletion/transfer | Restricted |
| Base repository permission | Does not weaken the organization default |
| Private/internal forking | Disabled unless explicitly approved |
| Actions policy | No broader than `catalog/actions-policy.yaml`, and not narrower than its required internal action paths |
| Runner groups | Public/untrusted repositories cannot reach private runners |
| Enterprise bypass | Minimal, named, and reviewed |

Organization-level Actions permissions, rulesets, repositories, and environments are managed by
this root. The enterprise policy is the ceiling and must not silently widen them.

The connected organization audit is `scripts/audit-connected-governance.py`. It is GET-only and
fails when any required endpoint is denied; a partial inventory is not compliance evidence. App
installation repository selection requires an approved organization-owner read credential because
one App installation token cannot enumerate another installation through the user-installation
endpoint. The plan App also needs organization Administration write solely because GitHub gates the
organization-ruleset GET endpoint at that permission level; its workflow is non-mutating, but its
token must not be described or handled as intrinsically read-only.

### Private vulnerability reporting

Enable private vulnerability reporting on every **public** repository and as the default for new
public repositories. GitHub exposes this reporter-facing feature only for public repositories;
private and internal repositories return `404` from the endpoint. `drift.yml` therefore checks
the setting only when the repository API reports `visibility=public`. Every repository still
requires its own `SECURITY.md` because the internal `.github` repository does not provide public
community-health inheritance.

### Immutable OIDC default subjects

Every managed repository must use GitHub's immutable default OIDC subject, including owner and
repository IDs. Repositories created after July 15, 2026 receive that format automatically;
pre-cutover repositories require an explicit opt-in through GitHub settings or the REST API.
The pinned Terraform provider resets custom templates with `use_default = true` but does not
model the immutable opt-in. The post-Terraform REST adapter enforces this provider-gap field and
drift checks it nightly. Record the observed subject mode and immutable IDs during monthly review
and before activating or rotating bootstrap WIF trust.

### Billing and contacts

| Control | Expected |
|---|---|
| Billing contact | Monitored Mindclade business mailbox |
| Security contact | Monitored `security@mindclade.com`-class mailbox, not an individual |
| Renewal/payment | Current, with an independent recovery payment path |

## Remediation

Do not fix drift silently. Record the finding first, including the audit actor and timestamp,
then restore the expected value. If the intended value changed, update this document and the
relevant catalog policy in a reviewed pull request.
