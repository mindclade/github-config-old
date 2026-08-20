# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# The subject template contains only claims that are present for every direct or
# reusable workflow job. Cloud authorization still uses mapped top-level claims;
# it must not depend solely on the human-readable subject string.
resource "github_actions_organization_oidc_subject_claim_customization_template" "this" {
  include_claim_keys = var.oidc_policy.subject_claim_keys
}

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
  description = "Effective managed-repository OIDC subject format."
  value = var.oidc_policy.repository_opt_in ? join(
    ":", [for key in var.oidc_policy.subject_claim_keys : "${key}=<value>"]
  ) : "github-immutable-default"
}
