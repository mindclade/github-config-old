# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

output "team_ids" {
  description = "Team key to numeric id, as a string. Consumers needing a number must tonumber() it."
  value       = { for k, v in local.all_teams : k => v.id }
}

output "team_slugs" {
  description = "Canonical slugs, which differ from the keys if a team is renamed."
  value       = { for k, v in local.all_teams : k => v.slug }
}
