# Server Meta Conversions API

## Route

Use Meta Conversions API official schema plus an inspected installed server template. Do not claim
that Meta provides an official GTM server template unless current evidence proves it. Record Pixel
ID, access-token owner, action source, event name/time/source URL, user-data fields/hashing, custom
data, item cardinality, consent, and outgoing response cues.

Map Meta fields from approved source values; GA4 names are not authority. Preserve every item when
projecting `items` to Meta `contents`, and prove catalog `content_ids` rather than assuming analytics
item IDs match the catalog.

For Pixel+CAPI overlap, follow current Meta dedup rules for matching event name and one shared
`event_id`. Purchase normally has an approved transaction/order identity; current Meta guidance
decides whether it is also the event ID or a companion custom-data field. The server never generates
a second ID.

Official sources:

- https://developers.facebook.com/docs/marketing-api/conversions-api/
- https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events/

Fail closed on unknown token handling, template provenance/hosts, user-data policy, item projection,
or dual-delivery identity.
