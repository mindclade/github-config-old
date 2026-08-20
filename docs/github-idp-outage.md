<!-- mindclade-doc: runbook@1 -->

# Recover from a GitHub or identity-provider outage

Owner: Security incident commander. Operators: one primary and one distinct observer recorded in
the drill or incident report. This runbook covers GitHub Enterprise Cloud unavailability, IdP/SCIM
unavailability, and loss of normal SSO access; it does not authorize bypass creation.

## Symptoms and impact

- GitHub status or API probes fail across independent networks.
- SAML login, SCIM provisioning, or team synchronization fails while GitHub remains available.
- Existing sessions work but new sessions cannot authenticate.
- Repository administration, protected workflow approval, or emergency merge capability is lost.

Declare an incident before changing access. Treat unexpected SSO configuration or membership
changes as compromise, freeze catalog applies, and follow the security response path.

## Preconditions and abort conditions

Record the exact `github-config` commit, UTC start time, affected identities, GitHub status evidence,
and IdP evidence. Confirm the primary and observer identities through an out-of-band channel.
Abort a drill immediately if production access, billing, organization ownership, signing identity,
or an undeclared tenant would be changed.

## Read-only diagnosis

1. Compare GitHub's service status with IdP health and an independent network probe.
2. From an already authenticated read-only session, capture organization audit-log continuity,
   SAML/SCIM status, pending invitations, owners, and recent role changes.
3. Run `make plan` only with the protected plan identity when service availability permits; never
   use a speculative plan as proof that the IdP is healthy.
4. Classify the fault as GitHub outage, IdP outage, federation/configuration failure, or suspected
   compromise. Preserve all command output with hashes.

## Recovery

For a GitHub outage, keep deployments and governance applies frozen, monitor status, and validate
audit-log continuity after service restoration. For an IdP outage, restore the authoritative IdP
first and allow SCIM/team reconciliation from declared catalog state. Use an existing, separately
custodied break-glass identity only when the incident commander authorizes the documented
[break-glass procedure](break-glass.md); do not create a new owner or weaken SSO enforcement during
the event.

After access returns, run a read-only plan, reconcile SCIM membership, inspect owner/ruleset/bypass
changes, revoke any emergency session, rotate credentials exposed during handling, and restore the
freeze only after security approval.

## Success and evidence

Success requires normal SSO for two test identities, expected SCIM/team convergence, unchanged
organization owners and protected rulesets, continuous audit evidence, and revoked emergency
access. Record measured RPO/RTO against the drill objectives, failures, corrective actions, exact
source SHAs, the next drill date, and immutable evidence URIs using report schema v2. A drill is not
qualified until the shared DR evidence workflow accepts that report in scratch or staging.
