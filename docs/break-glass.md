<!-- mindclade-doc: runbook@1 -->

# GitHub governance blocks an emergency change

> **Use when:** a declared incident cannot proceed through an available ordinary governance path.
> **Impact:** a narrow bypass can change organization-wide governance and repository protection.
> **Primary owner:** incident commander with security and GitHub enterprise operators.
> **Escalate:** when no declared bypass exists, audit evidence is unavailable, or scope expands.

## Symptoms

- a critical recovery pull request cannot satisfy a ruleset in the required incident window;
- a protected governance apply is blocked while customer or platform recovery is waiting; or
- ordinary GitHub access paths are unavailable during a confirmed incident.

## Impact and stop conditions

This procedure can change organization-wide governance. Stop if there is no declared
incident, no incident commander, no second qualified reviewer, or no way to preserve GitHub
audit evidence. A failing baseline, tag-protection, or blocked-file push rule is not bypassable
by design; fix the proposed change or the rule through the reviewed path.

## Diagnose

1. Record the incident identifier, affected repository and rule, recovery objective, operator,
   reviewer, and start time.
2. Confirm whether the blocking ruleset actually declares a bypass actor in
   `modules/rulesets/bypass.tf` and the corresponding ruleset resource.
3. Confirm that the emergency change is represented by a pull request. Declared bypasses use
   `pull_request` mode; they are not general direct-push authority.
4. Determine whether protected-environment approval, a ruleset, identity synchronization, or
   GitHub availability is the actual blocker.

## Mitigate

1. Activate the approved, time-bounded emergency membership for the minimum eligible team.
   The secret `incident-command` team is the general incident-response actor; security-only
   bypasses remain separate.
   GitHub does not retain secret teams as protected-environment reviewers, even when they have
   repository read access. The closed `security` team is therefore the enforced `break-glass`
   environment reviewer, while `incident-command` stays secret with read-only access for incident
   coordination. GitHub required-reviewer lists are any-one-of, so listing both teams would not
   create a two-approval quorum.
2. Reauthenticate with phishing-resistant MFA.
3. Use the existing recovery pull request and request only the declared bypass for the
   specific blocking rule.
4. Preserve the pull request, approvals, workflow run, audit-log events, and incident record.
5. If a Terraform governance apply is required, use the protected workflow. Do not copy App
   keys, cloud credentials, state, or saved plans to a workstation.

## Verify recovery

- The emergency change is visible in Git history and the audit log.
- Required service or governance behavior is restored.
- `main` expresses the intended resting policy.
- `nix develop --command make validate` passes on the recovery state.
- Drift detection reports no unexplained change.

## Revoke, escalate, and follow up

1. Remove temporary emergency membership and confirm the team no longer appears in the
   operator's effective grants.
2. Close or expire any associated access exception.
3. Reconcile any necessary policy change in `catalog/` and apply it through the normal path.
4. Attach the evidence timeline to the incident and conduct a post-incident review.
5. Create prevention work for the condition that required bypass.

Never weaken the no-bypass baseline, tag-protection, or blocked-file push controls as an
incident shortcut.
