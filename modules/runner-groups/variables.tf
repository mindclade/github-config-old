# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "runner_groups" {
  description = "Human-authored organization runner-group policy."
  type = map(object({
    visibility               = string
    allowsPublicRepositories = bool
    restrictedToWorkflows    = bool
    repositories             = list(string)
    workflows                = list(string)
  }))
}

variable "repository_ids" {
  description = "Managed repository database IDs keyed by name."
  type        = map(number)
}
