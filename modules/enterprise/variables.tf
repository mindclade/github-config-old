# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
variable "enterprise_slug" {
  description = "Enterprise account slug, from github.com/enterprises/<slug>."
  type        = string
}

variable "organization" {
  description = "GitHub organization login owned by this enterprise."
  type        = string
}

variable "billing_email" {
  description = "Organization billing email."
  type        = string
}

variable "enterprise_admin_logins" {
  description = "Logins holding enterprise owner rights. At least two — see the precondition in main.tf."
  type        = set(string)
}

variable "allowed_action_patterns" {
  description = <<-EOT
    Actions permitted beyond GitHub-owned and verified-creator ones. Must be a superset of
    the org-level list in modules/policies — the narrower of the two always wins, so a
    pattern allowed there but missing here is still blocked, with a confusing error.
  EOT
  type        = list(string)
}

variable "secret_scanning_link" {
  description = "URL shown to a developer when push protection blocks a commit."
  type        = string
}
