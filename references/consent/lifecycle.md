# CMP lifecycle and transport

## Handle page-view timing

[GA4 ownership](../analytics/ga4-ownership.md#assign-exactly-one-page-view-owner) selects the
collector for each destination/occurrence. Under strict/basic gating, give that owner a verified
CMP readiness/grant opportunity and its complete eligibility predicate. Record whether a later
grant should produce the initial view, and provide that opportunity where required. Resolve all
page fields freshly on the chosen event. Repeatable consent-change events require explicit state
and duplicate handling; initial load and SPA virtual views have separate occurrence domains.

One-time initialization and legitimate virtual views retain their own lifecycles. Reconcile
Enhanced Measurement/history and other automatic collectors as part of page-view ownership.

## Handle business events that precede CMP readiness

Consent eligibility is evaluated at an invocation; event recovery needs its own approved mechanism.
Select the first feasible authorized route:

1. The site emits the business event after CMP readiness with its complete fresh payload.
2. The application emits a later semantically equivalent event with its complete fresh payload.
3. Approved one-time replay preserves the exact occurrence/payload, verifies consent at replay and ensures one delivery.
4. Otherwise the site/dataLayer owner supplies the required mechanism as an external dependency.

A Trigger Group records member-trigger occurrence. Payload retention, event-model restoration and
exactly-once recovery require the selected route's independent evidence.

## Handle revocation

Exceptions govern later GTM invocations. Already-loaded scripts and previously sent data retain
their documented lifecycle. Inspect native disable/revoke, automatic events, storage and any required
reload/site action. Required immediate-unload behavior needs a supported implementation; unresolved
capability holds that requirement. State the configured limitation precisely in the handoff.

## Carry consent through a pipeline

A transporter declares blocked, unconditional or conditional transport according to its approved
purpose. Forward the approved documented CMP state or native Google signal. Direct browser tags
retain their own policy. Each server-triggering event carries enough state to distinguish granted,
denied and unknown; readiness and business occurrence remain distinct signals. Apply the selected
single effective [server consent mechanism](server.md) to the receiving consumers.
