# ChatGPT Ads Conversions API

Apply the [server media framework](media-destinations.md) and reopen the current
[Conversions API](https://learn.chatgpt.com/ads/conversions-api) and
[supported events](https://learn.chatgpt.com/ads/supported-events). An API endpoint does not prove
an official GTM server template. Inspect an installed compatible implementation, actual fields,
permissions, credential handling, batching, response handling and retries before configuration.

Use the intended Pixel ID even for a server-only route. The ingestion endpoint is
`https://bzr.openai.com/v1/events?pid=...`, authenticated with a server-held Conversions API Bearer
key, not an advertiser administration key. Keep credentials behind the existing secret provider;
never place them in browser GTM or evidence. Account/key administration remains external.

Map original occurrence `id`, `type`, `timestamp_ms` and `data`; website events require the
documented `action_source: web` and `source_url`. Inspect current age/future-skew and batch limits.
Use integer currency minor units and preserve complete content arrays. Browser initialization
user fields and CAPI per-event user fields differ; map the documented plural hash arrays with
explicit normalization/hash ownership. Preserve available original `oppref` and consented
`user.obref` when that route uses them. Do not regenerate timestamps or identifiers on retries.

Enforce the authorized incoming consent through the actual server implementation; do not treat
an opt-out field as proof of a firing gate. For overlapping delivery, CAPI `id` must equal Pixel
`event_id` for the same Pixel and event/custom name. Purchase needs retry-stable identity. A
server-only authorization records browser overlap as an external dependency and cannot certify it.

Saved configuration includes exact template/source/permission and field readback. It does not
certify HTTP acceptance, deduplication, attribution or reporting. Runtime requests and validate-only
API calls belong to separately authorized acceptance work.
