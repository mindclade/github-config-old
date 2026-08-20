<!-- mindclade-doc: how-to@1 -->

# Onboard an engineer to Mindclade GitHub

> **Audience:** Identity and security operators
> **Outcome:** Provision least-privilege GitHub access through the corporate identity path and
> verify the resulting team grants.
> **Risk:** high—incorrect group assignment can grant protected control-plane authority.

## Prerequisites

- an approved onboarding request with manager, role, and start date;
- access to the corporate identity provider's group-management workflow; and
- a separate qualified reviewer for elevated security, platform, infrastructure, release, or
  production-control access.

Do not grant repository access directly to an individual. Ordinary access originates in the
identity provider and is mapped to catalog-managed GitHub teams.

## Procedure

1. Create or activate the corporate identity according to the identity-provider procedure.
2. Require phishing-resistant MFA and register only approved recovery factors.
3. Assign the minimum approved IdP groups for the engineer's role.
4. Wait for enterprise membership and team synchronization to complete.
5. Compare the resulting teams with `catalog/teams.yaml` and grants with
   `catalog/access.yaml`.
6. Obtain separate approval before assigning any group that maps to `security`,
   `infrastructure`, `platform`, `release`, `incident-command`, or `biosecurity` authority.
7. Ask the engineer to clone only a repository they are expected to access:

   ```sh
   gh auth status
   gh repo clone mindclade/mindclade-internal-monorepo
   ```

## Verify

- GitHub Enterprise membership is active.
- Expected teams appear; unexpected teams do not.
- A normal engineer can read the monorepo but cannot administer it.
- Membership in `engineering` alone does not grant access to `bootstrap` or `github-config`.
- Protected-environment approval is absent unless separately authorized.

Record the verification in the onboarding request. If synchronization grants more access
than approved, remove the upstream IdP group, treat the excess grant as a security event, and
do not mask it with a manual GitHub edit.

## Roll back or recover

Remove the incorrect upstream IdP group and let managed synchronization revoke the derived GitHub
team membership. Confirm effective access is gone and preserve the request, group delta, sync event,
and repository access check. Escalate excess privileged access as a security incident.

## Related documentation

- [Access model](access-model.md)
- [Offboarding](offboarding.md)
- [GitHub break-glass](break-glass.md)
