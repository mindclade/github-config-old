<!-- mindclade-doc: changelog@1 -->

# Mindclade changelog · GitHub Enterprise governance

This file records material repository changes from the adoption of the
estate-wide changelog contract. Earlier history remains available in Git and is
not reconstructed or relabeled here.

## Unreleased

### Added

- Added a workspace-level GitHub platform qualifier with native gates, cross-repository policy and
  workflow contracts, and separate JSON/Markdown source and connected-evidence verdicts.
- Added a schema-backed shared-workflow adoption graph, generated dashboard, expiring evidence
  ledger, protected DR activation preparation, and coordinated immutable-pin upgrade automation.
- Added negative mutation tests for permissions, caller pins, activation gates, evidence expiry,
  and fail-closed preparation behavior.
- Added a schema-versioned `BOOTSTRAP_ACCOUNT_HANDOFF_JSON` compiler contract that binds a clean
  bootstrap source commit and canonical platform-output digest to the exact state buckets and
  service accounts protected governance publishes to `infrastructure-live`.
- Added an inert `nix-cache-publication` environment assigned only to the monorepo, with protected
  main, Platform and Security review, self-review prevention, and a wait timer. It contains no
  variables or secrets and activates no cache publisher while connected qualification is blocked.
- Added the source-only bootstrap `1.5.0` Bazel-cache WIF handoff and exact applied `1.4.0`
  provider/reader/writer governance contract, with all cache client activation remaining blocked.
- Added structural HCL validation for required-check rulesets, release-tag controls, adoption
  imports, environment handoff, and repository OIDC behavior, with mutation tests proving comments
  cannot satisfy implementation contracts.
- Added a schema-backed readiness contract for the deferred infrastructure cost verdict; the
  candidate context remains explicitly non-required until positive and intentional-negative
  evidence is reviewed for both pull requests and merge groups.
- Added selected-repository estate-observer and ref-janitor Apps, separate read/delete
  environments, and a dry-run-first retention policy for the exact seven-repository estate.
- Added a machine-validated governance activation gate and the mandatory independent
  retrospective record for bootstrap PR #25.
- Added the stable live PostgreSQL registry and admission qualification context to the
  evaluate-only mixed-language ruleset, preserving the connected database safety gate.
- Restored inert Terraform `moved` blocks and an immutable-ID runbook for the historical
  monorepo repository-key migration while connected state inventory remains unresolved.
- Added the exact estate-wide `LEGAL.md` reliance policy and made it part of
  the repository contract.
- Added connected-audit expectations for `members_can_delete_repositories` and
  `members_can_change_repo_visibility`, so the enterprise repository-policy ceiling
  fails closed instead of passing unobserved.
- Added an evaluate-first organization rule for `v*` tag creation with Release as its sole
  creation bypass, plus a Terraform precondition that rejects activation before connected
  qualification or without active no-bypass immutability protection.
- Recorded the connected `github-config/main` merge-protection gap as a machine-enforced adoption
  blocker after five administrator merges completed with no review while protected plans waited.
- Added a GET-only estate tag inventory that reports SemVer releases and fails closed on temporary
  refs or potentially truncated connected evidence.
- Added a schema-backed, SHA-bound rescue-tag exception expiring 2026-09-21 and exact
  platform-managed dispositions for empty GitHub Copilot environments. Movement, expiry,
  additional temporary tags, or added environment authority fails the connected audit.

### Changed

- Made the bootstrap protected-CI input handoff explicit and fail closed, including the exact
  legacy-replica disposition, U.S. Secret Manager location, state retention, and KMS protection
  values required to keep post-migration plans identical to the reviewed first apply.
- Replaced hard-coded evaluate-only clamps for every evidence-gated ruleset with one fail-closed
  lifecycle that accepts active enforcement only after that rule's connected evidence is
  qualified; the resting catalog remains evaluate.
- Changed nightly access-expiry validation from whole-file substring matching to parsed workflow
  job and step validation.
- Refreshed connected environment imports, including every observed desired environment, while
  recording auto-created `copilot` environments as explicit platform-managed exceptions and
  absent `.github` release environments as unresolved rather than mutating them.
- Staged `ruleset-workflows` and the bootstrap `plan / verdict` gate in evaluate mode until their
  release and connected-context evidence exists; baseline and protected-path desired enforcement
  remain active.
- Added explicit `adopt-evaluate`, `promote-core`, and `normal` apply phases whose exact
  enforcement overrides are recorded in and re-verified from the saved-plan artifact.
- Documented that repository deletion/transfer and visibility-change member privileges are
  enterprise-owner-only writes with no REST or provider path, including the exact GraphQL
  mutations and the required read-back verification.
- Documented that GitHub-to-cloud token-exchange evidence must consume a cloud API, because a
  successful authentication step alone does not prove a token was minted.
- Synchronized policy bundle `2026.08.23.1`, pinned repository-home validation to canonical
  commit `f6d4bf43a1c4a69345556a224cfd13c3ab53188e`, and removed the obsolete duplicate validator.
- Updated the proprietary license with the protected-disclosure notice and
  recorded the Contributor Covenant 2.1 attribution and modifications.
- Moved the reusable SPDX source-header template under `.github/` so `LICENSE`
  is the sole root license surface.

### Fixed

- Corrected the production contract to require `catalog/oidc-policy.yaml` and allow the
  committed Terraform dependency lock needed for reproducible provider resolution.

### Security

- Split ARC presubmit from artifact authority with an exact second runner group, and corrected
  release access to the four reusable workflows that directly define ARC jobs instead of the
  caller workflow that cannot authorize them.
- Add an always-present, path-aware `plan / verdict` contract for github-config and a dedicated
  evaluate-mode required-check ruleset. Active enforcement is machine-blocked until both
  credential-free and protected-plan paths are observed.
- Record the zero-review, pre-qualification merge incidents through github-config PRs #35–#39 and
  infrastructure-live PR #25, `.github` PRs #22–#23, and bootstrap PR #30 as connected
  branch-protection activation blockers. Audit evidence attributes them to an interactive browser
  administrator session rather than an App or Actions workflow.

- Clarified that security response times are non-contractual operational
  targets and that safe harbor cannot authorize third-party systems or
  unlawful conduct.

### Removed

- Retired the temporary monorepo rescue-tag exception after its durable GKE qualification work
  moved to a governed pull request and the obsolete Buildkite path remained intentionally retired.

## 2026-08-21 — Common-document governance baseline

### Added

- established local, versioned contribution, security, support, conduct,
  governance, license, notice, and changelog documents;
- added machine-enforced presence and content requirements for those documents.

### Changed

- aligned the root documentation with the Mindclade MONO brand and repository
  authority contract;
- standardized proprietary rights, contributor authorization, third-party
  precedence, and support routing across the governed repository estate.

### Security

- made private vulnerability reporting and the absence of a published PGP key
  explicit;
- prohibited secrets, sensitive evidence, customer data, model material, and
  restricted biological content in public or general-purpose channels.
