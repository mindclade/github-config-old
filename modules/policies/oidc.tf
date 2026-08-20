# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# The subject template contains only claims that are present for every direct or
# reusable workflow job. Cloud authorization still uses mapped top-level claims;
# it must not depend solely on the human-readable subject string.
resource "github_actions_organization_oidc_subject_claim_customization_template" "this" {
  include_claim_keys = var.oidc_policy.subject_claim_keys
}

# Organization templates are not inherited automatically. Every managed
# repository is opted into the catalog-defined template explicitly. Supplying
# the keys here also avoids provider/API ambiguity around use_default=false with
# an empty include_claim_keys list.
resource "github_actions_repository_oidc_subject_claim_customization_template" "managed" {
  for_each = var.oidc_policy.repository_opt_in ? var.managed_repository_ids : {}

  repository         = each.key
  use_default        = false
  include_claim_keys = var.oidc_policy.subject_claim_keys

  depends_on = [github_actions_organization_oidc_subject_claim_customization_template.this]
}

output "oidc_subject_format" {
  description = "Catalog-defined GitHub Actions OIDC subject format."
  value       = join(":", [for key in var.oidc_policy.subject_claim_keys : "${key}=<value>"])
}
