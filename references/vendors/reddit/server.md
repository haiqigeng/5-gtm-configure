# Server Reddit Conversions API

## Route

Use current Reddit CAPI and an inspected GTM server template. Record advertiser/pixel identity,
event type/time/source, click ID, match keys/hashing, products/value, consent, token, batching, and
response. Current official direct-integration guidance—not the browser Pixel schema—controls the
payload.

Reddit requires deduplication when Pixel and CAPI send the same occurrence. Verify current
`conversion_id`, event type, asset, and match-key requirements; no dedup contract is needed for one
integration type. Use one occurrence source and keep distinct events unique.

Official sources:

- https://ads-api.reddit.com/docs/v3/guides/programs/capi
- https://ads-api.reddit.com/docs/v3/guides/programs/capi/direct-integration

Fail closed on unknown token/template permissions, click persistence, required match keys, product
projection, consent, or conversion identity.
