# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Repository-level Actions variables — the wiring between the repos.
#
# Forty-eight of these are referenced across the five pipelines: WIF provider names, service
# account emails, project ids, state buckets, App ids. Every one of them used to be typed
# into the GitHub UI by hand.
#
# That made them the one part of this estate that was not code, and it showed in exactly the
# ways an unmanaged control does:
#
#   NOT DRIFT-DETECTED. drift.yml compares Terraform's world against reality. A variable
#   nothing declares is in neither, so someone editing SA_TF_LIVE_APPLY to point at a
#   different service account produces no diff, no alert, and a pipeline that authenticates
#   as something else entirely.
#
#   SILENT WHEN ABSENT. An unset variable expands to the empty string rather than failing.
#   `workload_identity_provider: ""` is an auth error naming no cause, and an empty TF_VAR is
#   a plan against a default that reports the difference as drift.
#
#   NOT REPRODUCIBLE. Standing up a second organization meant knowing which thirty-one values
#   to set, from a list that existed only in whoever set them up last.
#
# ---------------------------------------------------------------------------------------
# Where the value comes from
# ---------------------------------------------------------------------------------------
# This variable was declared for a while and never delivered: no workflow set
# TF_VAR_ci_variables, so every plan saw the `{}` default, this file produced no resources,
# and the values it argues for stayed hand-typed. drift.yml then reported all forty-eight as
# undeclared on every nightly run — a control that was configured, reported on, and enforcing
# nothing.
#
# It now arrives as the CI_VARIABLES repository variable, which plan.yml, apply.yml (both
# jobs) and drift.yml pass through as TF_VAR_ci_variables. Build it rather than typing it:
#
#   python3 scripts/export-ci-variables.py --stage bootstrap --bootstrap ../bootstrap --set
#
# Bootstrap stage emits only authoritative inputs for initial governance; the default full stage
# is used after downstream infrastructure and Apps exist. Both merge catalog/ci-variables.yaml
# — the half a human decides — with
# `terraform -chdir=../bootstrap output -json` — the half bootstrap generated. It refuses to
# write while any value is empty, and names which.
#
# NOTE THE HAZARD in the other direction: applying locally with a populated tfvars and then
# letting CI apply with CI_VARIABLES unset plans the DESTRUCTION of every variable here. The
# preflight step in each workflow fails before the plan for that reason, and
# apply.yml's `Refuse destructive applies` guard is the second line.

locals {
  ci_variable_pairs = merge([
    for repo, variables in var.ci_variables : {
      for name, value in variables :
      "${repo}:${name}" => { repository = repo, name = name, value = value }
    }
  ]...)
  arc_artifact_authority = {
    canary = {
      provider_variable = "WIF_PROVIDER_ARC_CANARY"
      provider_id       = "gh-arc-canary"
      account_variable  = "SA_ARC_CANARY"
      account_id        = "sa-arc-canary"
    }
    builder = {
      provider_variable = "WIF_PROVIDER_ARC_BUILDER"
      provider_id       = "gh-arc-builder"
      account_variable  = "SA_ARTIFACT_BUILDER"
      account_id        = "sa-artifact-builder"
    }
    qualification_reader = {
      provider_variable = "WIF_PROVIDER_ARC_QUALIFICATION_READER"
      provider_id       = "gh-arc-qualification-reader"
      account_variable  = "SA_ARTIFACT_QUALIFICATION_READER"
      account_id        = "sa-artifact-qual-reader"
    }
    qualifier = {
      provider_variable = "WIF_PROVIDER_ARC_QUALIFIER"
      provider_id       = "gh-arc-qualifier"
      account_variable  = "SA_ARTIFACT_QUALIFIER"
      account_id        = "sa-artifact-qualifier"
    }
    signer = {
      provider_variable = "WIF_PROVIDER_SIGNER"
      provider_id       = "gh-mindclade-internal-monorepo"
      account_variable  = "SA_ARTIFACT_SIGNER"
      account_id        = "sa-artifact-signer"
    }
    promoter = {
      provider_variable = "WIF_PROVIDER_ARC_PROMOTER"
      provider_id       = "gh-arc-promoter"
      account_variable  = "SA_ARTIFACT_PROMOTER"
      account_id        = "sa-artifact-promoter"
    }
  }
  arc_v5_active = anytrue([
    for capability, identity in local.arc_artifact_authority :
    try(var.ci_variables["mindclade-internal-monorepo"][identity.provider_variable], "") != ""
    if capability != "signer"
  ])
}

resource "github_actions_variable" "this" {
  for_each = local.ci_variable_pairs

  repository    = github_repository.this[each.value.repository].name
  variable_name = each.value.name
  value         = each.value.value
}

# A variable declared for a repository that does not exist fails mid-apply with a map-lookup
# error naming neither. Catch it at plan time.
check "ci_variables_reference_declared_repositories" {
  assert {
    condition = alltrue([
      for _, v in local.ci_variable_pairs : contains(keys(var.repositories), v.repository)
    ])
    error_message = "ci_variables names a repository that is not in the catalogue."
  }
}

# An empty value is worse than a missing one: the variable exists, the workflow reads it, and
# the failure surfaces as an auth error or a phantom drift rather than as "this is unset".
check "ci_variables_are_not_empty" {
  assert {
    condition = alltrue([
      for _, v in local.ci_variable_pairs : trimspace(v.value) != ""
    ])
    error_message = "A ci_variables entry has an empty value. An unset Actions variable expands to \"\" at run time, which surfaces as an authentication error naming no cause — remove the entry or give it a real value."
  }
}

# ---------------------------------------------------------------------------------------
# Per-repository WIF isolation
# ---------------------------------------------------------------------------------------
# bootstrap creates ONE Workload Identity provider per consuming repository, so that
# revocation is a targeted deletion and the audit log says which repository authenticated
# rather than "something in the org did".
#
# That isolation is undone by a copy-paste: pasting one repository's provider resource name
# into every entry produces a configuration that works perfectly — every pipeline
# authenticates — while every repository now shares one trust anchor. Nothing fails, and
# nothing in a plan says so.
#
# The provider id bootstrap generates is "gh-<repository>" (see its wif.tf), so the check is
# just that each repository's own name appears in its own provider string.
locals {
  wif_provider_vars = {
    for k, v in local.ci_variable_pairs : k => v
    if startswith(v.name, "WIF_PROVIDER") && !(
      v.repository == "infrastructure-live" && v.name == "WIF_PROVIDER_SIGNER"
    )
  }
}

check "wif_providers_are_per_repository" {
  assert {
    condition = alltrue([
      for _, v in local.wif_provider_vars :
      endswith(v.value, "/gh-${substr(replace(v.repository, "_", "-"), 0, 28)}")
    ])
    error_message = "A WIF_PROVIDER* variable does not end in this repository's own provider id. bootstrap creates one provider per repository (gh-<repo>); pointing two repositories at one provider works and silently removes the isolation that arrangement exists to provide."
  }
}

# The same failure in the other direction: a service account email pasted across repositories
# means two pipelines act as one identity, and the audit log cannot tell them apart.
check "service_accounts_are_not_shared_across_repositories" {
  assert {
    condition = length(distinct([
      for _, v in local.ci_variable_pairs : v.value
      if startswith(v.name, "SA_")
      ])) == length([
      for _, v in local.ci_variable_pairs : v.value
      if startswith(v.name, "SA_")
    ])
    error_message = "The same SA_* value appears twice within one repository's variables. Plan and apply identities must be different service accounts — that separation is what keeps apply credentials unreachable from a pull request."
  }
}

locals {
  deployment_attestor_contract = [
    try(var.ci_variables["gitops"]["BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT"], ""),
    try(var.ci_variables["gitops"]["BINAUTHZ_DEPLOYMENT_ATTESTOR"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_DEPLOYMENT_ATTESTOR"], ""),
  ]
  monorepo_attestor_contract = [
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_BUILD_ATTESTOR_PROJECT"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_BUILD_ATTESTOR"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_QUALIFICATION_ATTESTOR_PROJECT"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_QUALIFICATION_ATTESTOR"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_DEPLOYMENT_ATTESTOR_PROJECT"], ""),
    try(var.ci_variables["mindclade-internal-monorepo"]["BINAUTHZ_DEPLOYMENT_ATTESTOR"], ""),
  ]
}

# GitOps validates the same deployment attestor that the protected signer writes. Initial
# governance may omit the entire not-yet-provisioned contract; once any field is supplied,
# require the complete, matching pair so a partial handoff can never become trusted state.
check "artifact_trust_roots_match_consumers" {
  assert {
    condition = (
      alltrue([for value in local.deployment_attestor_contract : value == ""]) ||
      (
        alltrue([for value in local.deployment_attestor_contract : value != ""]) &&
        local.deployment_attestor_contract[0] == local.deployment_attestor_contract[2] &&
        local.deployment_attestor_contract[1] == local.deployment_attestor_contract[3]
      )
    )
    error_message = "The deployment attestor handoff must be wholly absent before infrastructure exists, or complete and identical for GitOps and the protected artifact signer."
  }
}

check "build_qualification_and_deployment_attestors_are_distinct" {
  assert {
    condition = (
      alltrue([for value in local.monorepo_attestor_contract : value == ""]) ||
      (
        alltrue([for value in local.monorepo_attestor_contract : value != ""]) &&
        length(toset([
          "${local.monorepo_attestor_contract[0]}/${local.monorepo_attestor_contract[1]}",
          "${local.monorepo_attestor_contract[2]}/${local.monorepo_attestor_contract[3]}",
          "${local.monorepo_attestor_contract[4]}/${local.monorepo_attestor_contract[5]}",
        ])) == 3
      )
    )
    error_message = "The monorepo attestor handoff must be wholly absent before infrastructure exists, or complete with distinct build, qualification, and deployment attestors."
  }
}

# infrastructure-live provisions the signer IAM binding and therefore consumes the same
# bootstrap trust tuple that the monorepo's protected release job uses. This is metadata, not
# an infrastructure-live authentication path, which is why WIF_PROVIDER_SIGNER is excluded
# from the per-repository authentication-provider check above.
check "artifact_signer_contract_matches_consumers" {
  assert {
    condition = (
      try(var.ci_variables["infrastructure-live"]["WIF_PROVIDER_SIGNER"], "") ==
      try(var.ci_variables["mindclade-internal-monorepo"]["WIF_PROVIDER_SIGNER"], null) &&
      can(regex(
        "^projects/[0-9]+/locations/global/workloadIdentityPools/github/providers/gh-mindclade-internal-monorepo$",
        try(var.ci_variables["infrastructure-live"]["WIF_PROVIDER_SIGNER"], "")
      )) &&
      can(regex(
        "^principal://iam\\.googleapis\\.com/projects/[0-9]+/locations/global/workloadIdentityPools/github/subject/repo:mindclade@[0-9]+/mindclade-internal-monorepo@[0-9]+:environment:release$",
        try(var.ci_variables["infrastructure-live"]["ARTIFACT_SIGNER_PRINCIPAL"], "")
      )) &&
      try(var.ci_variables["infrastructure-live"]["ARTIFACT_SIGNER_JOB_WORKFLOW_REF"], "") ==
      "mindclade/.github/.github/workflows/reusable-binauthz-sign.yml@refs/tags/${local.arc_v5_active ? "v5.0.0" : "v3.0.0"}"
    )
    error_message = "Infrastructure signer IAM and the monorepo release job must consume bootstrap's exact staged signer trust tuple (v3 before ARC activation, v5 after)."
  }
}

check "arc_artifact_authority_contract_is_capability_exact" {
  assert {
    condition = !local.arc_v5_active || (
      alltrue([
        for _, identity in local.arc_artifact_authority : can(regex(
          "^projects/[0-9]+/locations/global/workloadIdentityPools/github/providers/${identity.provider_id}$",
          try(var.ci_variables["mindclade-internal-monorepo"][identity.provider_variable], "")
        ))
        ]) && (
        alltrue([
          for _, identity in local.arc_artifact_authority :
          try(var.ci_variables["mindclade-internal-monorepo"][identity.account_variable], "") == ""
          ]) || alltrue([
          for _, identity in local.arc_artifact_authority :
          try(var.ci_variables["mindclade-internal-monorepo"][identity.account_variable], "") ==
          "${identity.account_id}@${try(var.ci_variables["mindclade-internal-monorepo"]["CI_PROJECT_ID"], "")}.iam.gserviceaccount.com"
        ])
      )
    )
    error_message = "Once any non-signer ARC capability is activated, every capability must use its dedicated bootstrap provider and applied common-CI service account."
  }
}

output "ci_variables" {
  description = <<-EOT
    Repository to the Actions variables declared for it. Read by drift.yml, which compares
    this against what the API reports — a variable added by hand in the UI is exactly as much
    of a problem as one that has drifted, and neither is visible to a plan.
  EOT
  value = {
    for repo, variables in var.ci_variables : repo => sort(keys(variables))
  }
}
