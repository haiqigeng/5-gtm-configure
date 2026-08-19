# Server GA4 and the Google Analytics Client

## Contents

- [Build the vertical slice first](#build-the-vertical-slice-first)
- [Inspect the claiming Client](#inspect-the-claiming-client)
- [Configure GA4 destinations](#configure-ga4-destinations)
- [Handle additional data](#handle-additional-data)
- [Respect consent and duplication](#respect-consent-and-duplication)

## Build the vertical slice first

Before adding media server destinations, prove one complete Google vertical slice: web Google tag
endpoint → request → intended Google Analytics Client → generated Event Data → server GA4 tag →
saved readback. Only expand platform coverage after this stage is green.

## Inspect the claiming Client

The Google Analytics Client is installed by default in new server containers and often needs no
changes. Verify its type, priority, activation paths/IDs, claim behavior, and generated data.
Changing priority or activation is high impact. Do not create a second GA4 Client merely for one
web event tag.

## Configure GA4 destinations

Preserve the approved analytics event name and field semantics. Decide which measurement identity
the server tag sends to, whether it inherits Event Data automatically, and any controlled override.
Do not use server routing to silently redesign the tracking plan. Record GA4 property/admin work as
external.

## Handle additional data

Google documents configuration-level and event-level parameters on the web sender. Additional
parameters may require the GA4 Client to parse them before they become Event Data. Use direct Event
Data variables for other tags; use a Transformation to exclude a parameter from consumers only
when its scope is intended. `items` and nested `user_data` require exact path/shape proof.

## Respect consent and duplication

Set Consent Mode in the web container and let consent-aware Google server tags process transported
signals. Reconcile automatic/manual page view, Enhanced Measurement, and direct-browser GA4 hits so
one occurrence is not sent through two routes accidentally. Do not invent a generic CAPI `event_id`
rule for GA4.

Official entry points:

- https://developers.google.com/tag-platform/tag-manager/server-side/send-data
- https://developers.google.com/tag-platform/tag-manager/server-side/common-event-data
- https://developers.google.com/tag-platform/tag-manager/server-side/consent-mode
