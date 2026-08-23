<!-- mindclade-doc: operations@1 -->

# GitHub platform qualification

This repository owns the three-repository qualification orchestrator because it owns GitHub
governance and adoption state. Reusable workflow implementation remains in `.github`; the private
member profile and checked-in brand distribution remain in `.github-private`.

## Run the complete source qualification

Place `.github`, `.github-private`, and `github-config` as sibling clean checkouts, then run:

```sh
make qualify-github-platform
```

The command executes each repository's locked native validation and flake gate, verifies the
policy distribution, checks every producer/consumer workflow pin and permission contract, checks
the repository-home action pins against the policy-manifest digest, checks the generated adoption
dashboard, and writes JSON and Markdown reports under `.qualification/`.
That directory is ignored and contains no credentials.

The report has two independent verdicts:

- `source_qualification` covers only checked-in source and locally reproducible gates;
- `connected_qualification` covers GitHub runs, native runners, WIF, protected approvals, and
  release evidence recorded in `catalog/connected-qualification-evidence.yaml`.

A successful source verdict never changes a blocked connected verdict. `--skip-native` exists for
unit tests and report-development only; it deliberately makes source qualification fail.

## Adoption graph and dashboard

`catalog/workflow-adoption.yaml` records the producer implementation, candidate or released
reference, exact callers, permissions, and activation gates. `docs/workflow-adoption.md` is
generated from that contract:

```sh
python3 scripts/render-workflow-adoption.py --write
```

Normal validation rejects stale output, changed caller permissions, missing producer commits,
blocked callers that no longer fail closed, and consumer references that differ from the graph.

## Connected evidence

Connected records are append-only review evidence, not copied workflow logs. Each record binds an
exact run URL, source SHA, successful outcome, observation and expiry timestamps, reviewer, and
SHA-256 evidence digest to one activation gate. Records may live for at most 90 days. A gate marked
`qualified` without at least one unexpired successful record fails local validation.

Before changing a gate to `qualified`:

1. retain the protected run and restricted evidence object;
2. independently verify the source SHA, workflow identity, outcome, runner or WIF boundary, and
   digest;
3. add the evidence record and gate transition in the same reviewed pull request;
4. regenerate the adoption dashboard and run the workspace qualification command.

Expired evidence closes the source contract on the next validation run. Renew evidence by running
the protected qualification again; never extend a timestamp on an old observation.

## Immutable pin upgrades

`scripts/upgrade-workflow-pins.py` is read-only by default. It refuses to prepare changes until
v5 is recorded as published with an exact source commit, all consumer gates are qualified, and
their connected records are fresh. The protected `Prepare immutable workflow upgrades` workflow
then changes only graph-declared caller references, runs both consumer flake checks, and opens
draft review pull requests with compatibility evidence.

The `mindclade-workflow-pin-updater` App is selected only to `.github-private` and
`github-config`, with Contents write, Pull Requests write, and Metadata read. Store
`WORKFLOW_PIN_UPDATER_APP_PRIVATE_KEY` only in the protected `governance` environment. Merge the
`.github-private` consumer first and the `github-config` caller/graph PR second; qualification
fails closed if the coordinated state drifts between merges.

## DR activation

`scripts/prepare-workflow-activation.py` verifies the blocked caller by default. `--write` is
accepted only after the v5 release and release-environment gates are qualified with fresh evidence.
The protected `Prepare DR workflow activation` workflow generates the exact caller and opens a
draft PR. It never activates the caller directly, changes an environment, or bypasses review.
