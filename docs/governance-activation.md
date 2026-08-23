<!-- mindclade-doc: runbook@1 -->

# Governance activation preflight

> **Use when:** moving the staged source changes into live GitHub enforcement.
> **Safety boundary:** source qualification is not authority to publish, approve, apply, or bypass.

`catalog/governance-activation.yaml` is the machine gate for this rollout. It stays `blocked`
until every named item has connected evidence. The current solo-founder exception does not cover
release publication, protected-environment approval, governance apply, repository administration,
or retrospective closeout.

## Current resting source state

- `baseline-all` and `protected-paths` remain the active desired floor with no baseline bypass and
  two approvals plus CODEOWNERS on enterprise/production control repositories.
- `ruleset-workflows` remains `evaluate` while the referenced `v5.0.0` tag is absent.
- `release-tag-creation` remains `evaluate`: Insights records who would be blocked from creating
  new `v*` tags, while the separate active, no-bypass `tag-protection` ruleset continues to
  prevent anyone—including Release—from moving or deleting an existing version tag.
- `required-checks-bootstrap` expects `plan / verdict` but remains `evaluate` until both its
  connected-plan and credential-free paths are observed.
- `required-checks-github-config` remains `evaluate` around the always-present `plan / verdict`
  context. Active enforcement is blocked until both documentation-only and connected-plan paths
  are observed at exact merged revisions.
- `required-checks-nix` remains `evaluate` until all seven repositories have native and rebuild
  evidence from the published v5 workflow.
- The monorepo Go, mixed-language, and infra-static rules remain `evaluate`. The mixed rule
  includes the exact `bazel / verdict` context, whose pull-request, intentional-negative,
  and merge-group full-graph evidence is tracked by
  [the monorepo rollout](monorepo-required-check-rollout.md). Affected-test latency remains a
  separate performance gate and cannot block required-check activation. The validator permits mixed and
  infra-static promotion only when their cataloged evidence gates are qualified; it no longer
  requires a validator-code edit to promote a qualified rule.
- `required-checks-gitops` and `required-checks-tf` remain `evaluate` until their sequential
  merge-queue canaries are qualified. The Terraform rule contains only `fmt`, `validate`, and
  `plan`. Infracost is not a required context: its source now defines a merge-group-capable verdict,
  but connected positive and intentional-negative evidence has not been reviewed on both event
  types. The schema-backed readiness contract therefore stays blocked.
- `.github` declares the two protected workflow-release environments, but the connected inventory
  found neither environment live.
- The exact observed `copilot` environments are GitHub-platform-managed exceptions, not Terraform
  resources. The audit requires zero secrets, variables, reviewers, timers, and custom protection
  rules and rejects any additional unmanaged environment.
- Read-only connected evidence proves `github-config/main` currently has no branch protection and
  inherits only active `push-blocklist` and `tag-protection`; desired branch-review and check
  rulesets are not live. GitHub accepting a merge is therefore not qualification to merge: PRs
  #35–#39 were merged by the repository administrator with zero reviews while `plan` was waiting.
  Infrastructure-live PR #25 was also merged with zero reviews while protected `plan` and
  `infracost` jobs were waiting, before dependency and terminal CI qualification; later review
  found additional fail-closed gaps requiring correction. `.github` PRs #22 and #23 and bootstrap
  PR #30 were also merged by the interactive administrator session without independent review.
  The audit evidence identifies a browser session, not an App or Actions workflow; this remains a
  governance failure requiring retrospective review, not evidence of credential compromise.

## Required order

1. Add a qualified person independent of both same-human founder accounts to the applicable
   Platform or Security review function. Preserve distinct people across the two v5 publication
   approvals.
2. Refresh organization-ruleset and Terraform-state inventory with an organization-ruleset-capable
   plan identity. Import every known-existing address and reject delete/replace actions.
   Remove redundant `.github` repository ruleset `21082865` only after the organization
   `tag-protection` rule is independently proven active and no-bypass.
3. Review the exact merged-SHA Terraform plan and dispatch `apply.yml` with
   `rollout_phase=adopt-evaluate`. This first bounded phase keeps every resting-active branch
   ruleset in evaluate mode while importing or creating the reviewed shapes. It may create
   `workflow-release-platform`, `workflow-release-security`, and `release-tag-creation` only in
   their staged forms; deletion or replacement remains a stop condition.
4. With an organization-ruleset-capable read identity, verify the connected rule targets only
   `refs/tags/v*` across all repositories, blocks creation, resolves the immutable Release team id
   as its sole always-bypass actor, and composes with active no-bypass `tag-protection`. Review
   Ruleset Insights and the exact non-destructive plan, then record
   `release_tag_creation_control_qualified: qualified` through an independently reviewed change.
5. After independently reviewing Ruleset Insights, dispatch `rollout_phase=promote-core` to make
   only `baseline-all` and `protected-paths` active. The saved-plan metadata must contain the
   exact phase and override map, and the apply job must recompute and match both before mutation.
   Promote `release-tag-creation` separately only after its qualification gate is recorded; its
   exact merged-SHA plan must pass the Terraform precondition before a bounded apply.
6. Merge the canonical `.github` v5 source through independent review. A Release-team operator—not
   an agent—creates the annotated `v5.0.0` tag on that exact merged commit through the active
   creation guard. Qualify the exact tag, approve
   both protected environments with distinct people, and publish the immutable release.
7. Adopt the published release and policy provenance record through consumer pull requests. Keep
   legacy Nix checks until `nix / verdict` is observed on pull requests, merge groups, schedules,
   all native platforms, and both rebuilds.
8. Merge the bootstrap and github-config plan-verdict workflows. For each repository, observe its
   stable verdict for both a relevant Terraform change and an unaffected documentation change.
   Confirm a close or draft-conversion event cancels a stale waiting run without cloud
   authentication.
   For github-config, first create the ruleset in evaluate mode and review Ruleset Insights before
   recording `github_config_verdict_observed: qualified`.
9. Update the remaining gate evidence to `qualified`, run the exact merged-SHA plan, and only then promote
   `ruleset-workflows`, `required-checks-bootstrap`, and `required-checks-nix` to active in a
   separate reviewed change.
10. Before adding cost policy to `required-checks-tf`, complete the four-step readiness sequence in
    [governance validation](governance-validation.md#deferred-cost-verdict). Never require the
    existing pull-request-only `infracost` or `comment` contexts.
11. Qualify merge queues sequentially through source-recorded `canary_active` and the exact
    `canary`, `promote`, `finalize`, and `rollback`
    transitions in [the protected merge-queue runbook](merge-queue-rollout.md). Resting normal
    applies must hold every unqualified repository and its permanent checks in `evaluate`.
12. Complete the independent retrospective in
   [issue #33](https://github.com/mindclade/github-config/issues/33) for infrastructure-live PR
   #25, `.github` PRs #22–#23, bootstrap PR #30, and github-config PRs #35–#39. Assign it to the
   independent Security reviewer after that human joins; a second founder-controlled account does
   not satisfy the review boundary.

## Stop conditions

Stop on a missing tag or release, same-human environment approvals, absent workflow context,
unimported live object, Terraform deletion/replacement, administrator bypass, tag-creation
activation without active no-bypass tag protection, incomplete API scope, or disagreement between
the plan, state list, connected audit, and activation record. Until the connected no-bypass branch
rules are proven active, stop even when GitHub presents an enabled merge action; an unprotected
repository accepting the operation is an external control gap, not an approval.

The read-only connected audit also inventories every live tag ref in every catalog-managed
repository. It emits that inventory as release evidence and fails closed on every non-SemVer ref
except the exact unexpired, SHA-bound rescue exception above, or when API evidence could be
truncated. Cleanup remains a separate reviewed operation; the auditor issues only GitHub GETs.
