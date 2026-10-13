# Server Criteo

## Route

Identify the exact Criteo product, market, account program, and documented server/API integration.
Do not treat OneTag, Commerce Growth, Retail Media, an Event API, or another Criteo product as
interchangeable. The media brief or account team must name the server product.

Then inspect the exact official schema and installed GTM server template: publisher/version,
permissions/hosts, authentication, event/product identifiers, basket cardinality, user matching,
consent, browser overlap, and outgoing response. Never infer a generic Criteo CAPI.

Official discovery entry point: https://developers.criteo.com/

If the exact product documentation and supported GTM route are absent, mark the route `Blocked` or
`Deferred`; fail closed rather than creating a generic HTTP request or repurposing OneTag fields.
