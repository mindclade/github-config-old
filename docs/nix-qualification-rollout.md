# Nix qualification rollout

The `required-checks-nix` organization ruleset targets exactly the seven managed repositories
and expects the stable `nix / verdict` context. Its resting enforcement is `evaluate`.

## Activation gates

Keep the ruleset in evaluate mode until all of the following evidence has been reviewed:

1. An operator publishes the single immutable `.github` `v5.0.0` workflow release only after
   x86_64 Linux, aarch64 Linux, aarch64 Darwin, and independent rebuild evidence is attached.
2. Until that tag exists, existing consumer pins remain source candidates only. A reviewed
   follow-up moves every consumer to `@v5.0.0` only after the annotated tag resolves to the
   post-hardening release commit and its source attestation verifies.
3. Pull-request and merge-group runs emit `nix / verdict`, including pull requests with no
   Nix-owned changes.
4. Weekly runs complete on every declared native platform. Linux arm64 is required only for
   repositories that expose `aarch64-linux`; Apple Silicon is required for all seven.
5. The two isolated x86_64-linux rebuild jobs agree on derivation, store path, and SRI output
   hash for every repository-selected installable.

Promotion from `evaluate` to `active` is a separate reviewed catalog change. It must not be
combined with workflow publication or first-consumer adoption.

## Rollback

If the released workflow or hosted-runner fleet is unhealthy, return the ruleset to `evaluate`
or `disabled` through the reviewed enforcement override while preserving the immutable release
tags and collected evidence. Repair the workflow in a new semver release; never move a tag.

This check qualifies Nix host tooling. Bazel remains authoritative for monorepo build/test and
application-container graphs, and no NixOS, nix-darwin, Home Manager, or Nix image authority is
introduced by this rollout.
