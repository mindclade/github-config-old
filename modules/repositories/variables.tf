# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
variable "repositories" {
  description = "Authoritative repository catalog."
  type = map(object({
    description            = string
    default_branch         = string
    visibility             = string
    repository_class       = string
    criticality            = string
    data_classification    = string
    production_authority   = string
    owner_team             = string
    ci_profile             = string
    language_profile       = string
    lifecycle              = string
    environments           = list(string)
    topics                 = list(string)
    has_issues             = bool
    has_projects           = bool
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
variable "team_slugs" { type = map(string) }
variable "environments" {
  type = map(object({
    wait_timer          = number
    reviewer_teams      = list(string)
    protected_branches  = bool
    prevent_self_review = bool
    project_required    = bool
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
