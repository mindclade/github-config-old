# Adopting an Existing GitHub Enterprise Organization

This repository manages an existing organization without recreating or silently overwriting it.
Adoption is a reviewed migration, not an ordinary first apply.

## Preconditions

1. The `catalog/` inventory exactly matches the repositories, teams, environments, and rules that
   should remain authoritative.
2. The plan and apply GitHub Apps are installed with their documented least-privilege permissions.
3. `bootstrap` has created the state bucket, WIF provider, and distinct plan/apply identities.
4. Mandatory workflows referenced by `catalog/rulesets.yaml` exist in `mindclade/.github` at the
   pinned release tag before any ruleset is activated.
5. A current organization and repository settings export has been retained as recovery evidence.

## Sequence

1. Initialize the remote backend without applying.
2. Apply only the declarative imports already present in `imports.tf` for the organization and six
   repository records.
3. Import any pre-existing teams, environments, rulesets, custom-property definitions, App scopes,
   or variables before enabling the corresponding resources. Use addresses from a speculative plan;
   never guess an import address or identifier.
4. Run `make validate`, `terraform validate`, and `terraform test`.
5. Generate a full speculative plan and classify every create, update, replacement, and deletion.
6. Resolve unexpected differences in the catalog or import state. Do not use lifecycle ignores to
   hide governance drift.
7. Merge through the protected branch. The post-merge workflow creates a new plan for the exact
   `main` SHA; reviewers inspect that artifact before approving the `governance` environment.
8. After apply, run drift detection and compare GitHub audit evidence with the plan summary.

## Import safety

- Do not import a resource into two Terraform addresses.
- Do not import credentials, GitHub App private keys, webhook secrets, or enterprise-owner tokens.
- Do not temporarily weaken branch/ruleset protection merely to make adoption easier.
- If a provider resource cannot manage an enterprise control reliably, keep it in
  `docs/enterprise-manual-controls.md` rather than asserting false declarative ownership.

## Rollback

Terraform state rollback is not the first response to a bad governance apply. Prefer an immediate
corrective catalog commit and reviewed apply. Restore a prior state object only when state itself is
incorrect or damaged, and always inspect a new plan before mutation.
