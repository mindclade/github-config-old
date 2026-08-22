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

## Source qualification versus activation

`membership.tf` guards the read with `fileexists()`, so a missing file yields no members and
offline `terraform validate` still works. That supports source/bootstrap validation only. The
production workflow runs `scripts/validate-adoption-plan.py --activation`, which fails when this
file is absent, contains no organization members, omits a catalog team, or when any directory-group
mapping remains deferred.

It also means **an empty file is indistinguishable from an outage**, which is why the export
script refuses to write a document with zero org members. Writing one would remove every
member on the next apply.

The `legal`, `platform`, and `security` groups are independent approval functions. After all
three directory mappings are verified, the exporter rejects an empty group or any GitHub login
that occurs in more than one of those groups. This makes the three-approval legal-path ruleset a
separation-of-duties control rather than three labels satisfied by one person.

## Which group feeds which team

`mappings.yaml` is the only source for verified directory addresses. The export script derives its
mapped and deferred sets from that document; catalog validation fails if a team is missing, appears
in both states, carries an address while deferred, or uses an address different from the verified
contract.

The currently verified projections are `biosecurity`, `bootstrap-reviewers`, `data-platform`,
`engineering`, `platform`, `research`, and `security`. The dedicated reviewer projection is
`github-bootstrap-reviewers@mindclade.com`; its membership is governed by the expiring
solo-founder procedure in [`docs/solo-founder-reviewer.md`](../docs/solo-founder-reviewer.md).
Directory addresses for `incident-command`, `infrastructure`, `legal`, `model-serving`,
`model-training`, `product`, and `release` have not been verified in source. The exporter warns and omits those teams
rather than deriving privileged group names by convention. Change each entry from `deferred` to
`mapped` and add its exact address in one reviewed change only after a read-only directory inventory
confirms it. No human login belongs in `mappings.yaml`.

Cloud Identity commands must charge quota to the bootstrap CI/CD project:

```sh
IDP_BILLING_PROJECT=mc-b-cicd-fb7649 \
  python3 scripts/export-idp-groups.py --apply
```

The billing project only selects an API quota consumer. It does not grant directory read or write
authority; the operator still needs the appropriate Cloud Identity role.
