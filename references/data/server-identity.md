# Server first-party data and secrets

## Trace the complete consumer route

Apply [identity](identity.md) for feature authority, normalization/hash ownership, permitted values
and consumer scope. Inspect the receiving path for each approved consumer:

```text
approved source → web normalization/hash owner → transported field → claiming Client
→ server Event Data → scoped redaction/augmentation → destination template
```

Record business approval, consent, raw/pre-hashed mode, wire/Event Data path, destination field,
external activation/terms and the exact consumer set. Common `user_data.*` Event Data paths describe
available data. A scoped Transformation restricts availability to authorized consumers where the
source event otherwise exposes it to unrelated destinations.

## Preserve credential custody

Tokens and private keys use supported secret/template fields through secure ephemeral input.
[Execution privacy](../core/execution.md#handle-secrets-without-false-equality) owns redaction,
exact-path handling, presence-only proof and persisted evidence. Verify non-secret field equality
and secret presence/ownership; authentication remains a server field-test dependency.

Official Event Data entry point:
https://developers.google.com/tag-platform/tag-manager/server-side/common-event-data
