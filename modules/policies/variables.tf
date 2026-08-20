# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "organization" {
  description = "GitHub organization login."
  type        = string
}

variable "actions_policy" {
  description = "Organization Actions policy from catalog/actions-policy.yaml."
  type = object({
    enabled_repositories             = string
    allowed_actions                  = string
    default_workflow_permissions     = string
    can_approve_pull_request_reviews = bool
    sha_pinning_required             = bool
    github_owned_allowed             = bool
    verified_creator_allowed         = bool
    allowed_action_patterns          = list(string)
  })
}

variable "oidc_policy" {
  description = "OIDC policy from catalog/oidc-policy.yaml."
  type = object({
    subject_claim_keys                               = list(string)
    required_wif_attribute_claims                    = list(string)
    repository_opt_in                                = bool
    require_immutable_default_subject                = bool
    require_trusted_owner_id                         = bool
    require_repository_id                            = bool
    require_workflow_ref                             = bool
    require_ref                                      = bool
    require_protected_environment_for_sensitive_plan = bool
    require_protected_environment_for_apply          = bool
    explicit_audience_required                       = bool
  })
}

variable "managed_repository_ids" {
  description = "Repository name to numeric id for selected organization variables."
  type        = map(number)
}

variable "wif_pool_project_number" {
  description = "Project number containing the bootstrap-managed WIF pool."
  type        = string
  default     = ""
  validation {
    condition     = var.wif_pool_project_number == "" || can(regex("^[0-9]+$", var.wif_pool_project_number))
    error_message = "wif_pool_project_number must be the numeric project number."
  }
}

variable "artifact_registry_host" {
  description = "Approved Artifact Registry hostname."
  type        = string
}
