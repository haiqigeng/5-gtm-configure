# Server Pinterest Conversions API

## Route

Use Pinterest's current Conversions API schema and an inspected server template. Record advertiser
ID, conversion token/OAuth owner, action source, event name/time/source URL, user data, click ID,
custom data, contents/cardinality, consent/opt-out, and response. Never persist the token.

Pinterest currently requires an API `event_id` and supports Pinterest Tag plus CAPI. For overlap,
verify the browser `eventID`, server `event_id`, matching event name, asset, and exact source value.
Purchase/order identity may be the approved source, but current product rules control companion
fields.

Official source:
https://developers.pinterest.com/docs/track-conversions/track-conversions-in-the-api/

Fail closed when account/token ownership, template permissions/host, hashed user-data rules,
contents projection, or dedup fields are unproved.
