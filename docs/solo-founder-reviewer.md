<!-- mindclade-doc: how-to@1 -->

# Operate the solo-founder bootstrap reviewer

> **Audience:** Cloud Identity and GitHub governance operators
> **Outcome:** Give the sole founder an expiring, IdP-backed review path without broad standing
> infrastructure or security membership.
> **Risk:** critical—this is a same-human exception, not independent review.

## Fixed scope and deadline

The Cloud Identity security group is
`github-bootstrap-reviewers@mindclade.com`. It projects to the standalone, closed GitHub team
`bootstrap-reviewers`. That team has only `pull` on `bootstrap`, `github-config`, and
`infrastructure-live`; it reviews only `plan`, `bootstrap`, and `bootstrap-recovery-read`.

`plan` is a shared environment used by all three repositories. The founder therefore receives
read-only plan approval across that control-plane surface. The exception does not include
`governance`, production, release, break-glass, repository write, or team administration authority.

The initial exception expires at **2026-11-18 23:59 America/Detroit**. The directory membership may
expire earlier but never later. `robpearc` and `mindclade-founder` are the same human, so approval
between those accounts must never be represented as independent review.

## Preconditions

- The three records in `catalog/access-exceptions.yaml` are approved and unexpired.
- The bootstrap change enabling `cloudidentity.googleapis.com` on `mc-b-cicd-fb7649` has passed a
  protected plan and protected apply. API enablement selects a quota consumer only; it grants no
  Cloud Identity directory authority.
- The operator is a qualified directory administrator and has verified that
  `robpearc@mindclade.com` has the custom schema value `github.login=robpearc`.
- No local or direct Terraform apply is used. Every generated membership change is reviewed and
  applied from the exact protected `main` revision.

## Initial cutover

1. Set the quota project and verify the directory identity without changing it:

   ```sh
   export IDP_CUSTOMER_ID='<verified Cloud Identity customer ID>'
   export IDP_BILLING_PROJECT=mc-b-cicd-fb7649
   gcloud identity users describe robpearc@mindclade.com \
     --billing-project="${IDP_BILLING_PROJECT}" \
     --format='value(customSchemas.github.login)'
   ```

   Stop unless the output is exactly `robpearc`.

2. Create a Cloud Identity **security** group with no permanent owner:

   ```sh
   gcloud identity groups create github-bootstrap-reviewers@mindclade.com \
     --organization=mindclade.com \
     --group-type=security \
     --display-name='GitHub bootstrap reviewers' \
     --description='Expiring IdP source for the solo-founder bootstrap reviewer exception.' \
     --with-initial-owner=empty \
     --billing-project="${IDP_BILLING_PROJECT}"
   ```

   If the group already exists, describe and verify its immutable name and security-group label;
   do not recreate or substitute another address.

3. Add only the `MEMBER` role with an expiration duration that ends no later than the fixed
   deadline. When executed on 2026-08-20, `90d` ends before 23:59 America/Detroit:

   ```sh
   gcloud identity groups memberships add \
     --group-email=github-bootstrap-reviewers@mindclade.com \
     --member-email=robpearc@mindclade.com \
     --roles=MEMBER \
     --expiration=90d \
     --billing-project="${IDP_BILLING_PROJECT}"
   ```

   If cutover occurs after 2026-08-20, shorten the duration so the membership ends no later than
   2026-11-18 23:59 America/Detroit. Stop if the Workspace edition or Cloud Identity API cannot
   enforce membership expiration. Do not grant `OWNER` or `MANAGER`.

4. Generate the complete IdP projection. Never hand-edit `idp/team-members.json`:

   ```sh
   nix develop .#ci --command python3 scripts/export-idp-groups.py \
     --customer-id="${IDP_CUSTOMER_ID}" \
     --billing-project="${IDP_BILLING_PROJECT}" \
     --apply
   ```

   Confirm the generated entry is exactly `robpearc` as a member of `bootstrap-reviewers`, review
   every other membership delta, and open a pull request containing the generated file.

5. Merge that generated-file pull request through normal protections. Approve and run the
   post-merge `governance` apply only from its exact reviewed `main` SHA.

6. Verify in GitHub that `bootstrap-reviewers` is closed and standalone, has only read access to
   the three declared repositories, and appears only on the three declared environments. Exercise
   a protected no-op plan and a `bootstrap-recovery-read` drill before removing old access.

7. After verification, remove only the temporary direct team memberships that this control
   replaces:

   ```sh
   gh api --method DELETE /orgs/mindclade/teams/infrastructure/memberships/robpearc
   gh api --method DELETE /orgs/mindclade/teams/security/memberships/robpearc
   ```

   Re-run the IdP export in print mode and confirm neither broader team is restored. Preserve the
   directory audit event, generated diff, protected plan/apply run, environment approval evidence,
   recovery drill, and membership removals in the exception issue.

## Renewal or revocation

The nightly expiry job opens or updates one issue at T-14. At **T-3**, the operator must either
complete a protected renewal or revoke the membership; there is no automatic renewal.

For renewal, obtain explicit approval for a new exception record and a new deadline no more than
90 days away. Merge that record first, then update only the `MEMBER` expiration with a duration that
does not exceed the new deadline:

```sh
gcloud identity groups memberships modify-membership-roles \
  --group-email=github-bootstrap-reviewers@mindclade.com \
  --member-email=robpearc@mindclade.com \
  --update-roles-params=MEMBER=expiration=<approved-duration> \
  --billing-project=mc-b-cicd-fb7649
```

If renewal is not approved by T-3, revoke immediately:

```sh
gcloud identity groups memberships delete \
  --group-email=github-bootstrap-reviewers@mindclade.com \
  --member-email=robpearc@mindclade.com \
  --billing-project=mc-b-cicd-fb7649
```

After either operation, regenerate `idp/team-members.json`, review its entire diff, and use the
protected GitHub plan/apply path. For revocation, also remove the expired catalog exception records.

## Independent closeout

When a qualified second human becomes available, they must independently review the original
source diffs, exact protected plans, apply summaries, directory and GitHub audit evidence, and
recovery drill. Record findings and remediation in the exception issue. Their review does not
retroactively make same-human approvals independent; it closes the documented exception.
