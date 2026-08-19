# Other server analytics destinations

## Contents

- [Require an identified server product](#require-an-identified-server-product)
- [Inspect ingress and template](#inspect-ingress-and-template)
- [Preserve analytics authority](#preserve-analytics-authority)
- [Fail closed](#fail-closed)

## Require an identified server product

For Matomo, Piwik PRO, Adobe, or another analytics platform, identify the exact server collection
product and current official documentation. A supported web tag does not establish server support.
Do not invent a generic Measurement Protocol or arbitrary HTTP endpoint.

## Inspect ingress and template

Prove the incoming Client, Event Data shape, installed server tag/template, version, publisher,
permissions, network hosts, authentication method, consent behavior, and outgoing schema. Template
installation or permission expansion requires explicit authority.

## Preserve analytics authority

The approved tracking plan controls event meaning and fields. Current product documentation
validates feasibility and the server destination schema but cannot substitute valid semantics.
Keep source fields separate from template and vendor fields.

## Fail closed

If official server collection, supported GTM implementation, required credentials, or Event Data
mapping cannot be proved, mark only that route `Blocked` or `Deferred`. Do not fall back silently to
Custom HTML, browser JavaScript, or unapproved direct API code.
