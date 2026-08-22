# Mindclade · Agent operating guide

## Purpose and authority

This repository is the source of truth for GitHub Enterprise repositories, teams, access,
rulesets, environments, Actions policy, custom properties, and OIDC metadata. Read BLUEPRINT.md,
README.md, CONTRIBUTING.md, and catalog/ before editing. Reusable workflow implementation belongs
in .github.

## Working rules

- Human-authored policy belongs in catalog; keep Terraform modules generic.
- Use team access by default. Temporary exceptions require an owner, reason, exact scope, and
  expiry.
- Treat custom-property, ruleset, identity, visibility, and protected-path changes as security
  changes.
- Never apply Terraform, alter live GitHub settings, refresh credentials, or widen access from an
  agent session. Plans and live applies use protected workflows and exact merged revisions.
- Do not print tokens, App keys, plan payloads, or sensitive drift output.

## Validation

    nix develop .#ci --command make validate
    nix develop .#ci --command make test
    nix flake check --no-update-lock-file

Live ruleset, IdP/SCIM, environment-reviewer, and drift qualification requires the approved
GitHub identity and remains distinct from source validation.

## Done

Catalog schemas and access expiry pass, tests pass, affected governance and rollback are
documented, and source results are not presented as live-system evidence.
