# Media tags

## Select the vendor guide

Load the named product and delivery surface:

[Affiliate](../vendors/affiliate/web.md), [Chatgpt Ads](../vendors/chatgpt-ads/web.md), [Criteo](../vendors/criteo/web.md), [Floodlight](../vendors/floodlight/web.md), [Google Ads](../vendors/google-ads/web.md), [Linkedin](../vendors/linkedin/web.md), [Meta](../vendors/meta/web.md), [Microsoft Ads](../vendors/microsoft-ads/web.md), [Pinterest](../vendors/pinterest/web.md), [Reddit](../vendors/reddit/web.md), [Snapchat](../vendors/snapchat/web.md), [Tiktok](../vendors/tiktok/web.md), [X](../vendors/x/web.md).

The media brief owns business intent and destination use under [authority](../core/authority.md).
An analytics plan can supply reusable source events; the exact media product owns its destination
schema. This guide owns media-specific declarations. [Template governance](../templates.md),
[data mapping](../data/mapping.md), [identity](../data/identity.md), and
[consent](../consent/web.md) own their respective implementation rules.

## Establish the media contract

Discover installed destination IDs, templates, source variables, triggers, CMP objects, routing and
initialization. Resolve remaining feature-specific blockers together using these inputs:

| Decision | Required declaration |
| --- | --- |
| Business action | Approved action, exact success moment, and optimization, reporting, remarketing, catalog or audience purpose. |
| Destination | Exact browser product, account/pixel/tag/dataset identity, environment and platform-side conversion object when applicable. |
| Event | Exact name, standard/custom status, eligibility and applicable naming limits from current official product documentation. |
| Field | Exact browser parameter, required/conditional/approved-optional status, type and event/item cardinality. |
| Source | Approved key or literal, evidence grade, type, availability, timing and lifetime. |
| GTM mapping | Resolution method and exact installed-template field/type, separately identified from the source and network parameter. |
| Catalog | Feed/business vertical and explicit product/variant/item-group identifier convention when applicable. |
| Consent and identity | Approved CMP policy and any explicitly selected matching/user-data feature. |
| Evidence | Official product URL/title/access date, source locator and inspected template/version. |

Current official documentation establishes the destination contract; the installed template
establishes available fields and execution behavior. [Evidence review](../core/evidence.md) resolves
disagreement before authoring. Required declarations determine readiness through the existing
[field and dependency model](../core/execution.md#contain-failures-by-dependency).

## Select event semantics and initialization

Prefer a current standard event whose documented meaning matches the business action. A custom
event needs a distinct approved meaning or product requirement and vendor support. Confirm its
reporting/optimization eligibility and any platform-side conversion setup.

Give each approved initialization and page-view occurrence one effective owner across GTM,
site code, partner/CMS integrations and automatic template behavior. Establish existing ownership
from the container and supplied evidence; record unknown outside-container behavior as an external
dependency. Create initialization only when required and uncovered by a compatible existing path.
Base tags carry documented initialization/shared settings. Business events have their own approved
success triggers. A template's inherent page-load event counts as the page-view owner; manual
page-view delivery is selected against that complete ownership picture.

Inspect automatic detection and Event Builder behavior alongside manual events. Configure the
selected collection scope through the [template lifecycle](../templates.md).

## Map fields and execution

Apply [data mapping](../data/mapping.md) to each terminal template field, including exact item
cardinality and catalog identity. Use [transformations](../data/transformations.md) for necessary
shape conversion and its static vectors. The source contract owns runtime completeness; an
approved payload-related firing condition is represented independently from consent eligibility.

[Web execution](../web/execution.md) owns trigger/lifecycle declarations;
[web consent](../consent/web.md) owns strict/basic versus explicitly approved product-native behavior.
[Identity](../data/identity.md) owns matching authorization, accepted fields, timing and hashing.
[Routing](../routing.md) owns multi-pixel/account/brand/region/environment selection.

## Record external platform dependencies

Record applicable work outside GTM: conversion actions/labels/goals, optimization eligibility,
audiences, account activation, catalogs and ownership, automatic/partner installations, matching
terms and data sources, publication and platform administration. Classify each dependency as
confirmed, separately authorized, required external work, intentionally untouched or blocking.
Platform-object existence requires its own evidence, independently of the configured browser tag.

## Cover an unlisted product

Use the same media contract with current official browser implementation, event/parameter,
consent, matching and GTM/template sources. Inspect the installed implementation against that
contract. A dedicated vendor guide supplies useful product decisions; the common declaration and
implementation owners apply equally when that guide is absent.

## Verify and hand off

Apply [saved-state verification](../core/execution.md) and [acceptance](../core/acceptance.md).
Review product-specific destination/event fields, automatic behavior, initialization ownership,
source projections, triggers/consent, references and the no-op comparison. Record external platform
work separately from saved GTM proof.

## Choose the delivery surface

Classify each destination event as browser-only, server-only/replacement, documented dual delivery
or template-native deduplication. Browser-only configuration maps an approved identifier when the
exact product and installed template support it. Server products use their own
[server media contract](server.md). Overlapping routes use the shared
[occurrence and deduplication contract](../pipeline/browser-server-deduplication.md).
