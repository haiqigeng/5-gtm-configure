# CMP and consent gating

## Contents

- [Default to strict/basic gating](#default-to-strictbasic-gating)
- [Distinguish observation from gating](#distinguish-observation-from-gating)
- [Research the installed CMP](#research-the-installed-cmp)
- [Route identified CMP platforms](#route-identified-cmp-platforms)
- [Route TCF conditionally](#route-tcf-conditionally)
- [Build a safe vendor block](#build-a-safe-vendor-block)
- [Select advanced/native consent only explicitly](#select-advancednative-consent-only-explicitly)
- [Handle page-view timing](#handle-page-view-timing)
- [Handle business events that precede CMP readiness](#handle-business-events-that-precede-cmp-readiness)
- [Handle revocation without overclaiming](#handle-revocation-without-overclaiming)
- [Validate the final decision](#validate-the-final-decision)

## Default to strict/basic gating

Unless the analyst explicitly requests and approves advanced/native consent behavior, prevent every analytics and media vendor tag from loading or firing before the required consent is granted.

Use the smallest reusable set of CMP blocking/exception triggers that expresses the complete approved predicate. One vendor/platform block is preferred when one native state represents the grant; use additional shared category/purpose, product-consent, or initialization blocks when those are independent required grants. Apply the complete set to the vendor's base/configuration and event tags in scope. Make unknown, undefined, uninitialized, and denied state block.

Keep firing opportunity and consent eligibility separate. A verified CMP readiness/grant event may
be the normal trigger that lets a base/configuration or page-view tag run on initial or later grant;
it does not replace the reusable vendor block. Attaching both is intentional defense in depth and
keeps the tag protected if its normal-trigger lifecycle later changes.

Use a normal Custom Event trigger for the business action and a separate vendor block, for example:

- `CE - purchase`
- `Block - Didomi - Meta denied`

Do not repeat consent conditions inside every business trigger when a shared vendor block expresses the approved policy safely.

Under this strict/basic topology, leave Additional Consent Checks unset rather than adding a second
copy of the same consent predicate. Template-owned built-in consent checks remain visible and are
recorded separately; do not claim that they were removed. For explicitly approved advanced/native
behavior, use the documented consent defaults/updates and built-in behavior without a defeating
block or Additional Consent Check.

Design the normal-trigger lifecycle separately from the block. A page-load trigger that is blocked while consent is unknown or denied does not retry automatically. When a base/configuration tag must initialize after consent, use verified CMP readiness/grant events and an appropriate once-per-page control so both an initial grant and a later grant have a valid firing opportunity. Keep any page-view event and late-consent page-view policy separate from initialization.

## Distinguish observation from gating

Classify the final GTM logic:

| Mechanism | Counts as a gate only when |
| --- | --- |
| Built-in consent requirement | It prevents the tag from firing under the selected model, rather than only changing tag behavior. |
| Firing-trigger condition | It evaluates false for every denied and unknown firing path. |
| Blocking/exception trigger | It evaluates true for every denied and unknown firing path and wins over the normal trigger. |
| Consent-aware/native advanced behavior | It intentionally allows documented limited or cookieless execution under denied state; describe it as advanced consent behavior, not strict blocking. |
| Observation only | It reads, displays, logs, or transmits consent state without preventing firing. This is not a gate. |

Never report a tag as strictly gated merely because its template lists built-in checks or a consent variable resolves in Preview.

## Research the installed CMP

Before creating a condition:

1. Open the current official CMP documentation for the installed product/version and GTM integration.
2. Identify separately the CMP initialization/readiness events, consent-change events, state variables/cookies/APIs, vendor identifiers, and value format.
3. Obtain the approved site/CMP signal contract and representative values before initialization, after denial, and after grant.
4. Establish event frequency, ordering, state lifetime, and returning-choice behavior from that contract.
5. Confirm the exact category/purpose and vendor identities used by this site.
6. Prove from GTM filter semantics that undefined state is expected to remain blocked. Treat a supplied value outside the CMP's documented format as an integration defect and block the affected design until the source contract is corrected or authoritatively clarified.

Do not infer that similarly named CMP events and variables have the same role. For Didomi, for example, establish readiness/change events independently from enabled-vendor state. Use the exact category/purpose and vendor identities documented and supplied for the site. Do not append a delimiter by convention; when the CMP serializes a delimited list, match the exact token format established by official documentation and the approved representative value.

## Route identified CMP platforms

When the CMP is OneTrust, Didomi, Axeptio, or another identifiable platform, load
`cmp-platform-patterns.md` after this general contract. Use its discovery route but keep the exact
installed template, site deployment, vendor/category/purpose IDs, and current official lifecycle as
the authority. Never copy one client's category IDs or another CMP's event names.

## Route TCF conditionally

Load `tcf-consent.md` only when the approved site/CMP architecture actually uses IAB Europe TCF.
Use the current TCF 2.3 route and the CMP's documented TC/Additional Consent plumbing. Do not select
purposes, legal bases, vendors, publisher restrictions, or CMP certification on the client's
behalf, and do not add TCF machinery to a non-TCF consent implementation.

## Build a safe vendor block

Define the exception's event scope before its consent-state condition. A shared block must be able to activate on every GTM event used by each consumer tag; a condition that reads the right CMP value is ineffective on an event the trigger does not match. In a Custom Event-first design, default a vendor-wide block to a verified `.*` Custom Event regex rather than repeating the current event-name inventory or using a CMP-only event name. Use a narrower matcher only when the block intentionally serves a documented consumer subset, and record that reason. If a consumer uses an event type the shared block cannot cover, stop and redesign the exception scope before claiming strict gating.

Inspect tag sequencing separately. GTM tags invoked as setup or cleanup tags ignore their own firing and blocking triggers. Do not rely on the sequenced tag's exception: make the initiating tag's complete predicate prevent the sequence under unknown or denied consent, and prove the expected static path from the configured references.

Use the documented CMP state variable directly in the blocking trigger whenever a native GTM filter can express the policy safely. For a vendor-enabled list, the default pattern is one negative condition:

    {{DLV - <CMP enabled vendors>}} does not contain <exact documented vendor token>

Derive the DLV key, operator, category/purpose and vendor token, delimiter, case, and value type from current CMP documentation and approved representative values. For a CMP that exposes a documented Boolean or keyed state, test that source directly. Avoid substring collisions by matching the exact documented token format.

GTM combines multiple filter rows inside one trigger with logical AND, while any matching blocking trigger prevents its consumer tag. Do not add mutually exclusive denial rows to one trigger. Use one documented native condition whose negative result covers every non-granted state when one signal represents the complete grant. When independent required grants each need OR-denial behavior, use separate reusable blocks or another officially supported native representation. Do not create a Custom JavaScript, JavaScript, lookup-table, or Boolean consent helper when documented CMP variables can be tested directly.

If the official CMP contract cannot be represented safely with a native GTM condition, mark the affected consent design `Blocked` and request an authoritative CMP signal or approved architecture. Do not invent a parser or helper variable to compensate for an undocumented source shape.

Test the block against similar vendor IDs and another-vendor-only consent. Do not combine different platforms in one block. If one platform is represented by multiple verified CMP identities, document their exact Boolean logic inside that platform's block.

## Select advanced/native consent only explicitly

Treat advanced consent as an architecture change because tags may execute and transmit limited data under denied consent.

Do not treat this as a Google-only decision. Load the vendor consent-mode capability reference and classify the exact browser product. Google tag/GA4, Google Ads, Floodlight, Conversion Linker, Microsoft Advertising UET, Microsoft Clarity, and vendor-native adaptive analytics can have materially different supported behavior. A shared parent company or CMP category does not make the products equivalent.

Before using it:

1. Obtain an explicit request and approved client policy.
2. Verify current official product, installed-template, and CMP support.
3. Document denied-state tag loading, request fields, storage, transmission, data use, and modeling or reporting behavior.
4. Configure consent defaults before affected tags and updates immediately after the user's choice.
5. Avoid additional consent checks or exception triggers that defeat the intended advanced behavior.
6. Validate denied, granted, update, and revocation states.

If a non-Google vendor offers consent mode, native cookie control, anonymous collection, or another limited-data feature, follow that vendor's current documentation; do not assume Google Consent Mode semantics apply. Cookie suppression alone does not prove advanced denied-state measurement.

## Handle page-view timing

Page-view source events often occur before CMP state is initialized. Under strict/basic gating:

1. Identify an official CMP event with the required one-time readiness semantics.
2. Verify that it occurs after the state is readable.
3. Trigger the separate page-view tag from that event with the vendor block.
4. Revalidate from the approved source contract that every page-view value is current and available on that CMP event; do not assume an earlier event-scoped payload persists.
5. Define whether a later grant sends a page view.
6. Prevent duplicate initial and consent-change page views.

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

## Validate the final decision

For each vendor tag, derive the expected static result:

| Contract state | Strict/basic configured expectation |
| --- | --- |
| CMP not initialized or value undefined | Expected not to fire. |
| Required category/purpose or vendor denied | Expected not to fire. |
| Different vendor granted only | Expected not to fire. |
| Complete required grant and normal trigger occur | Eligible under the selected firing option. |
| Consent revoked | Later GTM invocations are expected to remain blocked; already-loaded behavior follows the documented configured limitation. |
| Consent granted after initial denial | The configured late-consent/page-view path matches the approved policy without a known duplicate. |

For a base/configuration tag, also prove statically that an initial grant and a later grant each have a valid configured initialization opportunity without repeated initialization.

For explicitly approved advanced behavior, replace the strict non-fire expectation with the exact officially documented limited-data configuration expectation and label it clearly. Do not present it as an observed request.

## Carry consent through a pipeline

Keep the web CMP lifecycle and vendor blocks unchanged for direct browser tags. For a transporter,
record whether it is blocked, always transports, or conditionally transports; do not attach the
downstream vendor block mechanically. Forward only an approved documented CMP state or native
Google consent signal.

For a non-Google server gate, prove denied, granted, and unknown state on every transported event
that can trigger the destination. State available only on page view does not protect a later
conversion. CMP readiness is not grant, and a consent-update event must not replay a business
conversion. Use one effective server mechanism and reject accidental equivalent double gates.
