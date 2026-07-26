# Floodlight and Campaign Manager 360

## Contents

- [Authority and inputs](#authority-and-inputs)
- [Research the current Floodlight architecture](#research-the-current-floodlight-architecture)
- [Design the saved GTM graph](#design-the-saved-gtm-graph)
- [Map counter and sales activities](#map-counter-and-sales-activities)
- [Consent, linker, and shared Google tags](#consent-linker-and-shared-google-tags)
- [External dependencies and acceptance](#external-dependencies-and-acceptance)

## Authority and inputs

Require an explicit media brief and the exact Campaign Manager 360/Floodlight identities needed by
the activity. Establish the Floodlight configuration ID, activity group and activity tag strings,
counter or sales type, counting method, intended optimization/audience use, and required custom
Floodlight variables. Treat activity creation and trafficking settings as platform-side inputs.

## Research the current Floodlight architecture

Open current official Campaign Manager 360 and GTM documentation for the exact browser tag format.
Inspect linked Google destinations, pushed/approved Floodlight activities, existing Google tags,
Conversion Linkers, and the native Floodlight Counter/Sales or Google tag path.

Official entry points:

- https://support.google.com/campaignmanager/answer/7554821
- https://support.google.com/campaignmanager/answer/3183388
- https://support.google.com/campaignmanager/answer/4599566
- https://support.google.com/tagmanager/answer/3374209

Do not reconstruct a pushed activity from memory or silently replace its current official/native
format. A Campaign Manager link request or Approval Queue action is external/high-impact unless
explicitly included.

## Design the saved GTM graph

Prefer the current recommended Google tag/native Floodlight architecture when supported by the
container and approved activity. Reconcile one site-wide Google tag, activity tags, existing iframe
or image implementations, automatic Google tag loading, and shared Ads/GA4 destinations before
creating another configuration path.

Build constants only for stable reusable configuration/activity identifiers when that improves
ownership. Keep `src`, group/type, activity/category, counting method, and every custom variable
distinct. Do not concatenate them into an opaque helper string unless the installed template
requires the official combined field.

## Map counter and sales activities

For counter activities, establish the current counting method and every required parameter. For
sales activities, establish revenue/value, currency where applicable, quantity, order/transaction
identity, and duplicate-counting expectations from the explicit brief and current official schema.

Map custom Floodlight variables only when the activity owns them. Never pass PII in custom
variables. Preserve valid zero, require design-time sources for required sales values, map runtime
values directly, and never invent an order ID or cache-busting value when the current Google
tag/template handles it.

For dynamic remarketing or product data, require the exact feed/catalog identifier convention and
project every approved item through the transformation playbook. GA4 item IDs are not automatically
Floodlight feed IDs.

## Consent, linker, and shared Google tags

Default to strict/basic CMP blocking. Apply the chosen route consistently to the Google tag,
Floodlight activity, and Conversion Linker consumers. Use advanced Consent Mode only after explicit
approval and current Floodlight-specific proof. Reconcile `ad_storage`, `ad_user_data`, and
`ad_personalization` when applicable without adding user-provided data automatically.

Load the Conversion Linker/cross-domain playbook for attribution or multi-domain journeys. Do not
add a second linker or a basic block that defeats an approved shared advanced Google route.

## External dependencies and acceptance

Record Campaign Manager activity creation, configuration linking, custom-variable definitions,
dynamic-tag settings, enhanced attribution, and platform validation separately. Read back the
Google/Floodlight tags, exact identifiers and fields, triggers, consent, linker, variables, folder,
and references. `Configured` proves the saved workspace objects, not activity approval, platform
receipt, counting behavior, or publication.
