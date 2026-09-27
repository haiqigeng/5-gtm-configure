# CMP lifecycle and transport

## Contents

- Handle page-view timing
- Handle business events that precede CMP readiness
- Handle revocation without overclaiming
- Carry consent through a pipeline

## Handle page-view timing

Page-view source events often occur before CMP state is initialized. Under strict/basic gating:

1. Choose the effective page-view owner using `google-field-ownership.md`: Google-tag automatic or
   explicit event, not both for the same occurrence and destination. Keep a correct existing owner
   during a narrow delta; prefer the analyst's explicit-event choice when it meets the requirements.
2. Identify the official CMP lifecycle opportunity and verify that its state is readable.
3. Give the chosen owner a verified CMP lifecycle firing opportunity and the required vendor block.
   Readiness alone may still mean unknown consent. If later grant must produce the initial view,
   prove a later firing opportunity too; a blocked one-time ready event does not retry itself.
4. Revalidate from the approved source contract that every page-view value is current and available on that CMP event; do not assume an earlier event-scoped payload persists.
5. Define whether a later grant sends a page view.
6. Prevent duplicate initial and consent-change page views.

Apply this lifecycle choice to page-load, page-view, and once-per-page work, not to purchase, lead,
cart, or other business events. For an SPA, once-per-page initialization must not suppress legitimate
virtual page views. Inspect Enhanced Measurement history collection and other automatic collectors
separately; `send_page_view: false` alone does not disable every automatic page-view source.

Do not attach a page-view tag to a generic repeatable consent-change event without an explicit state and duplicate policy.

## Handle business events that precede CMP readiness

A blocking trigger or Additional Consent Check evaluates only on the current GTM event; it does not
queue or replay a business event after consent becomes ready. Before configuring any business event
that can occur first, select the first authorized feasible route:

1. the site emits the business event only after CMP readiness, with its complete fresh payload;
2. the application emits a later semantically equivalent event with a fresh complete payload;
3. an explicitly approved one-time replay retains the exact payload, proves consent at replay,
   prevents duplicates, and preserves the original business occurrence semantics;
4. otherwise, record a site/dataLayer external dependency and do not claim the event will be
   recovered.

Do not use a Trigger Group as a replay queue. It records that member triggers have fired during its
lifecycle; it does not retain the original event payload, restore its event model, or establish a
safe exactly-once conversion.

## Handle revocation without overclaiming

A GTM exception can stop later tag invocations, but it does not unload a vendor script that already loaded after an earlier grant or erase data already sent. Inspect current vendor documentation and template behavior for native disable/revoke controls, automatic events, storage, and whether a page reload or site-level action is required. If the approved policy requires immediate unload behavior that the browser implementation cannot establish, mark the affected requirement `Blocked` and report the limitation. Record this as a configured limitation; never describe a loaded script as unloaded merely because subsequent GTM tags are blocked.

## Carry consent through a pipeline

Keep the web CMP lifecycle and vendor blocks unchanged for direct browser tags. For a transporter,
record whether it is blocked, always transports, or conditionally transports; do not attach the
downstream vendor block mechanically. Forward only an approved documented CMP state or native
Google consent signal.

For a non-Google server gate, prove denied, granted, and unknown state on every transported event
that can trigger the destination. State available only on page view does not protect a later
conversion. CMP readiness is not grant, and a consent-update event must not replay a business
conversion. Use one effective server mechanism and reject accidental equivalent double gates.
