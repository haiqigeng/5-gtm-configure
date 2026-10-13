# Multi-destination and environment routing

## Contents

- [Purpose](#purpose)
- [Resolve the routing contract](#resolve-the-routing-contract)
- [Choose separation or deterministic routing](#choose-separation-or-deterministic-routing)
- [Protect environments](#protect-environments)
- [Handle Google tag destinations](#handle-google-tag-destinations)
- [Handle media destinations](#handle-media-destinations)
- [Verify routing](#verify-routing)

## Purpose

Use this playbook when one web container serves multiple analytics streams, advertising accounts,
pixels, datasets, brands, regions, hostnames, or deployment environments. The objective is to avoid
cross-destination leakage while keeping the smallest understandable object graph.

## Resolve the routing contract

For each independently owned destination, establish:

- stable product and destination identity;
- environment, hostname, brand, region, language, or business-unit selector;
- event schema and source timing;
- consent route and first-party-data policy;
- automatic/base-tag behavior;
- safe no-match behavior;
- business owner and future change path.

Do not infer production/staging or brand ownership from a hostname alone. Treat destination IDs as
approved inputs for media and confirmed configuration inputs for analytics.

## Choose separation or deterministic routing

Prefer separate base/configuration and event tags when destinations differ in schema, consent,
automatic behavior, ownership, or lifecycle. Prefer one LUT/RLT-backed graph when the destinations
share all of those semantics and differ only by a deterministic selector and destination identity.

Use a routing table only when:

1. every input case is real and approved;
2. match precedence is unambiguous;
3. the no-match result fails closed or is explicitly intended;
4. one output type is valid for every consumer;
5. the mapping reduces duplication without hiding ownership.

Never use a default production destination as the no-match value. Never place multiple unrelated
IDs in one constant or one broad Custom JavaScript router.

## Protect environments

Keep test, staging, QA, and development traffic out of production destinations unless explicitly
approved. Distinguish GTM Environments from business-hostname routing: an environment resource
controls a container deployment context, while a LUT/RLT can select a destination inside one saved
workspace configuration.

Creating or changing a GTM Environment is high-impact and requires explicit authority. This skill
may configure environment-aware objects but never publishes a version to any environment.

## Handle Google tag destinations

Inspect current Google tag configuration objects and linked destinations before deciding whether to
reuse one Google tag, create another configuration path, or use an officially supported destination
separation. Reconcile:

- tag IDs and measurement/destination IDs;
- connected GA4, Google Ads, and Floodlight consumers;
- inherited configuration and Event Settings variables;
- automatic page-view/event behavior;
- Conversion Linker and cross-domain needs;
- basic versus explicitly approved advanced consent routes.

Do not link, move, or detach a Google destination as an incidental implementation step. Current APIs
and UI capabilities change; discover the exact supported action and obtain explicit authority.

## Handle media destinations

For multiple pixels, datasets, accounts, or conversion actions, keep destination identity separate
from event semantics. Reuse one mapped tag only when the installed template supports a variable
destination field and every routed target has the same event contract, consent, matching policy,
catalog convention, and owner. Otherwise use separate readable tags with compatible shared source
variables and triggers.

Never assume that the same product identifier is valid across media catalogues. Route catalog/feed
identity separately when required.

## Verify routing

Read back every selector, mapping row, no-match value, destination reference, consumer, consent
route, and environment condition. Use static vectors covering every approved route plus unknown,
empty, and overlapping inputs. Confirm that no route can send test traffic, first-party data, or an
event to an unintended production destination and that an identical rerun makes no change.

## Route tagging endpoints by environment

When web senders use different server endpoints, route by an approved stable environment or host
with an explicit no-match result. Unknown traffic must never fall through to production. Record the
endpoint owner, all sender consumers, and the receiver target for every route. Endpoint cutover is
high impact and occurs only after the corresponding server graph is read back and verified.

Do not confuse one server endpoint with one destination: one claiming Client event may fan out to
several server tags, while one web container may intentionally use more than one receiver only when
the architecture and environment isolation require it.
