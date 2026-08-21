# `idp/`

`team-members.json` is written only with `python3 scripts/export-idp-groups.py --apply`
and read by [`modules/teams/membership.tf`](../modules/teams/membership.tf). It is the only
source of organization and team membership.

**Do not edit it by hand.** The next sync overwrites the file, and the overwrite looks like
someone's access being revoked for no reason. Change the group in the IdP instead.

## Shape

```json
{
  "org_members":  [{ "username": "alice", "role": "member" }],
  "team_members": { "platform": [{ "username": "alice", "role": "maintainer" }] }
}
```

`username` is the **GitHub login**, not the directory address. The mapping comes from the
`github.login` custom schema attribute the IdP sets during SCIM provisioning — a user without
it is omitted from the export and warned about, rather than guessed at from the local part of
their email.

## Absence is valid

`membership.tf` guards the read with `fileexists()`, so a missing file yields no members and
`terraform validate` still works. That is deliberate: requiring the export to exist before the
repository can be initialised is a bootstrap ordering problem nobody needs.

It also means **an empty file is indistinguishable from an outage**, which is why the export
script refuses to write a document with zero org members. Writing one would remove every
member on the next apply.

## Which group feeds which team

`TEAM_GROUPS` in the export script contains only verified directory addresses. Every catalog
team is either in that map or in the explicit `DEFERRED_TEAMS` set; catalog validation fails if
a team is missing from both, appears in both, or uses the stale `data` key instead of
`data-platform`.

The currently verified projections are `biosecurity`, `bootstrap-reviewers`, `data-platform`,
`engineering`, `platform`, `research`, and `security`. The dedicated reviewer projection is
`github-bootstrap-reviewers@mindclade.com`; its membership is governed by the expiring
solo-founder procedure in [`docs/solo-founder-reviewer.md`](../docs/solo-founder-reviewer.md).
Directory addresses for `incident-command`, `infrastructure`, `model-serving`, `model-training`,
`product`, and `release` have not been verified in source. The exporter warns and omits those teams
rather than deriving privileged group names by convention. Add each real address to `TEAM_GROUPS`
and remove the same key from `DEFERRED_TEAMS` in one reviewed change after a read-only directory
inventory confirms it.

Cloud Identity commands must charge quota to the bootstrap CI/CD project:

```sh
IDP_BILLING_PROJECT=mc-b-cicd-fb7649 \
  python3 scripts/export-idp-groups.py --apply
```

The billing project only selects an API quota consumer. It does not grant directory read or write
authority; the operator still needs the appropriate Cloud Identity role.
