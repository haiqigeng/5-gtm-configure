# Meta Pixel browser tags

## Contents

- [Resolve the Meta requirement](#resolve-the-meta-requirement)
- [Inspect current documentation and the installed template](#inspect-current-documentation-and-the-installed-template)
- [Configure initialization and events separately](#configure-initialization-and-events-separately)
- [Map ecommerce without assumptions or item loss](#map-ecommerce-without-assumptions-or-item-loss)
- [Keep payload mapping separate from firing](#keep-payload-mapping-separate-from-firing)
- [Select standard or custom events deliberately](#select-standard-or-custom-events-deliberately)
- [Configure advanced matching only explicitly](#configure-advanced-matching-only-explicitly)
- [Apply consent](#apply-consent)
- [Verify the saved Meta setup](#verify-the-saved-meta-setup)
- [Official entry point](#official-entry-point)

## Resolve the Meta requirement

Derive from the explicit media brief and relevant container state, or request only when missing and
critical:

- Meta Pixel/dataset ID and environment;
- requested business action and optimization, conversion, or audience use;
- current standard event or justified custom event;
- catalog identity and the exact product-ID convention for commerce events;
- required value, currency, order reference, item fields, and invalid-item policy;
- advanced-matching request and approved user-data sources, if any;
- CMP identity and the default strict/basic gate or explicitly requested native behavior.

Do not use a GA4 event name as the Meta destination name unless current official Meta documentation
gives it the same exact name and meaning.

## Inspect current documentation and the installed template

Before designing tags or variables, open the current official Meta Pixel browser event reference and
inspect native tag types and the exact installed GTM template version/repository. Use the compatible
supported installed template when available. If installation/update authority is missing, block the
tag family; do not substitute Custom HTML. Record only the applicable:

- standard/custom event spelling, casing, meaning, and limitations;
- required, recommended, optional, and conditional parameters;
- accepted number/string types, arrays, object keys, enums, and formats;
- catalog matching rules for content identifiers;
- template publisher, commit/version, fields, defaults, permissions, and automatic behavior;
- advanced-matching and consent capabilities.

Design against the installed version, not a newer upstream field. If Meta's official page is
temporarily unavailable, retry or use another official Meta source. Block a critical unresolved
schema decision rather than using a remembered event list or another platform's contract.

## Configure initialization and events separately

Ensure exactly one compatible Pixel initialization path. Reuse a compatible GTM tag, site code,
plugin, partner integration, or installed-template path. Create `Meta - Config` only when
initialization is part of the request and no compatible path exists.

Do not include `PageView` in a newly configured base tag by default. Create
`Meta - Event - PageView` only when requested and after reconciling hard-coded pixels, plugins,
automatic event setup, partner integrations, and existing tags.

Create separate business-event tags such as `Meta - Event - Purchase`, triggered from the approved
vendor-neutral Custom Event with the applicable Meta consent block.

## Map ecommerce without assumptions or item loss

Treat every current Meta parameter as an independent contract. When the official browser schema and
brief require them:

- return `content_ids` in its documented array form and retain every required identifier;
- return `contents` as an array of documented content objects and retain every required item;
- map each identifier to the actual Meta catalog convention;
- map or calculate value and currency only from an approved source and documented rule;
- preserve number versus string types, including valid zero;
- statically verify missing, empty, one-item, multi-item, zero, and invalid-type cases.

Do not assume analytics `item_id` is the Meta catalog ID. Do not synthesize `content_type`, default
currency, quantity, value, or another field merely because a template exposes it. Do not coerce a
numeric string unless the approved source rule explicitly permits that conversion.

Do not flatten or stringify arrays, select the first item, or silently drop an invalid item. Use a
direct DLV when it already has the exact terminal shape. Use `CJS - Meta - content_ids` or
`CJS - Meta - contents` only when a real shape conversion is required.

## Keep payload mapping separate from firing

Fire from the approved business event and map every authorized Meta browser field supported by the
installed template. Do not create `CJS - Meta - ... valid`, `CJS - Ecommerce - ... Eligible`, or a
second validity trigger merely because `contents`, `content_ids`, value, or currency can be absent at
runtime. Record that as a site/dataLayer dependency for recette.

Block configuration only when a required field has no approved source, compatible transformation,
or supported template field. Add a native firing condition only when the explicit Meta brief or
current official Meta browser documentation requires it; use CJS only when that required rule cannot
be represented natively.

## Select standard or custom events deliberately

Prefer a current official Meta standard event when its meaning matches the requested action and
intended platform use. Use a custom event only after checking current name and optimization
limitations and confirming the media-team requirement.

Do not assume that a browser custom event creates a Custom Conversion in Events Manager. Record that
platform-side dependency separately.

## Configure advanced matching only explicitly

Do not enable automatic or manual Advanced Matching by default. Require explicit approval, accepted
browser identifiers, controlled source fields, normalization/hash ownership, consent, and current
official/template support. Follow the first-party-data reference and do not use automatic DOM
collection when the approved design requires controlled dataLayer sources.

## Apply consent

Use strict/basic gating by default for the Meta base and every Meta event:

- attach `Block - <CMP> - Meta denied` or the smallest complete approved Meta block set;
- block unknown, undefined, uninitialized, and denied state;
- ensure each block's event scope covers every consumer event;
- preserve a valid initialization opportunity after an initial or later grant.

Use a native limited-data or consent feature only when explicitly requested and current official
Meta browser documentation plus the installed template proves the complete denied-state request,
storage, and data-use behavior. A consent checkbox or grant/revoke API alone does not prove advanced
measurement. Never infer Google Consent Mode behavior.

## Verify the saved Meta setup

Re-read the saved tags, variables, triggers, blocks, folders, and installed-template fields. Confirm
one initialization path, exact event name, destination ID, parameter types, item preservation,
browser-only field scope, consent route, firing option, references, and an idempotent rerun. Record catalog,
Custom Conversion, optimization, and publication dependencies separately and make no runtime claim.

## Official entry point

- https://developers.facebook.com/docs/meta-pixel/reference/

## Server route

For Meta Conversions API, load `server/media-meta.md`. Map CAPI independently, preserve complete
item cardinality, and record Pixel/CAPI overlap with one current Meta-documented occurrence ID.
