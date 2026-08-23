<!-- mindclade-doc: operations@1 -->

# Terraform module release governance

`github-config` owns the protected GitHub environment used by the monorepo's Terraform module
publisher. The monorepo owns release source, exact-tag qualification, manifests, attestations,
and GitHub Release publication. Release-team tag creation remains a separate organization
ruleset authority; this environment cannot create, delete, or move a tag.

## Source contract

`terraform-module-release` is assigned only to `mindclade-internal-monorepo`. It accepts only a
protected branch, waits at least five minutes, requires the Security team, prevents self-review,
and denies administrator bypass through the repository-environment resource. The independently
qualified Release signer and release-tag-creation rule own signed tag creation; GitHub environments
use any-one-reviewer semantics, so adding Release as a second reviewer would not require both teams.
The publisher must therefore use `workflow_dispatch` from protected `main`; a tag-triggered run
cannot satisfy a protected-branch-only environment.

Release preflight uses the selected-repository `mindclade-release-governance-reader` App, not the
caller `GITHUB_TOKEN`, to read immutable-release settings, workflow evidence, repository source,
and organization membership. The monorepo receives only the non-secret
`RELEASE_GOVERNANCE_READER_APP_ID` repository variable from Terraform. Activate the exact
`RELEASE_GOVERNANCE_READER_APP_PRIVATE_KEY` secret manually only in the protected
`terraform-module-release` environment after the App installation and permissions pass connected
audit. The private key must never enter Git, `CI_VARIABLES`, Terraform input, a plan, state, logs,
or artifacts.

## Activation order

1. Qualify an exact signing key and signer identity, and retain the digest-bound evidence named by
   the monorepo release-authority contract.
2. Create and install the release-governance reader App exactly as cataloged, set the App ID
   variable in both selected repositories, and place its private key only in the documented
   repository/protected-environment Actions secrets. Prove that its token can perform every
   required read and that write requests and webhook delivery remain unavailable.
3. Enable immutable releases for the monorepo and retain independent read-back evidence. The
   GitHub Terraform provider does not make that manual setting part of this environment resource.
4. Run the protected `github-config` exact-main plan. Stop on any deletion, replacement, reviewer
   drift, branch-policy drift, or unexpected environment variable or secret.
5. Apply only the reviewed saved plan, then read back the environment: exact Security team ID,
   protected branches only, no self-review, no administrator bypass, and the wait timer.
   Independently prove the exact Release team bypass on the creation-only tag rule and the
   qualified signer identity.
6. Record connected evidence before updating the monorepo release-authority contract from blocked
   to qualified. Source validation alone never authorizes publication.

## Rollback and failure

Before publication, disable or delete a newly created environment only through another reviewed
plan; leaving it present but unused is safer than bypassing review. After an immutable release is
published, do not delete or retarget its tag or replace its assets. Stop consumers on the prior
immutable version and publish a new patch release after correction.
