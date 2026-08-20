# Offboarding

Revocation checklist with a timed SLA. Work top to bottom — the order is by how much damage
the credential can do, not by convenience.

## SLA

| Departure | Complete within |
|---|---|
| Involuntary, or any security concern | **1 hour**, starting before the conversation |
| Voluntary, notice served | End of last working day |
| Contractor engagement ends | End of final day |
| Extended leave | Suspend, do not delete |

The clock starts at the decision, not at the last day. For an involuntary departure, steps 1
and 2 happen *before* the person is told.

## Immediate — the IdP does most of it

**1. Disable the IdP account.** One action, and it cascades: SAML sessions die, SCIM
deprovisions the GitHub account, org membership drops, team membership drops with it.

**2. Revoke active sessions and tokens.** Deprovisioning does not kill what is already
issued.

```sh
gh api -X GET "/orgs/mindclade/credential-authorizations" \
  --jq '.[] | select(.login=="LOGIN") | {id, credential_type, credential_accessed_at}'

gh api -X DELETE "/orgs/mindclade/credential-authorizations/CREDENTIAL_ID"
```

That covers PATs and SSH keys authorised against the org. A PAT that was never SAML-authorised
already cannot reach org resources.

**3. Confirm the GitHub account is gone from the org.**

```sh
gh api "/orgs/mindclade/members/LOGIN" --silent && echo "STILL A MEMBER" || echo "removed"
```

## Within the hour, if they held elevated access

Skip any that do not apply. Check `access-model.md` if unsure what they held.

**4. Enterprise owner.** Follow `docs/break-glass.md` and the enterprise owner recovery procedure. Add the approved replacement before removing the departing owner so at least two independent recovery owners remain. Enterprise-owner membership is intentionally not changed by the ordinary organization Terraform apply.

**5. Break-glass.** Rotate the credential itself, not just their access to it. Procedure in
`bootstrap/docs/break-glass.md`. Anyone who has ever used it has seen it.

**6. GCP.** Check for standing bindings and any service account keys they created:

```sh
gcloud organizations get-iam-policy "$ORG_ID" \
  --flatten="bindings[].members" --filter="bindings.members:LOGIN" \
  --format="table(bindings.role)"
```

Key creation is blocked org-wide by policy, so this should be empty. Investigate anything
that is not, because it means the policy has a gap.

**7. Shared credentials they could read.** Anything in Secret Manager they had access to is
compromised in the sense that matters: you cannot prove they did not copy it. Rotate rather
than reason about it. `bootstrap/docs/credential-rotation.md`.

## Within the day

**8. Reassign ownership.** Any repo whose `owner-team` was effectively them, any open PR
worth keeping, any on-call slot.

**9. Remove from the rota.** PagerDuty, the incident channel, the escalation list. A page
routed to a departed engineer is a page nobody answers.

**10. Transfer or archive personal forks** holding org code.

**11. Check the audit log** for the notice period. Not accusatory — a bulk clone the week
before leaving is worth knowing about either way.

```sh
gh api "/orgs/mindclade/audit-log?phrase=actor:LOGIN&per_page=100" \
  --jq '.[] | {action, created_at, repo}'
```

## Within the week

**12. Update the IdP group membership export** and confirm `github-config` applies clean.

**13. Record the revocation.** Who, when, which steps, who performed them. A checklist with
no evidence it was followed is not a control.

## Verification

Run this after finishing. Every line should report removed or empty.

```sh
LOGIN=departing-user

gh api "/orgs/mindclade/members/${LOGIN}" --silent 2>/dev/null \
  && echo "FAIL: still an org member" || echo "ok: not a member"

gh api "/orgs/mindclade/credential-authorizations" \
  --jq "[.[] | select(.login==\"${LOGIN}\")] | length" \
  | xargs -I{} sh -c '[ {} -eq 0 ] && echo "ok: no authorised credentials" || echo "FAIL: {} credentials remain"'

gh api "/orgs/mindclade/outside_collaborators" --jq '.[].login' \
  | grep -qx "${LOGIN}" && echo "FAIL: became an outside collaborator" || echo "ok: not a collaborator"
```

That last check catches a specific failure: removing someone from teams while leaving them
as an outside collaborator. It looks like revocation in the members list and is not.

## Extended leave

Suspend, do not delete. Deleting the account breaks commit attribution and orphans review
history. Suspend in the IdP, remove from the on-call rota, leave everything else alone.
