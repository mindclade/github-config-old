<!-- mindclade-doc: runbook@1 -->

# Protected merge-queue rollout

> **Use when:** qualifying one repository for mandatory queued merges.
> **Safety boundary:** never apply governance locally, from an agent session, or from a plan that
> does not name the exact merged commit, repository, stage, and compiled rollout bundle.

## Contract

`catalog/merge-queue-readiness.yaml` is the versioned authority for rollout order, exact required
contexts, GitHub Actions integration ID `15368`, and immutable qualification evidence. The order is
`mindclade-internal-monorepo`, `gitops`, then `infrastructure-live`; a later repository cannot
advance until every predecessor is `qualified`.

The state machine is fail-closed:

- `blocked`: queue and permanent checks are `evaluate`; no evidence is accepted.
- `canary_active`: the queue and exact temporary repository-local checks are active, permanent
  organization rules remain `evaluate`, and no qualification evidence is accepted yet.
- `canary_passed`: the queue stays active with exact temporary repository-local checks, while the
  permanent organization rules remain `evaluate`.
- `qualified`: the queue and permanent rules are active and temporary duplicate checks are absent.

Each retained evidence object records the Actions run URL, head and base commit SHAs, UTC timestamp,
independent reviewer, generation-qualified restricted GCS URI, and SHA-256. `canary_passed` requires
positive pull-request, positive merge-group, and intentional-negative merge-group evidence.
`qualified` additionally requires a connected audit of the effective permanent rulesets.

Affected-test latency is not a merge-safety gate. It controls only pull-request affected-test and
queue-concurrency optimization; merge groups always run the repository's complete required graph.

## Protected transitions

All dispatches use `.github/workflows/apply.yml` on an exact merged `main` SHA. Keep delete and
replacement authorization false.

1. In a reviewed PR, change only the first blocked repository to `canary_active` while retaining
   its blocker and null evidence. The speculative plan must show only that queue and its exact
   temporary checks becoming active. The protected normal apply on the merged SHA activates them;
   an exact `canary` dispatch is an idempotent replay, not an unrecorded state transition.
2. Queue a benign documentation PR. Its post-merge normal apply must preserve the active canary.
   Retain the successful pull-request and merge-group evidence independently.
3. Queue a separate marker-gated failure that runs only on `merge_group`. Verify the required check
   fails, the PR does not merge, and no administrator or incident bypass is used. Close the PR.
4. Commit the three immutable evidence objects and set the repository to `canary_passed`. A normal
   protected apply preserves the active queue and temporary checks.
5. Dispatch `promote`. The exact temporary checks remain while the permanent organization rules
   become active. Audit their repository target, context strings, integration ID, strict policy,
   queue size, merge method, and bypass actors through a read-only connected identity.
6. Commit the permanent-ruleset audit and set the repository to `qualified`. The normal bundle and
   an explicit `finalize` bundle both remove temporary checks only while permanent checks are active.
7. Repeat for the next repository. Do not increase build concurrency or merge batch above one until
   the separately reviewed performance evidence window is complete.

For `infrastructure-live`, the positive merge group must include a successful protected read-only
WIF plan within the queue timeout. For `gitops`, `promotion-integrity` must validate the actual
merge-group base/head delta, and `production-handoff-gate` must report on every range. Its connected
read-only branch runs only for a `qualified-v1` production activation and must prove the immutable
evidence generation before merge. For the monorepo, `bazel / verdict` must prove full configured
analysis and tests over `//...`.

## Stop and rollback

Stop on a missing context, skipped or cancelled required result, wrong integration ID, stale SHA,
non-generation-qualified evidence URI, failed protected plan, delete or replacement, unexpected
repository scope, bypass, or disagreement between the catalog, compiled bundle, saved-plan metadata,
and connected read-back.

Rollback in reverse rollout order with a separately reviewed exact-SHA `rollback` dispatch. It
returns only the selected repository queue and permanent checks to `evaluate`, removes temporary
checks, and audits the exact rollback bundle. Immediately record that repository as `blocked` in a
reviewed source change before any unrelated main push can recompile the prior active state. Remove
queued pull requests before changing workflow producers, and preserve every check producer until
connected read-back confirms the rollback.
