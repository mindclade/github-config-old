# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# The subject template contains only claims that are present for every direct or
# reusable workflow job. Cloud authorization still uses mapped top-level claims;
# it must not depend solely on the human-readable subject string.
resource "github_actions_organization_oidc_subject_claim_customization_template" "this" {
  include_claim_keys = var.oidc_policy.subject_claim_keys
}

# integrations/github 6.13 does not expose GitHub's use_immutable_subject field. Terraform
# therefore remains authoritative for the claim template and use_default flags, while the narrow
# scripts/enforce-immutable-oidc.py REST adapter restores and verifies the immutable opt-in after
# every apply. Plan and drift run the same adapter in read-only mode.

# Organization templates are not inherited automatically. Manage every repository's opt-in
# explicitly so an out-of-band custom subject cannot silently invalidate bootstrap's default
# environment-shaped WIF subjects. include_claim_keys must be unset when use_default is true.
resource "github_actions_repository_oidc_subject_claim_customization_template" "managed" {
  for_each = var.managed_repository_ids

  repository         = each.key
  use_default        = !var.oidc_policy.repository_opt_in
  include_claim_keys = var.oidc_policy.repository_opt_in ? var.oidc_policy.subject_claim_keys : null

  depends_on = [github_actions_organization_oidc_subject_claim_customization_template.this]
}

output "oidc_subject_format" {
  description = "Required managed-repository OIDC subject format; REST enforcement is verified after Terraform apply."
  value = var.oidc_policy.repository_opt_in ? join(
    ":", [for key in var.oidc_policy.subject_claim_keys : "${key}=<value>"]
  ) : "github-immutable-default"
}
