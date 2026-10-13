# Server first-party data and secrets

## Contents

- [Trace the complete consumer route](#trace-the-complete-consumer-route)
- [Scope user data](#scope-user-data)
- [Own normalization and hashing](#own-normalization-and-hashing)
- [Keep credentials ephemeral](#keep-credentials-ephemeral)
- [Verify without comparing secrets](#verify-without-comparing-secrets)

## Trace the complete consumer route

Record:

```text
approved source → web normalization/hash owner → transported field → claiming Client
→ server Event Data → scoped redaction/augmentation → destination template
```

For each consumer, name business approval, consent, raw/pre-hashed state, wire/Event Data path,
destination field, external activation/terms dependency, and fields withheld from other consumers.

## Scope user data

Do not attach `user_data` globally because one destination can consume it. Bind it to approved
events and consumers. Google documents common nested `user_data.*` Event Data paths; this does not
authorize sending those fields to every template. Use a narrowly scoped Transformation when an
unrelated destination must not see them.

## Own normalization and hashing

Follow the current destination's official rules for normalization, country/phone formatting, and
SHA-256 ownership. Do not hash twice. Record whether the web variable, server template, or another
approved owner performs the step. Never use hashed user data as a general analytics dimension.

## Keep credentials ephemeral

API tokens, authorization keys, secrets, and private keys enter a mutation only through a secure
ephemeral provider or approved secret-capable template field. Store safe references or
`present-not-compared`, never literal values, in contracts, baselines, fixtures, diffs, errors,
Markdown, or configuration results. Redact exact template paths before heuristic detection.

## Verify without comparing secrets

Prove that the intended secret field is populated and that all non-secret fields match. Never treat
two redacted markers as equality. A secret rotation/version reference can establish intended
ownership; runtime authentication remains a server recette dependency.

Official Event Data entry point:
https://developers.google.com/tag-platform/tag-manager/server-side/common-event-data
