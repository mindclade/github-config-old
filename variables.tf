# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "organization" {
  description = "Canonical GitHub organization login: mindclade."
  type        = string
  default     = "mindclade"
}

variable "billing_email" {
  description = "Organization billing email."
  type        = string
}

variable "ruleset_enforcement_overrides" {
  description = "Temporary, reviewed per-ruleset enforcement overrides. The catalog defines the resting state."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for _, value in var.ruleset_enforcement_overrides : contains(["active", "evaluate", "disabled"], value)])
    error_message = "Each ruleset enforcement override must be active, evaluate, or disabled."
  }
}

variable "ci_variables" {
  description = "Non-secret repository Actions variables generated from authoritative outputs."
  type        = map(map(string))
  default     = {}
}

variable "environment_project_ids" {
  description = "Environment to GCP project id for environments that require one."
  type        = map(string)
  default     = {}
}

variable "wif_pool_project_number" {
  description = "Numeric project number containing the bootstrap-managed WIF pool."
  type        = string
  default     = ""
  validation {
    condition     = var.wif_pool_project_number == "" || can(regex("^[0-9]+$", var.wif_pool_project_number))
    error_message = "wif_pool_project_number must be numeric."
  }
}

variable "artifact_registry_host" {
  description = "Approved Artifact Registry hostname."
  type        = string
  default     = "us-central1-docker.pkg.dev"
}

variable "app_scopes" {
  description = "Deprecated compatibility input. GitHub App scopes are authoritative in catalog/github-apps.yaml."
  type        = map(list(string))
  default     = {}

  validation {
    condition     = length(var.app_scopes) == 0
    error_message = "app_scopes is no longer caller-controlled; edit catalog/github-apps.yaml."
  }
}
