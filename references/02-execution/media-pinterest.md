# Pinterest Tag

## Contents

- [Resolve the brief](#resolve-the-brief)
- [Research the official GTM path](#research-the-official-gtm-path)
- [Configure base and events](#configure-base-and-events)
- [Ecommerce, matching, and privacy fields](#ecommerce-matching-and-privacy-fields)
- [Verify](#verify)

## Resolve the brief

Require the Pinterest business/ad account use, exact Tag ID, business action, conversion/audience
objective, source event, catalog convention when applicable, and environment. Establish whether the
platform or team already created GTM objects through a partner flow.

## Research the official GTM path

Open https://help.pinterest.com/en/business/article/google-tag-manager-and-pinterest-tag and the
current linked event/reference pages. Inspect the installed Pinterest template version, fields,
base/event behavior, sequencing options, and automatic behavior before design.

## Configure base and events

Reuse one compatible base path per Tag ID/environment. Create an event tag only for a current
official Pinterest event or an explicitly supported custom path. Reconcile base-before-event
sequencing, page-visit behavior, partner-created objects, and existing site code.

Map exact source values to visible template fields. Do not copy GA4 names, recommended parameters,
or item structures into Pinterest without current official support.

## Ecommerce, matching, and privacy fields

For product audiences or ecommerce, prove the catalog product-ID convention and current single or
multi-item schema. Preserve every approved item. Require the source for each design-time required
identifier before mutation, then map runtime values directly. Use the deterministic transformation
playbook when a direct source array is incompatible; do not add a payload-eligibility helper.

Enhanced matching, event IDs, custom parameters, or limited-data-processing fields require an
explicit brief, current accepted format, source approval, and consent. Do not invent geography,
hashes, event IDs, or opt-out values.

Default strict/basic CMP blocking. Use Pinterest native stop/hold or another route only when
explicitly selected and currently documented for the exact browser product.

## Verify

Read back Tag ID, base/event separation, official event, full parameters, product arrays, matching
and privacy fields, sequencing, triggers, consent, template version, folder, and references. Record
Pinterest account conversion setup, catalog/feed work, Test Events, runtime receipt, and publication
as external dependencies.

## Server route

For Pinterest Conversions API, load `server/media-pinterest.md`. Prove token handling, current
required `event_id`, source, user-data hashing, contents projection, and Tag+CAPI overlap.
