# Enterprise manual controls

This repository declaratively manages the Mindclade organization surface that is safe to
apply through the organization GitHub App. Enterprise-account controls that lack reliable
provider coverage or require a human enterprise-owner credential remain explicit manual
controls rather than being hidden behind an unaudited PAT.

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
| Actions policy | No broader than `catalog/actions-policy.yaml` |
| Runner groups | Public/untrusted repositories cannot reach private runners |
| Enterprise bypass | Minimal, named, and reviewed |

Organization-level Actions permissions, rulesets, repositories, and environments are managed by
this root. The enterprise policy is the ceiling and must not silently widen them.

### Private vulnerability reporting

Enable private vulnerability reporting on every repository and as the default for new
repositories. The pinned provider does not manage this setting, so `drift.yml` checks it with
the GitHub API and reports any repository where it is disabled.

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
