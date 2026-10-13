# Server X Conversion API

## Route

Use the current X Ads web-conversion/Conversion API product and an inspected GTM server template.
Record pixel/conversion-event identity, event time/source, click and user matching, item/value data,
consent, credentials, endpoint, and response diagnostics. Do not infer API support from a browser
Pixel implementation.

For browser and server overlap, verify current use of `conversion_id`, compatible event/conversion
identity, and all companion fields. Use one occurrence source across routes and never persist API
credentials.

Official source: https://docs.x.com/x-ads-api/measurement/web-conversions

Fail closed if the exact X product, account access, template publisher/hosts, field schema, consent,
or dedup mapping is not proved.
