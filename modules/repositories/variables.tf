# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

variable "repositories" {
  description = "Authoritative repository catalog."
  type = map(object({
    description          = string
    default_branch       = string
    visibility           = string
    repository_class     = string
    criticality          = string
    data_classification  = string
    production_authority = string
    owner_team           = string
    ci_profile           = string
    language_profile     = string
    lifecycle            = string
    environments         = list(string)
    topics               = list(string)
    has_issues           = bool
    has_projects         = bool
  }))
}
variable "custom_properties" {
  description = "Organization custom-property definitions from catalog/custom-properties.yaml."
  type = map(object({
    type               = string
    required           = bool
    default_value      = string
    description        = string
    values_editable_by = string
    values             = list(string)
  }))
}
variable "team_access" { type = map(map(string)) }
variable "team_ids" { type = map(string) }
variable "environments" {
  type = map(object({
    wait_timer             = number
    reviewer_teams         = list(string)
    protected_branches     = bool
    custom_branch_policies = bool
    prevent_self_review    = bool
    project_required       = bool
  }))
}
variable "repository_environments" { type = map(list(string)) }
variable "ci_variables" {
  type    = map(map(string))
  default = {}
}
variable "environment_project_ids" {
  type    = map(string)
  default = {}
}
variable "dr_evidence_environment_variables" {
  description = "Exact non-secret values published only to protected DR evidence environments after bootstrap and infrastructure apply."
  type        = map(string)
  default     = {}

  validation {
    condition = length(var.dr_evidence_environment_variables) == 0 || (
      toset(keys(var.dr_evidence_environment_variables)) == toset([
        "WIF_PROVIDER_DR_EVIDENCE",
        "SA_DR_EVIDENCE_WRITER",
        "DR_EVIDENCE_PROJECT",
        "DR_EVIDENCE_BUCKET",
      ]) &&
      can(regex("^projects/[0-9]+/locations/global/workloadIdentityPools/github/providers/gh-dr-evidence$", try(var.dr_evidence_environment_variables["WIF_PROVIDER_DR_EVIDENCE"], ""))) &&
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam\\.gserviceaccount\\.com$", try(var.dr_evidence_environment_variables["SA_DR_EVIDENCE_WRITER"], ""))) &&
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", try(var.dr_evidence_environment_variables["DR_EVIDENCE_PROJECT"], ""))) &&
      can(regex("^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$", try(var.dr_evidence_environment_variables["DR_EVIDENCE_BUCKET"], "")))
    )
    error_message = "DR evidence environment variables must be wholly absent during initial governance or contain the exact provider, writer, project, and bucket contract."
  }
}
