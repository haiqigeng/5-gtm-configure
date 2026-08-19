# Server Snap Conversions API

## Route

Use the current Snap CAPI version and an inspected installed server template. Record Pixel ID,
endpoint/version, event name/time/source, click ID, hashed match data, custom data, items, token,
consent, and response. Do not use deprecated CAPI fields from an older version.

For Pixel+CAPI overlap, current Snap guidance distinguishes browser `client_dedup_id` from server
`event_id`. Purchase also distinguishes browser `transaction_id` and server
`custom_data.order_id`; current guidance may require both identifier pairs. Map one approved value
into each exact field and keep distinct occurrences unique.

Official sources:

- https://developers.snap.com/marketing-api/Conversions-API/Introduction
- https://developers.snap.com/marketing-api/Conversions-API/Deduplication

Fail closed on unproved CAPI version, template/host permissions, Pixel asset, token, event fields,
item projection, or cross-channel identity.
