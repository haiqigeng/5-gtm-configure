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

Do not stop at an API-only search when the vendor documents a GTM integration. For example, check
[Piwik PRO's server GTM guide](https://help.piwik.pro/support/integrations/google-tag-manager-server-side-integration/)
and [Piano's implementation-method matrix](https://developers.piano.io/analytics/data-collection/general/implementation-methods/).
Prove which capability is being configured: serving a script, proxying a request, claiming Event
Data, or sending destination events. The first two do not by themselves prove the latter two.

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
