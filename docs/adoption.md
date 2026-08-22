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
6. `catalog/adoption-inventory.yaml` is `qualified`, has no unresolved discovery classes, and
   every known-existing address is already in state or appears as an exact import in the plan.
7. `idp/mappings.yaml` contains no deferred teams and the generated `idp/team-members.json`
   covers every catalog team with at least one organization member.

## Sequence

1. Initialize the remote backend without applying.
2. Review the immutable IDs in `catalog/adoption-inventory.yaml` against a fresh read-only export.
   Apply only the matching declarative imports in `imports.tf`; never translate a name into an ID
   by convention.
3. Import any other pre-existing teams, environments, rulesets, custom-property definitions, App
   scopes, or variables before enabling the corresponding resources. Use addresses and provider
   import IDs from a speculative plan and the provider documentation; never guess either one. Do
   not add an import for a deferred value merely because an unmanaged variable with that name exists.
4. Run `make validate`, `terraform validate`, and `terraform test`.
5. Generate a full speculative plan and state-address list, then run the adoption gate:

   ```sh
   terraform state list > state-list.txt
   terraform plan -out=github-config.tfplan
   terraform show -json github-config.tfplan > plan.json
   python3 scripts/validate-adoption-plan.py --plan-json plan.json --state-list state-list.txt
   ```

   The gate rejects any known-existing object that would be created rather than imported and any
   destructive action without an explicit reviewed override.
6. Resolve unexpected differences in the catalog or import state. Do not use lifecycle ignores to
   hide governance drift.
7. Merge through the protected branch. The post-merge workflow creates a new plan for the exact
   `main` SHA; reviewers inspect that artifact before approving the `governance` environment.
8. Before approval, run the same gate with `--activation`. It deliberately remains closed while
   the inventory says `blocked`, a discovery class is unresolved, an IdP mapping is deferred, or
   `team-members.json` is unavailable.
9. After apply, run `make connected-audit` and compare its machine-readable evidence with the plan
   summary. A denied endpoint is an evidence failure.

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
terraform show -json /tmp/github-config-adoption.tfplan > /tmp/github-config-adoption.plan.json
terraform state list > /tmp/github-config-adoption.state-list.txt
python3 scripts/validate-adoption-plan.py \
  --plan-json /tmp/github-config-adoption.plan.json \
  --state-list /tmp/github-config-adoption.state-list.txt \
  --activation
terraform apply /tmp/github-config-adoption.tfplan
unset GITHUB_TOKEN
```

The JSON plan and state-address files must be produced from the same saved plan and backend
immediately before the gate. The token must remain process-environment input only: never write it to Terraform variables,
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
`env:ENVIRONMENT_PROJECT_IDS`. Export the exact clean, applied infrastructure handoff outside both
repositories, then run the full exporter with it:

```sh
python3 scripts/export-ci-variables.py \
  --stage full \
  --bootstrap ../bootstrap \
  --applied-handoff /protected/evidence/infrastructure-control-plane-handoff.json
```

The exporter requires handoff contract `1.2.0`, an exact 22-variable inventory, a full immutable
source commit, and an explicit assertion that credential material is absent. Bootstrap supplies
`PRODUCTION_QUALIFICATION_IDENTITY_JSON` directly from `platform_contract`; an operator cannot
substitute it. Supply only exact applied values for remaining non-handoff `env:` inputs and reapply
`github-config`. Full mode remains fail-closed on every unresolved normal-plane input.

The same export requires bootstrap `platform_contract` version `1.4.0`, reads
`state.replica_buckets.bootstrap`, and publishes it as the managed
`bootstrap/TFSTATE_REPLICA_BUCKET` Actions variable. The protected
`bootstrap-recovery-read` environment is catalog-managed; never allow the recovery workflow to
auto-create an unprotected environment with that name.

The exporter requires `platform_contract.buildkite` to remain disabled with null pool/provider
and the matching catalog flag. Buildkite cannot be re-enabled through an operator input. It also
validates all six capability-specific ARC providers, collision-resistant mapped principals,
trusted-main caller, immutable v4 canary/build/attestation/signing workflows, and the isolated v5
qualification-reader and promotion workflows before publishing any release variable.
It also validates the exact eight-principal DR evidence provider and compiles the applied writer,
project, and bucket outputs into environment variables on only the protected `scratch` and
`staging` environments of `bootstrap`, `github-config`, `infrastructure-live`, and `gitops`.

The ARC catalog is desired-state and preflight evidence, not proof of a live GitHub App
installation. Before enabling the canary provider, create or verify both exact installations:

- `mindclade-arc`: selected to `mindclade-internal-monorepo`, organization
  self-hosted-runners write, repository Actions/metadata read;
- `mindclade-release-promoter`: selected to `gitops`, repository contents/pull-requests write
  and metadata read.

Apply and verify runner group `mindclade-arc-artifact-authority` as private/selected, with only
the monorepo and only its `release.yml@refs/heads/main` workflow. Record the live IDs and
effective permissions as connected evidence. Do not infer installation from the catalog or add
broader App scopes to make a failed canary pass.

The Terraform plan/apply Apps follow the separate exact contract in
[`github-apps.md`](github-apps.md). In particular, the plan App's organization-ruleset read requires
an organization-administration write permission at the GitHub API boundary; do not describe that
token as read-only or expose it outside the protected plan workflow.

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

If an adoption plan is wrong before apply, discard the saved plan and correct the inventory/import
address. After apply, suspend the apply App installation to stop further mutation, preserve the
plan/evidence artifacts, submit a corrective catalog change, and produce a new reviewed plan. Do
not remove an import block, manually delete a live object, or restore an older state snapshot merely
to make Terraform agree.
