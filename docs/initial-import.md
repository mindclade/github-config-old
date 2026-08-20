<!-- mindclade-doc: how-to@1 -->

# Import and activate the GitHub configuration repository

> **Audience:** Security and platform bootstrap operators
> **Outcome:** Import this tree without losing history, validate it offline, and activate
> governance only after its dependencies and negative authorization tests are qualified.

## Prerequisites

- the existing `mindclade/github-config` repository and its `.git` history;
- the `.github` repository's protected `v3.0.0` workflow-contract tag, which is the
  full-semver baseline referenced by `catalog/rulesets.yaml`;
- completed Ring-0 bootstrap state and GitHub-to-Google Cloud federation;
- plan and apply GitHub Apps with distinct minimum permissions;
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
6. Open a pull request and inspect the speculative plan. Unexpected deletion, replacement,
   ownership, or visibility change is a stop condition.

## Activate

1. Qualify the plan identity: it can read governed state and create plans but cannot mutate
   GitHub resources.
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
- required workflow rules reference the immutable `v3.0.0` release;
- negative tests prove the plan identity cannot mutate and the apply identity cannot skip the
  protected environment; and
- drift detection reports no unexplained changes.

The platform import order is `.github`, `bootstrap`, `github-config`,
`infrastructure-live`, then `gitops`.
