<!-- mindclade-doc: changelog@1 -->

# Mindclade changelog · GitHub Enterprise governance

This file records material repository changes from the adoption of the
estate-wide changelog contract. Earlier history remains available in Git and is
not reconstructed or relabeled here.

## Unreleased

### Added

- Added the exact estate-wide `LEGAL.md` reliance policy and made it part of
  the repository contract.
- Added connected-audit expectations for `members_can_delete_repositories` and
  `members_can_change_repo_visibility`, so the enterprise repository-policy ceiling
  fails closed instead of passing unobserved.

### Changed

- Documented that repository deletion/transfer and visibility-change member privileges are
  enterprise-owner-only writes with no REST or provider path, including the exact GraphQL
  mutations and the required read-back verification.
- Documented that GitHub-to-cloud token-exchange evidence must consume a cloud API, because a
  successful authentication step alone does not prove a token was minted.
- Synchronized policy bundle `2026.08.21.3`, pinned repository-home validation to canonical
  commit `8467615f12868d4b78718b8ddf7f05797c44a507`, and removed the obsolete duplicate validator.
- Updated the proprietary license with the protected-disclosure notice and
  recorded the Contributor Covenant 2.1 attribution and modifications.
- Moved the reusable SPDX source-header template under `.github/` so `LICENSE`
  is the sole root license surface.

### Fixed

- Corrected the production contract to require `catalog/oidc-policy.yaml` and allow the
  committed Terraform dependency lock needed for reproducible provider resolution.

### Security

- Clarified that security response times are non-contractual operational
  targets and that safe harbor cannot authorize third-party systems or
  unlawful conduct.

### Removed

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
