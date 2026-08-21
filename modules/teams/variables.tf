# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "teams" {
  description = "Team key to its description, privacy, and parent key (null for a root team)."
  type = map(object({
    description = string
    privacy     = string
    parent      = optional(string)
  }))
}

variable "review_assignment_teams" {
  description = "Teams that receive round-robin review requests. Others get none, to avoid noise."
  type        = set(string)
  default     = []
}

variable "idp_export_path" {
  description = <<-EOT
    Path to the IdP membership export. Absence is tolerated only for offline/source bootstrap;
    every supported connected plan/apply path must pass validate-adoption-plan.py first.
  EOT
  type        = string
}
