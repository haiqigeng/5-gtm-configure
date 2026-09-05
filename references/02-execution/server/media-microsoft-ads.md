# Server Microsoft Advertising

## Route

Use the exact Microsoft Advertising Conversions API product and current official schema. A CAPI
endpoint alone does not prove a compatible GTM server template: inspect the installed template or
vendor/partner route, publisher, version, permissions, hosts, authentication, and mappings.

Record UET tag identity, business event, event time/source, click and browser identifiers, user
matching, consent, and item/value fields independently from the browser UET schema. Record Microsoft
ID Sync or another required client-side identity mechanism as a paired/external dependency.

For browser plus server overlap, use the same current product identifiers, event name, and shared
`eventId` only when current Microsoft documentation/template support it. Never invent a dataLayer
event named `microsoft_ads_consent_granted`; use the proved CMP lifecycle/state topology.

Official source: https://learn.microsoft.com/en-us/advertising/guides/uet-conversion-api-integration

Classify requirements by the selected use. Current Microsoft guidance requires ID Sync for
remarketing/audience building and recommends it for conversion quality; do not block conversion-only
configuration solely because an optional ID Sync enhancement is absent. Record that limitation and
the responsible external owner. Recheck this conditional requirement against the current guide.

Fail closed only for missing requirements of the chosen CAPI feature: account access, authentication,
supported template route, required identity/consent, and deduplication when delivery overlaps.
