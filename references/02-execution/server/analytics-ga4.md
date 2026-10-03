# Server GA4 and the Google Analytics Client

## Contents

- [Build the vertical slice first](#build-the-vertical-slice-first)
- [Inspect the claiming Client](#inspect-the-claiming-client)
- [Preserve client identification](#preserve-client-identification)
- [Configure first-party script serving only when requested](#configure-first-party-script-serving-only-when-requested)
- [Configure GA4 destinations](#configure-ga4-destinations)
- [Handle additional data](#handle-additional-data)
- [Respect consent and duplication](#respect-consent-and-duplication)

## Build the vertical slice first

For a Google transport, first prove the approved sender → request → intended Google Analytics
Client → Event Data slice. Add a server GA4 forwarding tag only when the approved destination
includes GA4. A media-only pipeline may consume that ingress without forwarding to a GA4 property.
For approved GA4 forwarding, verify Event Data → server GA4 tag →
saved readback. Only expand platform coverage after this stage is green.

## Inspect the claiming Client

The Google Analytics Client is installed by default in new server containers and often needs no
changes. Verify its type, priority, activation paths/IDs, claim behavior, and generated data.
Changing priority or activation is high impact. Do not create a second GA4 Client merely for one
web event tag.

## Preserve client identification

Read back the GA4 Client's **Cookies and Client Identification** setting and applicable cookie
options. Preserve the selected JavaScript-managed or server-managed strategy. A switch can change
user continuity and is a high-impact change requiring explicit authority, confirmed first-party
domain prerequisites, and a runtime continuity check. A server endpoint alone does not prove that
server-managed identification is suitable. See Google's [GA4 Client setup](https://developers.google.com/tag-platform/learn/sst-fundamentals/5-sst-setup-analytics).

## Configure first-party script serving only when requested

For an approved Google tag gateway request, distinguish CDN serving from serving through the
tagging server. Configure only the authorized GTM portion exposed by the installed Client: current
Google guidance uses the **Google Tag Manager: Web Container** Client with allowed web container
IDs, a distinct tag-serving path, and supported compression settings. Do not append that script
path to `server_container_url`, broaden allowed IDs, or change the GA4 event-ingress Client by
analogy. Inspect claim/path conflicts and preserve unrelated serving settings.

The website snippet, DNS, CDN/load balancer, server capacity and publication remain external
dependencies. Serving scripts first-party does not prove collection routing or consent behavior;
read back GTM settings and hand off separate script/network checks. See the
[tagging-server procedure](https://developers.google.com/tag-platform/tag-manager/server-side/dependency-serving?option=sgtm).

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
