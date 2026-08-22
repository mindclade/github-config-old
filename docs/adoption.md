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
   The 2026-08-22 refresh added every observed desired repository environment to `imports.tf`.
   Auto-created `copilot` environments have an explicit platform-managed disposition in
   `catalog/connected-resource-exceptions.yaml`; Terraform must neither import nor delete them.
   The connected audit accepts only the exact five-repository inventory and requires every such
   environment to contain zero secrets, variables, reviewers, timers, or custom protection rules.
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
   `catalog/governance-activation.yaml` is an additional stop: release-dependent rules cannot
   become active until their exact published release, contexts, native evidence, independent
   reviewers, import plan, and connected audit are all qualified.
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

The exporter requires a full immutable source commit and an explicit assertion that credential
material is absent. Bootstrap contracts `1.2.0` and `1.4.0` consume applied handoff `1.3.0` with
its exact 25-variable production-eligibility inventory. Bootstrap contract `1.5.0` instead
requires applied handoff `1.4.0`, whose exact 28-variable inventory is the `1.3.0` contract plus
`WIF_PROVIDER_BAZEL_CACHE`, `SA_BAZEL_CACHE_READER`, and `SA_BAZEL_CACHE_WRITER`. Versions are not
interchangeable and stale, partial, or extra fields fail before GitHub can be changed.

Bootstrap supplies `PRODUCTION_QUALIFICATION_IDENTITY_JSON` and, under contract `1.5.0`,
`BAZEL_CACHE_IDENTITY_JSON` directly from `platform_contract`; an operator cannot substitute
either value. The cache JSON is only the exact infrastructure source contract. The exporter does
not publish the monorepo provider or its separate reader/writer service accounts until the applied
`1.4.0` handoff matches the bootstrap provider and common-CI account identities. It does not
publish a cache endpoint, enable a client, or claim that the provider, accounts, IAM bindings, or
bucket are live. Supply only exact applied values for remaining non-handoff `env:` inputs and
reapply `github-config`. Full mode remains fail-closed on every unresolved normal-plane input.

### Publish the applied bootstrap account handoff

Bootstrap contract `1.5.0` also makes `BOOTSTRAP_ACCOUNT_HANDOFF_JSON` a derived governance
output. It is not a catalog value and must never be reconstructed in the GitHub UI. The exporter
requires the bootstrap checkout to be clean, records its full commit SHA, hashes the complete
canonical `platform_contract`, validates the versioned schema, and binds the record to the exact
state location, three state buckets, plan identity, and four apply identities already published as
individual `infrastructure-live` variables. Terraform rejects the complete `CI_VARIABLES` payload
if any duplicate differs. The credential-free validator pins the byte-identical version `1` schema
shared with the infrastructure consumer. Bootstrap `1.2.0` and `1.4.0` exports omit the record
entirely.

After the bootstrap apply is complete and its source commit is independently recorded, use this
exact activation sequence. The first mutation updates only the self-hosting compiler input on
`github-config`; the protected plan/apply remains the sole publisher to `infrastructure-live`.

```sh
set -euo pipefail
umask 077

export BOOTSTRAP_APPLIED_SHA='<40-character reviewed bootstrap commit>'
git -C ../bootstrap fetch origin main
git -C ../bootstrap checkout --detach "$BOOTSTRAP_APPLIED_SHA"
test -z "$(git -C ../bootstrap status --porcelain=v1)"
test "$(git -C ../bootstrap rev-parse HEAD)" = "$BOOTSTRAP_APPLIED_SHA"

python3 scripts/export-ci-variables.py \
  --stage full \
  --bootstrap ../bootstrap \
  --applied-handoff /protected/evidence/infrastructure-control-plane-handoff.json \
  > /protected/evidence/github-ci-variables.json
jq -er '."infrastructure-live".BOOTSTRAP_ACCOUNT_HANDOFF_JSON | fromjson |
  .schema_version == 1 and
  .bootstrap_contract_version == "1.5.0" and
  .bootstrap_source_commit == env.BOOTSTRAP_APPLIED_SHA' \
  /protected/evidence/github-ci-variables.json >/dev/null

python3 scripts/export-ci-variables.py \
  --stage full \
  --bootstrap ../bootstrap \
  --applied-handoff /protected/evidence/infrastructure-control-plane-handoff.json \
  --set
python3 scripts/export-ci-variables.py \
  --stage full \
  --bootstrap ../bootstrap \
  --applied-handoff /protected/evidence/infrastructure-control-plane-handoff.json \
  --check

gh workflow run apply.yml --repo mindclade/github-config --ref main \
  -f rollout_phase=normal -f allow_destroy=false
```

Review the saved plan for exactly one new repository Actions variable, approve the `governance`
environment only for that reviewed plan, and wait for apply verification. Then compare the live
value byte-for-byte with the compiled record:

```sh
jq -r '."infrastructure-live".BOOTSTRAP_ACCOUNT_HANDOFF_JSON' \
  /protected/evidence/github-ci-variables.json \
  > /protected/evidence/bootstrap-account-handoff.expected.json
gh variable get BOOTSTRAP_ACCOUNT_HANDOFF_JSON \
  --repo mindclade/infrastructure-live \
  > /protected/evidence/bootstrap-account-handoff.observed.json
cmp /protected/evidence/bootstrap-account-handoff.expected.json \
  /protected/evidence/bootstrap-account-handoff.observed.json
```

Stop before approval if the bootstrap checkout is dirty, the SHA is not the applied revision, the
plan changes any unrelated variable, or the read-back differs. Roll back only by restoring a prior
reviewed compiler payload from its exact clean bootstrap revision and running the same protected
plan/apply path; never edit or delete the downstream variable manually. Retain the compiled record,
plan checksum, apply run, read-back, reviewer, and timestamps in the restricted evidence boundary.

The same export accepts bootstrap `platform_contract` version `1.4.0` or `1.5.0`, reads
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
Under bootstrap `1.5.0`, it additionally validates the dedicated `gh-bazel-cache` provider, exact
immutable monorepo IDs, pull-request read route, and protected main, merge-group, and nightly write
routes before exporting any cache-related value.

The ARC catalog is desired-state and preflight evidence, not proof of a live GitHub App
installation. Before enabling the canary provider, create or verify both exact installations:

- `mindclade-arc`: selected to `mindclade-internal-monorepo`, organization
  self-hosted-runners write, repository Actions/metadata read;
- `mindclade-release-promoter`: selected to `gitops`, repository contents/pull-requests write
  and metadata read.

Apply and verify both ARC groups as private/selected and available only to the monorepo.
`mindclade-arc-artifact-authority` permits only the four `v5.0.0` reusable ARC workflows that
directly define the canary, build, qualification, and qualification-attestation jobs. The caller
`release.yml` is deliberately not sufficient: GitHub runner-group workflow restrictions authorize
the workflow that directly defines a job. `mindclade-arc-ci` permits only
`presubmit.yml@refs/heads/main` and must remain separate from every signing or publishing job.

Record the live group IDs, selected repositories, selected workflows, and effective permissions as
connected evidence. Before routing pull-request work to `mindclade-arc-ci`, prove with a bounded
canary that pull-request and merge-group events can schedule the permitted job while an unlisted
workflow cannot. Do not infer installation or routing from catalog source, and do not add broader
App scopes or workflow access to make a failed canary pass.

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
