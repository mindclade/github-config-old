# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
output "repositories" {
  description = "Managed repositories, with the numeric ids other repos need for WIF bindings."
  value       = module.repositories.repositories
}

output "team_ids" {
  description = "Team slug to numeric id. Consumed by infrastructure-live for IAM bindings."
  value       = module.teams.team_ids
}

output "team_slugs" {
  description = "Canonical slugs, which differ from the keys if a team is ever renamed."
  value       = module.teams.team_slugs
}

output "environments" {
  description = "Repository environments and their gates, for the runbook and for audit."
  value       = module.repositories.environments
}

output "oidc_subject_format" {
  description = <<-EOT
    The OIDC subject format this org now issues. Paste into bootstrap/wif.tf's
    attribute_condition, or diff against it — a mismatch here is the cause of nearly every
    "unable to acquire impersonated credentials" failure.
  EOT
  value       = module.policies.oidc_subject_format
}

output "ruleset_enforcement" {
  description = "Reminder of whether rulesets are enforcing or only evaluating."
  value       = module.rulesets.enforcement
}

output "ci_variables" {
  description = <<-EOT
    Repository to the Actions variable names declared for it. drift.yml compares this against
    what the API reports, so a variable added by hand in the UI surfaces the same way a
    drifted one does.
  EOT
  value       = module.repositories.ci_variables
}
