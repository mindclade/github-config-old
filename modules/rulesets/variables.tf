# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "security_team_id" {
  description = "Numeric id of the security team."
  type        = number
}

variable "platform_team_id" {
  description = "Numeric id of the platform team."
  type        = number
}

variable "infrastructure_team_id" {
  description = "Numeric id of the infrastructure team."
  type        = number
}

variable "release_team_id" {
  description = "Numeric id of the release team."
  type        = number
}

variable "dot_github_repo_id" {
  description = "Numeric id of the .github repository holding mandatory workflows."
  type        = number
}

variable "rulesets" {
  description = "Ruleset inventory and resting enforcement from catalog/rulesets.yaml."
  type = map(object({
    enforcement       = string
    target            = optional(string)
    classes           = optional(list(string), [])
    repositories      = optional(list(string), [])
    language_profiles = optional(list(string), [])
    workflow_ref      = optional(string)
  }))
}

variable "repositories" {
  description = "Repository catalog used when a provider rule is available only per repository."
  type = map(object({
    repository_class = string
  }))
}

variable "enforcement_overrides" {
  description = "Temporary reviewed per-ruleset overrides."
  type        = map(string)
  default     = {}
  validation {
    condition     = alltrue([for _, value in var.enforcement_overrides : contains(["active", "evaluate", "disabled"], value)])
    error_message = "Each override must be active, evaluate, or disabled."
  }
}
