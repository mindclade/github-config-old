# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
variable "organization" {
  description = "GitHub organization login."
  type        = string
}

variable "billing_email" {
  description = "Required by github_organization_settings."
  type        = string
}

variable "webhook_url" {
  description = "Real-time governance events endpoint. Empty disables the webhook."
  type        = string
  default     = ""
}

variable "webhook_secret" {
  description = "HMAC secret for the webhook. Supply only through a protected runtime credential path; never commit or persist it in a saved plan."
  type        = string
  default     = ""
  sensitive   = true
}

variable "app_scopes" {
  description = "GitHub App slug to the repositories it may reach."
  type        = map(list(string))
  default     = {}
}
