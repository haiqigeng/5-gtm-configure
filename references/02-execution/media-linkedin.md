# LinkedIn Insight Tag

## Contents

- [Resolve the brief](#resolve-the-brief)
- [Research and template gate](#research-and-template-gate)
- [Configure base and conversion paths](#configure-base-and-conversion-paths)
- [Consent and sensitive pages](#consent-and-sensitive-pages)
- [Verify](#verify)

## Resolve the brief

Require the LinkedIn ad account/use, exact partner ID, base Insight Tag requirement, conversion or
audience objective, conversion identity or rule method, source event, and environment. Do not treat
“LinkedIn lead” as a complete implementation brief.

## Research and template gate

Open the current LinkedIn Marketing Solutions browser and tag-manager documentation. Inspect the
installed LinkedIn Insight Tag template, publisher, version, permissions, base/event capabilities,
and automatic behavior. Use https://www.linkedin.com/help/lms/answer/a418880 as an entry point and
follow the current conversion-tracking and compatible-tag-manager pages.

If the current official event path or installed template cannot express the requested conversion,
block it. Do not paste remembered Insight Tag code into Custom HTML as a shortcut.

## Configure base and conversion paths

Reuse one compatible site-wide base tag per approved partner/environment. Distinguish URL/rule-based
platform conversions from event-specific browser tags and configure only the method selected in the
brief. Keep the partner ID and any conversion identifier separate, map only currently documented
fields, and reconcile an existing site/plugin implementation before adding GTM.

Use a direct source mapping where possible. For ecommerce or value fields, apply the current
official LinkedIn schema. Require design-time sources before mutation and record runtime missing
values as a site/dataLayer and recette dependency; do not create a payload-eligibility CJS. Do not
translate GA4 event names or item arrays by analogy.

## Consent and sensitive pages

Default the base and event paths to strict/basic CMP blocking. Inspect current LinkedIn restrictions
for pages containing or revealing sensitive data and block configuration on prohibited or
unresolved page scope. Advanced matching or user data requires an explicit request, approved source,
current accepted fields, normalization/hash ownership, consent, and destination isolation.

## Verify

Read back partner/conversion identity, base/event separation, template/version, fields, triggers,
page/environment scope, consent, matching data, consumers, and duplicates. Record Campaign Manager
conversion creation, domain/source validation, audiences, runtime status, and publication as
external work.
