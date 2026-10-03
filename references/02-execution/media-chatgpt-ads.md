# ChatGPT Ads Measurement Pixel

Use the approved media brief to establish Pixel ID, business action, source event, value units,
consent and any matching scope. Account setup, conversion settings and campaign attachment remain
external dependencies. The browser Pixel requires no API key.

Reopen the current [Pixel documentation](https://learn.chatgpt.com/ads/measurement-pixel),
[supported events](https://learn.chatgpt.com/ads/supported-events), and
[conversion tracking](https://learn.chatgpt.com/ads/conversion-tracking). Cart additions use
`items_added`, purchases `order_created`, leads `lead_created`, and registrations
`registration_completed`; choose from current product semantics rather than copying GA4 names.
Amounts are integer currency minor units with currency, not necessarily cents. Preserve every
approved content item and quantity; `group_id` and `variant_dict` are CAPI-only.

Inspect and reuse a compatible installed template before the
[official OpenAI web template](https://github.com/openai/ads-measurement-pixel-gtm-template).
Bind its observed native type, fields, exact source/version and permissions. Import/update authority
is separate from using an installed template. Do not invent a native short code or bypass an
unsupported template with Custom HTML.
The official source's static injectScript cache key is not authentication. If its credential-shaped
constant name needs classification, use the exact inspected-source provenance described in
[template governance](template-governance.md); never exempt the whole source from secret detection.

The inspected official template initializes in each event tag; a separate base tag is optional.
`sendEvent: false` means initialization only. Defaults send `page_viewed`, so explicitly select
`sendEvent` and `eventName` for the requested occurrence. Actual fields include `pixelId`,
`eventId`, `amount`, `currency`, `contents` and `optOut`. Inspect the complete contents-table mapping:
a SIMPLE_TABLE is not proof that an arbitrary runtime whole-array variable is supported. Block
unsupported cardinality rather than truncate items or modify vendor code without authority.

`optOut` is event metadata, not consent enforcement. The inspected template issues no consent
command and uses `measure`, not an isolated `measureSingle` route. The Pixel defaults to allowed
unless denial is set/stored; denial suppresses future events, later grant does not replay them,
and revocation removes its cookies. Establish the authorized CMP gate and an actually supported
consent-lifecycle owner. Do not claim the stock template handles that lifecycle. Multi-Pixel
dispatch also needs an inspected route, not assumed isolation.

Matching requires explicit scope and account-behavior inspection. Browser manual user data is
initialization-scoped; the template's fields do not cover every SDK field. Inspect normalization
and hashing ownership. In the reviewed source `zipCode` emits `zip_code`, while current SDK docs
specify `postal_code`; leave that mapping unverified until reconciled. Preserve SDK-owned `oppref`
and browser-cookie capture rather than adding redundant helpers.

For dual delivery, browser `event_id` and CAPI `id` share one occurrence source, Pixel and event
(including custom event name). Use approved retry-stable purchase identity and the existing
[shared-ID route](pipeline/browser-server-deduplication.md) for supported other occurrences.
Web-only sender preparation records the external receiver. Saved readback proves native field,
template, consent-gate and identity configuration, not SDK execution, delivery or attribution.
