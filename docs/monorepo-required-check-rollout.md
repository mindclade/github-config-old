<!-- mindclade-doc: runbook@1 -->

# Monorepo required-check rollout

> **Use when:** qualifying and activating the canonical monorepo's critical merge checks.
> **Safety boundary:** workflow source and evaluate-mode Terraform are not evidence of live enforcement.

## Evaluate contract

`required-checks-go`, `required-checks-mixed`, and
`required-checks-infra-static` remain in `evaluate`. The mixed ruleset includes
the exact stable `bazel / verdict` context. The merge-queue source contract is
active, but connected drift must be reconciled and audited through a protected
exact-SHA plan.

## Canary matrix

Before promotion, retain connected evidence for:

1. A documentation-only pull request where every required context reports and
   Bazel records an authoritative empty or narrow affected selection.
2. A leaf-source pull request where `bazel / verdict` records the owning package
   and its reverse-dependent tests without unrelated targets.
3. A global architecture or component-metadata pull request where the Bazel
   selection expands to `//...`.
4. An intentional Bazel analysis or test failure that reports the exact context
   red and appears in Ruleset Insights as a would-block result.
5. A successful merge-group run where `bazel / verdict` records explicit full
   configured analysis and tests.
6. A separately reviewed 28-day affected-run evidence window with at least 20 samples and p95 at
   or below 1,800 seconds before affected-test or queue-concurrency optimization. This performance
   evidence is not required-check activation evidence.

The same pull-request and merge-group audit must confirm `ci / build`,
`codeql-go / analyze (go)`, `python / build`, `rust / build`, `architecture`,
`Go registry + admission / live PostgreSQL and failure injection`, and
`infra-static` use their exact cataloged strings.

## Promotion order

1. Merge the monorepo workflow first and observe the evaluate-mode contexts.
2. Update the merge-safety activation gates to `qualified` with links or
   immutable evidence identifiers. Independent Platform and Security review is
   required.
3. In a separate PR, change only `required-checks-go`,
   `required-checks-mixed`, and `required-checks-infra-static` to `active` and
   update the matching activation evidence. The semantic validator already permits qualified
   mixed and infra-static promotion and rejects active enforcement while any required gate is
   blocked.
4. Review a protected plan for the exact merged SHA. Stop on deletion,
   replacement, unexpected repository scope, or a context not present in both
   pull-request and merge-group evidence.
5. Apply through the protected workflow, audit live rulesets and merge queue,
   then run a successful and intentional-negative canary without administrator
   bypass.

`required-checks-nix` remains evaluate until its independent v5/native-runner
qualification completes.

## Rollback

Return the affected ruleset to `evaluate` in a separately reviewed catalog
change before removing or renaming a workflow context. Apply only the exact
merged rollback SHA and verify live Insights. Do not disable the check producer
as the first response; the monorepo can switch Bazel to full mode while
preserving `bazel / verdict`.
