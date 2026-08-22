## Change

Describe the governance outcome and the catalog, module, ruleset, identity, or workflow
boundary affected.

## Risk and authority

- Change class: low / medium / high / critical
- Managed objects affected:
- Identity, access, trust, visibility, or bypass impact:
- Destructive or replacement actions expected: none / list exact objects

## Validation evidence

List the exact commands run and their results. Include the speculative Terraform plan link
when the change affects managed GitHub resources.

```text
nix develop --command make validate
terraform init -backend=false
terraform validate
terraform test
```

## Rollback and recovery

State how to reverse the change without bypassing the authoritative repository. Critical
changes must include a tested recovery path and the incident/change record used for any
emergency exception.

## Checklist

- [ ] The change preserves one authoritative owner for every managed object.
- [ ] Required workflow job IDs still match required-check contexts.
- [ ] New Actions references are immutable-pinned and least-privilege permissions are explicit.
- [ ] No credential, private key, state, saved plan, or local Terraform cache is committed.
- [ ] Any access exception has an owner, approver, exact scope, reason, and expiration.


## Contributor authorization

- [ ] I am authorized under a current written agreement with Mindclade, LLC. to
      submit every part of this contribution.
- [ ] I identified every third-party component, dataset, model, font, media,
      specification, or generated artifact and preserved its source, license,
      provenance, and required notices.
- [ ] I updated `LICENSE`, `NOTICE`, the SBOM, or other license evidence when
      the included or distributed material changed.
