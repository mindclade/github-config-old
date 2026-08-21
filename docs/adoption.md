# Adopting an Existing GitHub Enterprise Organization

This repository manages an existing organization without recreating or silently overwriting it.
Adoption is a reviewed migration, not an ordinary first apply.

## Preconditions

1. The `catalog/` inventory exactly matches the repositories, teams, environments, and rules that
   should remain authoritative.
2. The plan and apply GitHub Apps are installed with their documented least-privilege permissions,
   or the explicitly approved one-time founder OAuth adoption path below is being used before those
   Apps exist.
3. `bootstrap` has created the state bucket, WIF provider, and distinct plan/apply identities.
4. Mandatory workflows referenced by `catalog/rulesets.yaml` exist in repository
   `mindclade/.github`, under `.github/workflows/`, at the pinned release tag before any ruleset
   is activated.
5. A current organization and repository settings export has been retained as recovery evidence.

## Sequence

1. Initialize the remote backend without applying.
2. Apply only the declarative imports already present in `imports.tf` for the organization, all
   seven repository records (including `.github-private`), and the read-only API-inventoried
   bootstrap variables and repository environments.
3. Import any other pre-existing teams, environments, rulesets, custom-property definitions, App
   scopes, or variables before enabling the corresponding resources. Use addresses and provider
   import IDs from a speculative plan and the provider documentation; never guess either one. Do
   not add an import for a deferred value merely because an unmanaged variable with that name exists.
4. Run `make validate`, `terraform validate`, and `terraform test`.
5. Generate a full speculative plan and classify every create, update, replacement, and deletion.
6. Resolve unexpected differences in the catalog or import state. Do not use lifecycle ignores to
   hide governance drift.
7. Merge through the protected branch. The post-merge workflow creates a new plan for the exact
   `main` SHA; reviewers inspect that artifact before approving the `governance` environment.
8. After apply, run drift detection and compare GitHub audit evidence with the plan summary.

## One-time founder OAuth adoption

Before the plan/apply Apps exist, a founder who is already an organization owner may perform the
initial import and exact reviewed apply locally. Record the operator, justification, start time,
expiry, reviewed plan digest, and post-change reviewer in the adoption change record. This is a
bootstrap exception, not an alternate steady-state credential path.

```sh
gh auth status
export GITHUB_TOKEN="$(gh auth token)"
terraform plan -out=/tmp/github-config-adoption.tfplan
terraform show -no-color /tmp/github-config-adoption.tfplan
terraform apply /tmp/github-config-adoption.tfplan
unset GITHUB_TOKEN
```

The token must remain process-environment input only: never write it to Terraform variables,
backend configuration, a plan filename, shell tracing, CI, or Git. Stop if `gh auth status` does not
identify the approved founder account or the plan contains an unreviewed delete/replacement.

After Terraform creates the teams, use the dedicated IdP-backed `bootstrap-reviewers` team for the
solo-founder bootstrap exception. Do not make the founder a standing member of the broader
`infrastructure` or `security` teams, grant direct repository access, or grant team `admin`. Follow
[`solo-founder-reviewer.md`](solo-founder-reviewer.md) to create the expiring Cloud Identity
membership, generate the membership projection, apply the exact reviewed plan, and remove any
temporary manual reviewer-team memberships only after cutover is verified. Install and qualify the
distinct Apps, then use App tokens exclusively for normal plan/apply operation.

For the initial governance plan, compile only values that already have an authoritative source:

```sh
export BILLING_EMAIL=founder@mindclade.com
export SECURITY_CONTACT=robpearc@mindclade.com
export BREAK_GLASS_PRINCIPALS_JSON="$(gh variable get BREAK_GLASS_PRINCIPALS_JSON --repo mindclade/bootstrap)"
python3 scripts/export-ci-variables.py --stage bootstrap --bootstrap ../bootstrap > /tmp/github-config-ci-variables.json
export TF_VAR_ci_variables="$(jq -c . /tmp/github-config-ci-variables.json)"
export TF_VAR_environment_project_ids='{}'
```

Use that exact output for the reviewed local plan/apply and, when ready to activate CI, set the
self-hosting `CI_VARIABLES` repository variable with the same exporter command plus `--set`. The
bootstrap stage deliberately omits unavailable GitHub App IDs, retired Buildkite inputs,
normal-plane identities, environment projects, and attestors. It uses `ENVIRONMENT_PROJECT_IDS={}`,
which creates and protects environments but omits every environment-level `GCP_PROJECT_ID`.
Terraform accepts only this empty initial handoff or a complete map for all project-required
environments; a partial map fails.

The current live `SECURITY_CONTACT` and organization billing email remain explicit operator inputs
until their IdP-backed group mailboxes exist. Do not substitute `security@mindclade.com` or
`billing@mindclade.com` before those addresses are provisioned and verified.

After `infrastructure-live` creates normal-plane GitOps service accounts, exact environment
projects, and supply-chain attestors, change `ENVIRONMENT_PROJECT_IDS` to
`env:ENVIRONMENT_PROJECT_IDS`, supply only exact applied outputs for every remaining `env:` input,
run the default full exporter, and reapply `github-config`. Full mode remains fail-closed on every
unresolved normal-plane input.

The same export requires bootstrap `platform_contract` version `1.3.0`, reads
`state.replica_buckets.bootstrap`, and publishes it as the managed
`bootstrap/TFSTATE_REPLICA_BUCKET` Actions variable. The protected
`bootstrap-recovery-read` environment is catalog-managed; never allow the recovery workflow to
auto-create an unprotected environment with that name.

The exporter requires `platform_contract.buildkite` to remain disabled with null pool/provider
and the matching catalog flag. Buildkite cannot be re-enabled through an operator input. It also
validates all six capability-specific ARC providers, collision-resistant mapped principals,
trusted-main caller, and immutable v4 reusable workflows before publishing any release variable.

`BOOTSTRAP_FOLDER_ID` is an adopt-existing bootstrap input, not an output handoff. The exporter
never publishes it. Keep the bootstrap repository variable absent while Terraform owns the folder;
a non-empty value switches bootstrap into adoption mode and would plan destruction of the managed
folder (blocked by `prevent_destroy`).

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
