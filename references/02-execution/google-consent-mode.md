# Google product-family Consent Mode

## Contents

- [Treat Consent Mode as broader than GA4](#treat-consent-mode-as-broader-than-ga4)
- [Choose the mode explicitly](#choose-the-mode-explicitly)
- [Verify consent types](#verify-consent-types)
- [Distinguish consent mechanisms](#distinguish-consent-mechanisms)
- [Implement the default basic route](#implement-the-default-basic-route)
- [Implement advanced mode only when approved](#implement-advanced-mode-only-when-approved)
- [Keep tag behavior and page views separate](#keep-tag-behavior-and-page-views-separate)
- [Configure every Google product consistently](#configure-every-google-product-consistently)
- [Record static consent assertions](#record-static-consent-assertions)
- [Official entry points](#official-entry-points)

## Treat Consent Mode as broader than GA4

Google Consent Mode is not a GA4-only feature. Current Google documentation lists built-in consent checks for:

- the Google tag;
- Google Analytics, including GA4;
- Google Ads Conversion Tracking and Remarketing, with Phone Call Conversions currently identified as pending support;
- Floodlight;
- Conversion Linker.

Verify this live list for every implementation. Decide basic or advanced behavior per destination/product, then reconcile those decisions with the actual Google tag and helper execution units. Treat every shared Google execution unit as one consent-controlled execution surface until current official capabilities prove that its destinations can be separated.

A blocking trigger attached to one shared Google tag blocks that tag for every connected destination; leaving the tag unblocked can expose every connected destination to that tag's denied-state behavior. Do not claim that incompatible per-product policies coexist merely because the destinations are listed separately. If one executable Google tag or helper serves products that require different routes, use only a current, officially supported destination-specific separation that the analyst approves. Otherwise mark the affected configuration `Blocked` pending an architecture decision.

## Choose the mode explicitly

Use current Google documentation to distinguish basic and advanced Consent Mode.

Default this skill to basic behavior: prevent Google tags from loading until the required consent is granted. Use advanced behavior only when the analyst explicitly requests and approves Google tags loading under denied defaults and sending the documented cookieless or limited-data signals.

Basic Consent Mode blocks Google tags until the required grant. Advanced Consent Mode loads consent-aware Google tags under documented defaults and changes their behavior according to consent state.

Do not describe built-in consent checks as a strict firing gate. Google tags with built-in checks can still execute in advanced mode and alter storage/transmission according to consent state.

## Verify consent types

Map the client-approved policy to the current Google consent types required by each destination. Verify at least:

- `analytics_storage` for Analytics storage behavior;
- `ad_storage` for advertising storage behavior;
- `ad_user_data` for sending user data to Google for advertising;
- `ad_personalization` for personalized advertising.

Check any additional consent type or privacy setting against current official documentation. Do not assume that GA4 always needs only `analytics_storage`; advertising features can introduce additional requirements.

## Distinguish consent mechanisms

Record each mechanism separately; none is a synonym for another:

| Mechanism | What it controls |
| --- | --- |
| Consent default/update state | The values supplied to Google's consent-aware tags. Defaults must precede affected tags; updates must follow the current user choice, including revocation. |
| Built-in consent checks | Template-owned behavior that changes storage or requests according to consent state. Built-in checks do not prove a strict basic-mode firing block. |
| Additional Consent Checks | Optional GTM firing requirements configured on a tag. They are not the same as built-in checks or a blocking trigger. Do not add them as a second copy of this skill's strict/basic vendor block. |
| Firing/blocking triggers | The strict pre-grant execution gate used by this skill's default basic route. |
| Custom-template consent APIs | `setDefaultConsentState`, `updateConsentState`, and `isConsentGranted` used by a permissioned CMP/template implementation. An unset value can be treated as granted by `isConsentGranted`; do not use that API alone as proof that unknown state fails closed. |

Prefer the CMP's supported consent template and GTM consent APIs. Do not implement defaults or
updates with Custom HTML `gtag('consent', ...)` because GTM can queue commands out of order and
template APIs are the supported in-container mechanism.

## Implement the default basic route

For basic behavior:

1. Verify how the CMP supplies the state and who owns the Google consent defaults and updates:
   site code, the CMP's GTM template, another saved tag, or an explicitly authorized new CMP tag.
   Do not create a second owner.
2. Map the approved policy explicitly to `analytics_storage`, `ad_storage`, `ad_user_data`, and
   `ad_personalization` as applicable. Preserve independently denied/granted values; do not derive
   every Google signal from one category unless the approved CMP mapping says they are identical.
3. Ensure the documented defaults precede affected Google tags and choice/revocation updates occur
   on the interaction page. If ownership lies outside the authorized GTM mutation, record it as a
   confirmed external dependency rather than claiming it was configured.
4. Reuse a strict block when the CMP identity, native condition, event scope, denied-state policy,
   ownership, and expected change path are semantically compatible. Separate GA4, Google Ads,
   Floodlight, or linker blocks only when one of those dimensions or the selected consent route
   differs.
5. Make unknown, uninitialized, and denied state block. Do not rely on an unset
   `isConsentGranted` result as the denial predicate.
6. Attach the applicable block to each Google config, event, conversion, remarketing, and linker
   execution unit only after verifying that every destination or consumer of that unit has a
   compatible basic policy.
7. Leave template-owned built-in checks visible, but set Additional Consent Checks to **not set**
   when the reusable vendor block owns strict eligibility. Do not report the built-in checks as
   removed; they are a separate native behavior surface.
8. Fire tags only after the required grant and prove from the complete GTM object graph that no
   in-scope Google execution unit can execute before it. Describe this as a configured
   expectation, not observed network behavior.

Use names such as `Block - Didomi - GA4 denied` and `Block - Didomi - Google Ads denied`.

Built-in consent checks may remain visible, but the shared CMP block is the mechanism that enforces
the default strict/basic non-fire policy. The normal trigger supplies the firing opportunity: use a
verified CMP readiness/grant event for a baseline/page-load tag and the approved business Custom
Event for a business-event tag.

## Implement advanced mode only when approved

For advanced behavior:

1. Use the CMP's supported GTM consent template when available and verified.
2. Fire consent-default logic on `Consent Initialization - All Pages` before affected Google tags.
3. Set the approved default states, normally denied where required by the client policy.
4. Send consent updates as soon as the user confirms or changes a choice and before a page transition.
5. Use the GTM consent template APIs rather than a Custom HTML `gtag('consent', ...)` workaround when implementing consent inside GTM.
6. Let Google tags use their documented built-in consent behavior.
7. Do not add Additional Consent Checks or exception triggers that block the denied-state pings the approved advanced design intends to send.
8. Configure optional mechanics only when explicitly required and documented:
   - `region` only for an approved geographic default and with the broader/default precedence
     understood;
   - `wait_for_update` only when a CMP update is expected within the chosen bounded delay;
   - `ads_data_redaction` only for the approved advertising-data behavior and current Google
     product support;
   - `url_passthrough` only when the site can preserve eligible click information in same-domain
     navigation and URL handling has been assessed;
   - linker and cross-domain options only from the approved domain/decorator architecture.

Do not silently convert an existing basic implementation to advanced mode merely because Google recommends or supports modeling.

Do not attach a blocking trigger that would suppress the denied-state behavior explicitly approved for Advanced Consent Mode.

## Keep tag behavior and page views separate

Consent defaults and updates do not decide page-view ownership. Apply the exact one-owner decision
in `analytics-tags.md`: Google-tag automatic, dedicated GA4 event, proven external owner, or
intentionally none. Inspect Enhanced Measurement and browser-history page views independently;
Consent Mode does not prevent duplicate automatic/manual events by itself.

## Configure every Google product consistently

Apply the selected product decision to each in-scope Google tag, GA4 tag, Google Ads conversion/remarketing tag, Floodlight tag, and Conversion Linker. Verify each tag's built-in checks, installed template settings, and denied-state behavior.

Different products may use different approved routes, but never mix a basic blocked product with an advanced product accidentally. Inventory shared destinations and helpers, require an explicit destination-by-destination decision and validation matrix, and split or block the design when one execution unit cannot satisfy every selected route.

## Record static consent assertions

This configuration skill does not execute runtime recette. Derive these assertions from the approved consent contract, configured defaults/updates, complete tag graph, and current official product behavior:

- default consent is set before affected tags;
- every required consent type has the expected initial value;
- updates occur on the interaction page;
- revocation updates the state;
- basic mode is configured so no in-scope Google execution unit is eligible before consent;
- advanced mode is configured for only the documented denied-state behavior and storage rules;
- tags list the expected built-in and additional consent checks;
- page views and conversions are not duplicated after consent updates.

Record the configured route as `strict/basic blocked` or `advanced consent-aware`; do not collapse both into the label `consent gated`. Label every result as a static configuration expectation, not observed browser behavior.

## Official entry points

- https://developers.google.com/tag-platform/security/concepts/consent-mode
- https://developers.google.com/tag-platform/security/guides/consent
- https://developers.google.com/tag-platform/security/guides/privacy
- https://support.google.com/tagmanager/answer/10718549
- https://developers.google.com/tag-platform/security/guides/consent-debugging

## Server pipeline ownership

Configure Google Consent Mode in the web container through one documented default/update owner.
The Google tag carries the relevant consent state with requests, and consent-aware Google tags in
the server container process it according to current Google documentation. Record this as
`incoming-google-consent-native`; do not invent a second gtag consent implementation in the server
container and do not translate a non-Google vendor grant into Google consent by analogy.

Basic mode may block a web request before transport; advanced mode may send documented limited
requests. Preserve the explicitly approved mode and prove web timing, signal propagation, and each
server Google tag's native behavior. A server blocking trigger is not a substitute for Google
Consent Mode unless current product documentation explicitly requires a separate condition.
