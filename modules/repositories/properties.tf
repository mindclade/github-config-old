# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Definitions and values are compiled from catalog/custom-properties.yaml and
# catalog/repositories.yaml. This module contains no repository-specific policy.
resource "github_organization_custom_properties" "this" {
  for_each = var.custom_properties

  property_name      = each.key
  value_type         = each.value.type
  required           = each.value.required
  default_value      = each.value.default_value
  description        = each.value.description
  allowed_values     = each.value.values
  values_editable_by = each.value.values_editable_by
}

locals {
  repository_property_values = merge([
    for repository, config in var.repositories : {
      "${repository}:mindclade_repository_class" = {
        repository = repository
        property   = "mindclade_repository_class"
        value      = [config.repository_class]
      }
      "${repository}:mindclade_owner_team" = {
        repository = repository
        property   = "mindclade_owner_team"
        value      = [config.owner_team]
      }
      "${repository}:mindclade_criticality" = {
        repository = repository
        property   = "mindclade_criticality"
        value      = [config.criticality]
      }
      "${repository}:mindclade_data_classification" = {
        repository = repository
        property   = "mindclade_data_classification"
        value      = [config.data_classification]
      }
      "${repository}:mindclade_production_authority" = {
        repository = repository
        property   = "mindclade_production_authority"
        value      = [config.production_authority]
      }
      "${repository}:mindclade_ci_profile" = {
        repository = repository
        property   = "mindclade_ci_profile"
        value      = [config.ci_profile]
      }
      "${repository}:mindclade_language_profile" = {
        repository = repository
        property   = "mindclade_language_profile"
        value      = [config.language_profile]
      }
      "${repository}:mindclade_lifecycle" = {
        repository = repository
        property   = "mindclade_lifecycle"
        value      = [config.lifecycle]
      }
    }
  ]...)
}

resource "github_repository_custom_property" "this" {
  for_each = local.repository_property_values

  repository     = github_repository.this[each.value.repository].name
  property_name  = each.value.property
  property_type  = var.custom_properties[each.value.property].type
  property_value = each.value.value

  depends_on = [github_organization_custom_properties.this]
}

check "repository_property_values_are_allowed" {
  assert {
    condition = alltrue([
      for _, item in local.repository_property_values :
      contains(var.custom_properties[item.property].values, one(item.value))
    ])
    error_message = "A repository custom-property value is absent from catalog/custom-properties.yaml."
  }
}
