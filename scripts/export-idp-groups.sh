#!/usr/bin/env bash
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

# Export organization and team membership from the IdP into idp/team-members.json.
#
# modules/teams/membership.tf reads that file and creates every github_membership and
# github_team_membership from it. Nothing here is hand-maintained, for two reasons:
#
#   Offboarding. Removing someone from the IdP has to remove them everywhere, and a
#   hand-kept copy is the file people forget.
#
#   Audit. "Who had access on this date" must be answerable from one system, not
#   reconciled across two.
#
# A human editing idp/team-members.json will have it overwritten by the next run. That is
# the intended behaviour: the IdP group is the record, this file is a projection of it.
#
#   ./scripts/export-idp-groups.sh                 # write the export
#   ./scripts/export-idp-groups.sh --check         # exit 3 if the committed file is stale
#   ./scripts/export-idp-groups.sh --dry-run       # print to stdout, write nothing
#
# Exit status: 0 current, 2 usage/missing tool, 3 stale (--check only), 1 everything else.
#
# Requires: gcloud (authenticated), jq. The Cloud Identity API is reached with the caller's
# own credentials — in CI that is a WIF-obtained token, locally it is your gcloud login.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/idp/team-members.json"
CUSTOMER_ID="${IDP_CUSTOMER_ID:-}"
DOMAIN="${IDP_DOMAIN:-mindclade.com}"

CHECK=0
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --check)   CHECK=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --domain)  DOMAIN="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# bash 4+, checked explicitly.
#
# This script uses associative arrays (`declare -A`). macOS ships bash 3.2.57 and always
# will — its licence changed at bash 4 — so on a stock Mac `declare -A GROUP_FOR_TEAM=(...)`
# is parsed as an INDEXED array assignment, `[engineering]` is evaluated as arithmetic, and
# the script dies with:
#
#   line 70: engineering: unbound variable
#
# which says nothing about bash versions to anyone reading it. `nix develop` in this
# repository now supplies bash 5, so inside that shell this never trips — the check is for
# anyone running the script directly, which is the common case on a Mac.
if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  echo "error: this script needs bash 4 or newer; found ${BASH_VERSION}." >&2
  echo "  macOS ships bash 3.2 and will not ship newer. Install a current one and re-run:" >&2
  echo "    brew install bash && \$(brew --prefix)/bin/bash $0 $*" >&2
  exit 2
fi

command -v gcloud >/dev/null || { echo "error: gcloud not on PATH. Install the Google Cloud SDK." >&2; exit 2; }
command -v jq >/dev/null     || { echo "error: jq not on PATH." >&2; exit 2; }

if [ -z "$CUSTOMER_ID" ]; then
  # The Cloud Identity customer id, same value bootstrap feeds to
  # iam.allowedPolicyMemberDomains. Derived rather than hardcoded so this script works
  # against a test directory without an edit.
  CUSTOMER_ID=$(gcloud organizations list --format='value(owner.directoryCustomerId)' | head -1)
fi
if [ -z "$CUSTOMER_ID" ]; then
  echo "error: could not determine the Cloud Identity customer id." >&2
  echo "  Set IDP_CUSTOMER_ID, or check that gcloud is authenticated." >&2
  exit 1
fi

# ---------------------------------------------------------------------------------------
# Group to team mapping
# ---------------------------------------------------------------------------------------
# The IdP group whose members become each GitHub team. Every key MUST exist in
# catalog/teams.yaml — membership.tf has a `check` block that fails the plan otherwise, and
# names the offending team.
#
# Kept here rather than in the catalogue because it is a property of the IdP, not of the
# access model: renaming a group in Okta changes this file and nothing else.
declare -A GROUP_FOR_TEAM=(
  [engineering]="eng-all@${DOMAIN}"
  [platform]="eng-platform@${DOMAIN}"
  [security]="eng-security@${DOMAIN}"
  [research]="eng-research@${DOMAIN}"
  [data]="eng-data@${DOMAIN}"
  [biosecurity]="biosecurity-review@${DOMAIN}"
)

# Groups whose members hold `admin` on the organization rather than `member`. Deliberately
# a separate group from eng-platform: org ownership is not a side effect of joining a team.
ADMIN_GROUP="github-org-admins@${DOMAIN}"

# ---------------------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------------------
# Cloud Identity returns the Google account address. The GitHub login is carried as a custom
# schema attribute set by the IdP during SCIM provisioning — without it there is no way to
# map a person to a GitHub account, and guessing from the local part is how the wrong
# `jsmith` gets added to an org.
members_of() {
  local group="$1"
  local group_id

  # A MISSING GROUP IS FATAL, not a warning.
  #
  # This used to warn and return 0, which meant a single absent group produced an export with
  # that team empty — and the next apply removed every member from it. The global
  # "refuse to write an empty export" guard below does not catch that: it only trips when
  # ALL org members resolve to zero, so one missing group sails past it while five others
  # keep the total non-zero.
  #
  # Offboarding an entire team is exactly the operation that must never happen by accident,
  # and a typo in GROUP_FOR_TEAM or a group renamed in the IdP is how it would.
  if ! group_id=$(gcloud identity groups describe "$group" --format='value(name)' 2>/dev/null); then
    echo "::error::group ${group} does not exist in the directory." >&2
    echo "  Every group in GROUP_FOR_TEAM must exist before this runs. Writing the export" >&2
    echo "  without it would empty the corresponding GitHub team on the next apply." >&2
    echo "  Create it, or remove the mapping — do not leave it dangling." >&2
    return 1
  fi

  gcloud identity groups memberships list \
    --group-email="$group" \
    --format=json 2>/dev/null \
    | jq -r --arg g "$group" '
        .[]
        | select(.type == "USER")
        | { email: .preferredMemberKey.id, role: ( [.roles[].name] | if index("MANAGER") then "maintainer" else "member" end ) }
      ' || {
    echo "error: could not list members of ${group} (id ${group_id})" >&2
    return 1
  }
}

# Resolve a directory address to its GitHub login. Returns nothing when the attribute is
# absent, which is the correct outcome: a person with no linked GitHub account should not
# appear in the export at all, rather than appearing under a guessed name.
github_login_for() {
  local email="$1"
  gcloud identity users describe "$email" --format=json 2>/dev/null \
    | jq -r '.customSchemas.github.login // empty' 2>/dev/null || true
}

echo "Exporting from directory ${CUSTOMER_ID} (${DOMAIN})..." >&2

org_members_json="[]"
team_members_json="{}"
unmapped=()

# Org membership, from the union of every mapped group. Someone in a team group but not in
# the org would be a team membership Terraform cannot create.
declare -A ORG_ROLE
declare -A SEEN_LOGIN

collect_org_role() {
  local email="$1" role="$2" login
  login=$(github_login_for "$email")
  if [ -z "$login" ]; then
    unmapped+=("$email")
    return 0
  fi
  SEEN_LOGIN["$email"]="$login"
  # admin wins over member, regardless of the order groups are processed.
  if [ "${ORG_ROLE[$login]:-member}" != "admin" ]; then
    ORG_ROLE["$login"]="$role"
  fi
}

for team in "${!GROUP_FOR_TEAM[@]}"; do
  group="${GROUP_FOR_TEAM[$team]}"
  echo "  ${team} ← ${group}" >&2

  entries=$(members_of "$group")
  [ -z "$entries" ] && continue

  team_entries="[]"
  while IFS= read -r entry; do
    [ -z "$entry" ] && continue
    email=$(jq -r '.email' <<<"$entry")
    role=$(jq -r '.role' <<<"$entry")

    collect_org_role "$email" "member"
    login="${SEEN_LOGIN[$email]:-}"
    [ -z "$login" ] && continue

    team_entries=$(jq -c --arg u "$login" --arg r "$role" '. + [{username: $u, role: $r}]' <<<"$team_entries")
  done < <(jq -c '.' <<<"$entries")

  team_members_json=$(jq -c --arg t "$team" --argjson m "$team_entries" '.[$t] = $m' <<<"$team_members_json")
done

# Org admins, applied over the top.
#
# No `|| true`. A missing admin group is the same class of problem as a missing team group:
# it does not error, it just silently downgrades every org owner to `member` on the next
# apply. Let members_of's failure propagate.
echo "  org admins ← ${ADMIN_GROUP}" >&2
admin_entries=$(members_of "$ADMIN_GROUP")
if [ -n "$admin_entries" ]; then
  while IFS= read -r entry; do
    [ -z "$entry" ] && continue
    email=$(jq -r '.email' <<<"$entry")
    collect_org_role "$email" "admin"
    login="${SEEN_LOGIN[$email]:-}"
    [ -n "$login" ] && ORG_ROLE["$login"]="admin"
  done < <(jq -c '.' <<<"$admin_entries")
fi

for login in "${!ORG_ROLE[@]}"; do
  org_members_json=$(jq -c --arg u "$login" --arg r "${ORG_ROLE[$login]}" \
    '. + [{username: $u, role: $r}]' <<<"$org_members_json")
done

# Stable ordering. Without it every run produces a diff, the scheduled job commits it, and
# the signal that membership actually changed is lost in the noise.
document=$(jq -S '
  {
    org_members: (.org_members | sort_by(.username)),
    team_members: (.team_members | with_entries(.value |= sort_by(.username)))
  }
' <<<"$(jq -n --argjson o "$org_members_json" --argjson t "$team_members_json" \
        '{org_members: $o, team_members: $t}')")

# ---------------------------------------------------------------------------------------
# Refuse to write an empty export
# ---------------------------------------------------------------------------------------
# An IdP outage, an expired credential, or a renamed group all produce zero members without
# producing an error. Writing that would remove every person from the organization on the
# next apply — a total lockout, from a script that reported success.
count=$(jq '.org_members | length' <<<"$document")
if [ "$count" -eq 0 ]; then
  echo "::error::the export contains no org members. Refusing to write." >&2
  echo "  This is almost always a credential or group-naming problem, not an empty org." >&2
  echo "  Writing it would remove every member on the next apply." >&2
  exit 1
fi

# ---------------------------------------------------------------------------------------
# Refuse to empty a team that currently has members
# ---------------------------------------------------------------------------------------
# The guard above is global: it only trips when EVERY org member vanishes. One team going to
# zero sails past it while the others keep the total non-zero — and that is the more likely
# failure, because it needs only one group renamed, one membership sync half-finished, or one
# typo in GROUP_FOR_TEAM.
#
# Emptying @security or @biosecurity is not a small mistake. Those teams gate ruleset changes
# and the production biosecurity attestor, so removing their members removes the reviewers
# who would have caught it.
#
# Compared against the COMMITTED export rather than against a threshold, so the question is
# "did this run lose people who were there before?" and not "does this number look low?".
# A team that was already empty stays allowed — that is a new team, not a regression.
if [ -f "$OUT" ]; then
  emptied=$(jq -r --argjson new "$document" '
    .team_members // {}
    | to_entries[]
    | select((.value | length) > 0)
    | select((($new.team_members[.key]) // [] | length) == 0)
    | "\(.key) (had \(.value | length))"
  ' "$OUT" 2>/dev/null || true)

  if [ -n "$emptied" ]; then
    echo "::error::this export would empty a team that currently has members:" >&2
    while IFS= read -r line; do
      [ -n "$line" ] && echo "  - $line" >&2
    done <<<"$emptied"
    echo "  Applying it removes every member from that team. If the team really is being" >&2
    echo "  disbanded, delete it from catalog/teams.yaml in the same change — do not let it" >&2
    echo "  happen as a side effect of a group that stopped resolving." >&2
    echo "  Override with IDP_ALLOW_TEAM_EMPTY=1 once you have confirmed it is intended." >&2

    # FATAL ONLY WHEN THIS RUN WOULD WRITE.
    #
    # --dry-run prints and writes nothing, and --check compares and writes nothing, so neither
    # can empty a team — but this guard sat above both early exits and exited 1 for them too.
    # That made the pre-flight step in bootstrap/docs/first-apply.md, which is presented as
    # the safe way to look before touching anything, fail on a condition it could not cause.
    # It also made --check's exit status ambiguous between "stale" and "would empty a team".
    if [ "$DRY_RUN" -eq 1 ] || [ "$CHECK" -eq 1 ]; then
      echo "::warning::not writing (--dry-run/--check), so this is reported and not enforced." >&2
    else
      [ "${IDP_ALLOW_TEAM_EMPTY:-0}" = "1" ] || exit 1
      echo "::warning::IDP_ALLOW_TEAM_EMPTY=1 set — proceeding anyway." >&2
    fi
  fi
fi

if [ ${#unmapped[@]} -gt 0 ]; then
  echo "::warning::${#unmapped[@]} directory user(s) have no linked GitHub login and were omitted:" >&2
  printf '  %s\n' "${unmapped[@]}" >&2
  echo "  Set the github.login custom schema attribute in the IdP. Guessing from the" >&2
  echo "  address is how the wrong account gets added to the organization." >&2
fi

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%s\n' "$document"
  exit 0
fi

if [ "$CHECK" -eq 1 ]; then
  if [ ! -f "$OUT" ]; then
    echo "::error::${OUT#"$ROOT/"} does not exist. Run this script without --check." >&2
    exit 1
  fi
  if diff -u <(jq -S '.' "$OUT") <(printf '%s\n' "$document"); then
    echo "idp/team-members.json is current (${count} org member(s))."
    exit 0
  fi
  # 3, not 1. Every other failure here exits 1 or 2 — an unreachable directory, a missing
  # customer id, a guard trip — and a caller that cannot tell those apart from "the file needs
  # regenerating" has to treat a broken read as routine staleness. .github/workflows/
  # idp-sync.yml relies on the distinction: 3 opens an issue, anything else fails the job.
  echo "::error::idp/team-members.json is stale. Re-run this script and commit the result." >&2
  exit 3
fi

mkdir -p "$(dirname "$OUT")"
printf '%s\n' "$document" > "$OUT"
echo "Wrote ${OUT#"$ROOT/"} — ${count} org member(s), $(jq '.team_members | length' <<<"$document") team(s)."
