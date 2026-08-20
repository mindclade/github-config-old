# Engineering Onboarding

Access is provisioned through the corporate identity provider and mapped into GitHub teams. Do not grant repository access directly to individuals.

1. Create or activate the corporate identity.
2. Assign approved IdP groups.
3. Confirm GitHub Enterprise membership and expected team synchronization.
4. Verify least-privilege repository access.
5. Register phishing-resistant MFA and approved recovery factors.
6. Clone the internal monorepo:

```sh
gh repo clone Mindclade/mindclade-internal-monorepo
cd mindclade-internal-monorepo
```

Bootstrap, GitHub governance, production infrastructure, and security teams require separate approval. Membership in `engineering` alone does not grant access to `bootstrap` or `github-config`.
