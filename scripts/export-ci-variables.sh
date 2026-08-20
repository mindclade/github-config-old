#!/usr/bin/env bash
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="${BOOTSTRAP_DIR:-$ROOT/../bootstrap}"
REPO="${GH_REPO:-Mindclade/github-config}"
MODE=print

while (($#)); do
  case "$1" in
    --bootstrap) BOOTSTRAP="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --set) MODE=set; shift ;;
    --check) MODE=check; shift ;;
    -h|--help) echo "usage: $0 [--bootstrap DIR] [--repo OWNER/REPO] [--set|--check]"; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 2 ;;
  esac
done

for command in terraform jq yq; do
  command -v "$command" >/dev/null || { echo "error: $command is required" >&2; exit 2; }
done

CONFIG="$(yq -o=json '.' "$ROOT/catalog/ci-variables.yaml")"
OUTPUTS="$(terraform -chdir="$BOOTSTRAP" output -json)"
[[ "$(jq 'length' <<<"$OUTPUTS")" -gt 0 ]] || { echo "error: bootstrap has no outputs" >&2; exit 1; }

PAYLOAD="$(jq -n --argjson config "$CONFIG" --argjson outputs "$OUTPUTS" '
  def output($name):
    ($outputs[$name].value // error("bootstrap output missing: \($name)"));
  def need($map; $key):
    ($map[$key] // error("bootstrap output map missing key: \($key)"));
  def required_env($name):
    (env[$name] // "") as $value
    | if ($value | length) == 0 then error("required operator environment variable is unset: \($name)") else $value end;
  def resolve:
    if type == "object" then with_entries(.value |= resolve)
    elif type == "array" then map(resolve)
    elif type == "string" and startswith("env:") then required_env(.[4:])
    else . end;

  ($config | resolve) as $resolved
  | (output("state_buckets")) as $state
  | (output("service_accounts")) as $sa
  | (output("github_wif_providers")) as $wif
  | (output("cicd_project_number")) as $cicd_number
  | (output("bootstrap_folder_id")) as $bootstrap_folder
  | (output("automation_secret_project_id")) as $automation_secret_project
  | (output("seed_project_id")) as $seed_project
  | (output("cicd_project_id")) as $cicd_project
  | (output("github_wif_pool_name")) as $github_wif_pool
  | (output("state_bucket_location")) as $state_location
  | (output("org_id")) as $org_id
  | (output("billing_account")) as $billing_account
  | (output("github_org")) as $organization
  | ($resolved * {
      "github-config": {
        ORGANIZATION: $organization,
        TFSTATE_BUCKET: need($state; "github-config"),
        WIF_POOL_PROJECT_NUMBER: ($cicd_number | tostring),
        WIF_PROVIDER_PLAN: need($wif; "github-config"),
        WIF_PROVIDER_APPLY: need($wif; "github-config"),
        SA_GITHUB_CONFIG_PLAN: need($sa; "github-config-plan"),
        SA_GITHUB_CONFIG_APPLY: need($sa; "github-config-apply")
      },
      bootstrap: {
        BOOTSTRAP_FOLDER_ID: $bootstrap_folder,
        TFSTATE_BUCKET: need($state; "bootstrap"),
        WIF_PROVIDER_PLAN: need($wif; "bootstrap"),
        WIF_PROVIDER_APPLY: need($wif; "bootstrap"),
        SA_BOOTSTRAP_PLAN: need($sa; "bootstrap-plan"),
        SA_BOOTSTRAP_DRIFT: need($sa; "bootstrap-drift"),
        SA_BOOTSTRAP_APPLY: need($sa; "bootstrap-apply")
      },
      "infrastructure-live": {
        GCP_ORG_ID: ($org_id | tostring),
        BILLING_ACCOUNT: $billing_account,
        BOOTSTRAP_SEED_PROJECT_ID: $seed_project,
        BOOTSTRAP_CICD_PROJECT_ID: $cicd_project,
        BOOTSTRAP_CICD_PROJECT_NUMBER: ($cicd_number | tostring),
        GITHUB_WIF_POOL_NAME: $github_wif_pool,
        STATE_LOCATION: $state_location,
        SECRETS_PROJECT_ID: $automation_secret_project,
        TFSTATE_BUCKET_DEVELOPMENT: need($state; "infrastructure-live-development"),
        TFSTATE_BUCKET_STAGING: need($state; "infrastructure-live-staging"),
        TFSTATE_BUCKET_PRODUCTION: need($state; "infrastructure-live-production"),
        WIF_PROVIDER_PLAN: need($wif; "infrastructure-live"),
        WIF_PROVIDER_APPLY: need($wif; "infrastructure-live"),
        SA_TF_LIVE_PLAN: need($sa; "infrastructure-live-plan"),
        SA_TF_LIVE_APPLY_FOUNDATION: need($sa; "infrastructure-live-apply-foundation"),
        SA_TF_LIVE_APPLY_DEVELOPMENT: need($sa; "infrastructure-live-apply-development"),
        SA_TF_LIVE_APPLY_STAGING: need($sa; "infrastructure-live-apply-staging"),
        SA_TF_LIVE_APPLY_PRODUCTION: need($sa; "infrastructure-live-apply-production")
      },
      gitops: {
        WIF_PROVIDER_PLAN: need($wif; "gitops")
      }
    })
')"

EMPTY="$(jq -r 'to_entries[] | .key as $repo | .value | to_entries[] | select(.value == "" or .value == null) | "\($repo)/\(.key)"' <<<"$PAYLOAD")"
if [[ -n "$EMPTY" ]]; then
  echo "error: required CI variable values are unset:" >&2
  sed 's/^/  - /' <<<"$EMPTY" >&2
  exit 1
fi

case "$MODE" in
  print)
    jq -S . <<<"$PAYLOAD"
    ;;
  set)
    command -v gh >/dev/null || { echo "error: gh is required for --set" >&2; exit 2; }
    # CI_VARIABLES is the bootstrap input that lets github-config create all other repository
    # variables. It is intentionally the one self-hosting variable not managed inside its own
    # JSON payload; drift.yml allowlists exactly this name.
    jq -cS . <<<"$PAYLOAD" | gh variable set CI_VARIABLES --repo "$REPO" --body-file -
    ;;
  check)
    command -v gh >/dev/null || { echo "error: gh is required for --check" >&2; exit 2; }
    current="$(gh variable get CI_VARIABLES --repo "$REPO")"
    diff -u <(jq -S . <<<"$current") <(jq -S . <<<"$PAYLOAD")
    ;;
esac
