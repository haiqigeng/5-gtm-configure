# Server affiliate and partner routes

## Route

Require the named partner's current official postback/server-pixel/API contract. There is no
universal affiliate payload. Record program/account identity, endpoint, authentication, event,
order/lead identity, amount/currency, basket rules, attribution/click ID, consent, retry/response
behavior, and duplicate policy.

Use an installed supported server template only after inspecting publisher/version, permissions,
network hosts, secret fields, and exact partner schema. A generic HTTP Request or custom server
template requires explicit authority and is permitted only when the partner contract is complete
and no safer supported template exists.

For overlapping browser and server pixels, use the partner's documented replacement or shared
identity rule. Never infer it from Meta, GA4, or another network.

Without the exact official partner contract, credentials owner, supported GTM route, consent, and
dedup expectations, fail closed for that partner while preserving independent destinations.
