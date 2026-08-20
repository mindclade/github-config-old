# Enterprise reference module

This module is **not instantiated by the normal `github-config` root**. It documents provider
resources that may be adopted later in a separate Terraform state and protected workflow.

Do not connect it to the organization root or pass an enterprise-owner PAT through the normal
plan/apply pipeline. Adoption requires:

1. a separate state prefix;
2. a dedicated protected environment;
3. a short-lived or tightly controlled enterprise-owner credential path;
4. imports for existing enterprise and organization objects;
5. an exact post-merge plan/apply flow;
6. a tested owner-recovery procedure.

Until then, `docs/enterprise-manual-controls.md` is authoritative for enterprise-account
settings.
