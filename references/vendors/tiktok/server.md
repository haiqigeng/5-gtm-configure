# Server TikTok Events API

## Route

TikTok documents an Events Manager setup for GTM web and server containers. Inspect the exact
generated/installed templates and all automatic tags, variables, permissions, hosts, and dedup
behavior; do not reproduce the setup from memory. Record Pixel code, event, context, user matching,
properties/items, access token, consent, and outgoing diagnostics.

The vendor flow may configure Pixel and Events API together and automatically create an `event_id`.
Prefer and inspect that owner. For another approved setup, one shared browser/transporter ID may be
used only when approved input provides its stable occurrence source. Product support for CJS does
not authorize deriving identity from undocumented GTM internals.

Official sources:

- https://ads.tiktok.com/help/article/how-to-set-up-events-api-for-server-side-tagging-in-google-tag-manager
- https://ads.tiktok.com/help/article/event-deduplication

Fail closed when the generated integration surface, token, Pixel identity, consent, event mapping,
or automatic/manual dedup owner cannot be proved.
