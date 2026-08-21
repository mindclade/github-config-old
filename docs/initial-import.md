<!-- mindclade-doc: how-to@1 -->

# Import and activate the GitHub configuration repository

> **Audience:** Security and platform bootstrap operators
> **Outcome:** Import this tree without losing history, validate it offline, and activate
> governance only after its dependencies and negative authorization tests are qualified.
> **Risk:** critical—the first apply can alter organization-wide repositories, access, and rules.

## Prerequisites

- the existing `mindclade/github-config` repository and its `.git` history;
- the `.github` repository's protected `v4.0.0` workflow-contract tag, which is the
  full-semver baseline referenced by `catalog/rulesets.yaml`;
- completed Ring-0 bootstrap state and GitHub-to-Google Cloud federation;
- plan and apply GitHub Apps with distinct minimum permissions, or the approved one-time founder
  OAuth adoption exception documented in [adoption](adoption.md), with exact permissions from
  [GitHub App authority contracts](github-apps.md);
- `plan` and `governance` protected environments; and
- approved non-secret variables and protected secrets required by the workflows.

Do not activate `apply.yml` until the plan and apply identities have passed positive and
negative authorization tests.

## Import

1. Back up the existing repository and record the current default-branch commit.
2. Copy this tree into the existing checkout while preserving `.git` and excluding local
   state, plans, credentials, `.account.env`, and Terraform cache directories.
3. Review the complete diff before committing. Confirm that `main` remains the default branch.
4. Enter the pinned shell and validate:

   ```sh
   nix develop --command make validate
   terraform init -input=false -backend=false
   terraform validate -no-color
   terraform test -no-color
   ```

5. Compare repository inventory, teams, environments, and rulesets in `catalog/` with the
   target organization. Follow [adoption](adoption.md) for resources that must be imported
   rather than created.
6. Confirm the declarative imports cover the existing `.github-private` repository plus every
   pre-existing Actions variable and environment that the staged payload will manage. Existing
   deferred variables are not authority for unavailable outputs and must not be imported under
   placeholder values.
7. Compile the initial payload with `export-ci-variables.py --stage bootstrap` as documented in
   [adoption](adoption.md). Use the current verified billing and security recipients and an empty
   environment-project map; do not invent normal-plane project IDs, App IDs, attestors, or
   retired Buildkite inputs.
8. Open a pull request and inspect the speculative plan. Unexpected deletion, replacement,
   ownership, or visibility change is a stop condition.
9. Run `scripts/validate-adoption-plan.py` with the plan JSON and state list. Production activation
   additionally requires `--activation`; do not bypass its connected-state or IdP blockers.

If the Apps do not exist yet, follow the one-time local founder OAuth procedure in
[adoption](adoption.md). Keep the token only in `GITHUB_TOKEN`, apply only the saved reviewed plan,
record an expiry, and add the founder manually only to required reviewer teams after Terraform has
created them. Normal operation becomes App-only as soon as the distinct Apps are installed and
qualified.

## Activate

1. Qualify the plan path: its workflow performs no GitHub mutation, and a negative test proves
   that boundary. The App token itself is not read-only because GitHub requires organization
   Administration write even for organization-ruleset reads; see `catalog/control-plane-apps.yaml`.
2. Qualify the apply identity: it is available only after the protected `governance`
   environment and cannot use the plan App's secret.
3. Merge the reviewed pull request.
4. Confirm `apply.yml` plans the exact merged commit, uploads a checksummed one-day artifact,
   and waits at the `governance` environment.
5. Approve and observe the first apply. Do not bypass a destructive-plan failure; reconcile
   the catalog or deliberately follow the reviewed manual dispatch path.

## Verify

- the applied commit matches `main`;
- plan metadata names the same repository and commit as the apply checkout;
- managed repositories have the expected custom properties and visibility;
- every managed repository issues an immutable default OIDC subject containing its owner and
  repository IDs, and a mismatched repository ID fails WIF token exchange;
- required workflow rules reference the immutable `v4.0.0` release;
- negative tests prove the plan workflow does not invoke mutation and the apply identity cannot
  skip the protected environment; and
- drift detection reports no unexplained changes; and
- `scripts/audit-connected-governance.py` can read every required endpoint and reports exact App,
  ruleset, runner-group, environment, Actions, repository, team, and custom-property parity.

The platform import order is `.github`, `bootstrap`, `github-config`,
`infrastructure-live`, then `gitops`.

## Roll back or recover

Before the first governance apply, close the pull request or revert the import commit. After apply,
use a reviewed catalog correction and protected exact plan; do not restore GitHub objects with
manual edits that drift from `main`. If governance blocks incident recovery, follow
[GitHub break-glass](break-glass.md) and reconcile the resting policy immediately afterward.
