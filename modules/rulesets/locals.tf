# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

locals {
  ruleset_names = sort(keys(var.rulesets))
  enforcement = {
    for name, config in var.rulesets :
    name => try(var.enforcement_overrides[name], config.enforcement)
  }
}

check "overrides_name_a_real_ruleset" {
  assert {
    condition     = alltrue([for name in keys(var.enforcement_overrides) : contains(local.ruleset_names, name)])
    error_message = "enforcement_overrides names an undeclared ruleset. Valid names: ${join(", ", local.ruleset_names)}."
  }
}

check "catalog_matches_implemented_rulesets" {
  assert {
    condition = toset(local.ruleset_names) == toset([
      "baseline-all",
      "merge-queue",
      "protected-paths",
      "push-blocklist",
      "required-checks-go",
      "required-checks-mixed",
      "required-checks-tf",
      "required-checks-tf-static",
      "required-checks-tf-tests",
      "ruleset-workflows",
      "tag-protection",
    ])
    error_message = "catalog/rulesets.yaml and modules/rulesets must be changed together."
  }
}

output "enforcement" {
  description = "Effective enforcement mode for every managed organization ruleset."
  value       = local.enforcement
}
