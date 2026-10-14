# Multi-destination and environment routing

## Resolve the routing contract

For each independently owned stream/account/pixel/dataset/brand/region/environment establish exact
product/destination identity, approved selector, event schema/timing, consent and user-data policy,
automatic/base behavior, safe no-match outcome, owner and change lifecycle. Media identities are
approved inputs; analytics identities are confirmed configuration. Hostnames require explicit
mapping to their business/environment meaning.

## Choose separation or deterministic routing

Separate tags when schema, consent, automatic behavior, ownership or lifecycle differs. A shared
LUT/RLT graph fits destinations differing only by an approved deterministic selector and identity.
Each row has real approved inputs, unambiguous precedence, compatible output type, visible ownership
and tested behavior. Unknown/no-match resolves to a non-production outcome with an explicit policy.
Catalog/feed identity has its own mapping where destination conventions differ.

Media template routing also requires a supported variable destination field and identical event,
matching/catalog and consumer policy. Otherwise share compatible source variables/triggers between
separate destination tags.

## Protect environments and Google destinations

Approved environment routing isolates test/staging/QA/development traffic from production unless
explicitly assigned there. GTM Environment resources control deployment context; saved LUT/RLT
selectors control destination choice. Environment and destination-link changes use
[target authority](core/authority.md#target-authority).

Inspect connected Google/GA4/Ads/Floodlight consumers, effective settings, automatic ownership and
linker/domain requirements through [Google ownership](analytics/ga4-ownership.md) and
[Google consent](consent/google.md) before sharing an execution unit.

## Route tagging endpoints by environment

Each endpoint row records approved selector, explicit non-production no-match, endpoint owner,
senders and receiver target. A receiving Client can fan out to several destinations; multiple
receivers require their own architectural/environment purpose. Endpoint cutover follows authorized
[receiver-first ordering](pipeline/architecture-and-workflow.md#build-receiver-first).

## Verify routing

Read back selectors, rows, no-match, identity references, consumers, consent and environment scope.
Static vectors cover all approved routes plus unknown/empty/overlapping inputs. Expected destination
and first-party-data scope match each vector. Apply native comparison and no-op convergence.
