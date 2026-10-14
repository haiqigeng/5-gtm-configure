# Server Criteo

## Route

Identify the exact Criteo product, market, account program, and documented server/API integration.
OneTag, Commerce Growth, Retail Media and Event API each have their own product contract. The media brief or account team must name the server product.

Then inspect the exact official schema and installed GTM server template: publisher/version,
permissions/hosts, authentication, event/product identifiers, basket cardinality, user matching,
consent, browser overlap, and outgoing response. Establish that exact product's server capability.

Official discovery entry point: https://developers.criteo.com/

If the exact product documentation and supported GTM route are absent, mark the route `Blocked` or
`Deferred`; fail closed rather than creating a generic HTTP request or repurposing OneTag fields.
