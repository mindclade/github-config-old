# `idp/`

`team-members.json` is written only with `python3 scripts/export-idp-groups.py --apply`.
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

`GROUP_FOR_TEAM` in the export script. Every key there must exist in
[`catalog/teams.yaml`](../catalog/teams.yaml) — `membership.tf` has a `check` block that
fails the plan and names the offending team otherwise.
