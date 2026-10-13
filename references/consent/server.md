# Server consent and data governance

## Contents

- [Record topology per destination](#record-topology-per-destination)
- [Apply the authority and gate matrix](#apply-the-authority-and-gate-matrix)
- [Handle Google consent natively](#handle-google-consent-natively)
- [Gate non-Google destinations](#gate-non-google-destinations)
- [Avoid double gates](#avoid-double-gates)
- [Limit data exposure](#limit-data-exposure)

## Record topology per destination

Record consent mode, transport behavior, exact web enforcement, exact server enforcement, signal
source, unknown-state behavior, event coverage, and any intentional double gate. Use one of these
server mechanisms:

- `incoming-google-consent-native`;
- `server-template-native-consent`;
- `server-additional-consent-check` only when the exact server tag/template exposes and requires it;
- `server-blocking-trigger`;
- `none`.

Do not treat these mechanisms as equivalent or stack them by default.

## Apply the authority and gate matrix

Classify each executing tag by role before choosing its consent control:

| Role and authority | Web firing/gate | Transported signal | Server destination gate |
| --- | --- | --- | --- |
| Direct browser destination under a third-party CMP | Business event, or documented CMP lifecycle event for a baseline tag, plus the reusable destination-vendor block | Not applicable | Not applicable |
| Web transporter under a third-party CMP | Functional event plus the approved browser-collection gate, if required; do not automatically copy every downstream vendor's block | Documented vendor state on every applicable event | One template-native gate or server blocking trigger; missing/unknown denies |
| Google destination with explicitly approved advanced Consent Mode | Current native Google consent behavior | Native Google consent parameters | Incoming Google-native behavior; no defeating additional block |
| Hybrid CMP plus Google Consent Mode | Classify each destination independently | Carry the authority required by that destination | Apply only that destination's declared authority |

The carrier is not the destination, but browser-to-server collection still needs its own approved
policy. Do not copy every downstream vendor's block onto a shared carrier or infer permission to
transport before choice merely because the final vendor is gated. Resolve the carrier's permitted
fields, timing, and consent independently. If the approved design prevents transport, record
`transporter_destination_vendor_block: true`, distinct gate roles, and any intentional double-gate
justification. Missing policy is an unresolved architecture decision, not automatic always-on transport.

For Google, native denied-state behavior is not a strict no-request gate. Do not label
`always-transported` plus `incoming-google-consent-native` as `strict-basic`. Use the approved basic
pre-transport eligibility or obtain explicit advanced/native authority; never silently change the
policy to satisfy the validator. Required native consent behavior can coexist with a basic external
eligibility gate because these mechanisms do different work.

Bind every active server destination tag to exactly one topology. Bind each server blocking trigger
to the saved tag, keep its ordinary Event Data event trigger separate, and prove that the same
documented CMP field reaches every event flow that can fire that destination.

## Handle Google consent natively

Configure Google Consent Mode in the web container. The Google tag adds consent parameters to the
request, the GA4 Client receives them, and consent-aware Google server tags adjust behavior. Do not
invent a second server Consent Mode implementation or map a non-Google vendor grant into Google
signals by analogy.

Official foundation:
https://developers.google.com/tag-platform/tag-manager/server-side/consent-mode

## Gate non-Google destinations

Forward only a client-approved documented CMP state field or product signal. Prove it on every
transported event that can fire the destination; a value only on `page_view` does not gate later
business events. Readiness is not grant. Unknown or absent state fails closed unless the approved
policy explicitly says otherwise. Never replay a conversion solely to carry new consent.

## Avoid double gates

A browser destination keeps its web vendor block under strict/basic policy. A transporter does not
automatically inherit that destination block; decide whether it must send so the server can receive
denied state. A server destination receives one effective vendor/purpose gate by default. If both
web and server gates are intentionally required, document distinct roles and the resulting event
coverage.

## Limit data exposure

Use scoped Transformations or destination-local mappings to prevent one destination from receiving
fields approved only for another. Treat raw/hashes of user data as controlled values. Record the
policy and technical owner without making legal decisions.
