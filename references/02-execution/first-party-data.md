# First-party user data

## Contents

- [Treat matching features as opt-in scope](#treat-matching-features-as-opt-in-scope)
- [Authorize collection and consumer scope](#authorize-collection-and-consumer-scope)
- [Prefer controlled sources](#prefer-controlled-sources)
- [Follow the vendor's field contract](#follow-the-vendors-field-contract)
- [Resolve feature ownership per destination](#resolve-feature-ownership-per-destination)
- [Configure Google first-party data natively](#configure-google-first-party-data-natively)
- [Separate analytics identifiers from advertising matching](#separate-analytics-identifiers-from-advertising-matching)
- [Design safe GTM objects](#design-safe-gtm-objects)
- [Apply consent before collection and transmission](#apply-consent-before-collection-and-transmission)
- [Validate without leaking data](#validate-without-leaking-data)
- [Current client-side boundary](#current-client-side-boundary)

## Treat matching features as opt-in scope

Apply this reference to Google Ads enhanced conversions, Meta Advanced Matching, TikTok Advanced
Matching, Snap matching, Microsoft user-data features, Pinterest enhanced match, X user parameters,
LinkedIn/Reddit/Criteo matching, or another vendor feature that uses email, phone, name, address,
external/customer ID, or similar identifiers.

Do not enable automatic or manual collection by default. Require:

- an explicit implementation request and authorization;
- the client-approved purpose and consent policy;
- confirmation that required vendor terms/settings are completed outside GTM where applicable;
- current official browser documentation for supported fields and handling;
- an approved source contract, evidence grade, and representative non-production test data.

Do not make the legal decision. Stop when the analyst cannot establish approved data use.

## Authorize collection and consumer scope

Approval of an identifier or matching feature does not authorize attaching it to every event. Before
configuration, record:

- the exact destination product and feature;
- its approved collection mode: tag-wide automatic, tag-wide manual, event-specific, or
  conversion-specific;
- every authorized consuming tag, page, event, or tag family;
- source availability, resolution timing, and lifetime at each authorized consumer;
- the applicable consent state and any account-side activation or terms;
- the GTM object that will own the setting.

Use tag-wide collection only when it is explicitly requested, current official documentation
supports it for the selected feature, and its wider collection scope is compatible with every
destination and consent route involved. When consumer scope cannot be established, block only the
affected first-party-data feature. Do not attach the data to all events as a fallback for
uncertainty.

## Prefer controlled sources

Use this source priority unless the approved implementation requires otherwise:

1. a deliberate dataLayer field available at the correct event;
2. an existing controlled JavaScript variable or first-party source;
3. a stable DOM element or selector only when documented and approved;
4. automatic DOM scanning only when explicitly enabled and its collection scope is understood.

Do not enable automatic collection merely because a template recommends it. Document every page and field type the feature can inspect.

Never send placeholder values, test identities, authentication secrets, or sensitive-category data.

## Follow the vendor's field contract

For every identifier, record:

- official vendor field and browser support;
- raw or pre-hashed input requirement;
- required normalization steps;
- hashing algorithm and whether the vendor/template performs it;
- accepted array/single-value shape;
- null, empty, invalid, and multiple-value behavior;
- GTM source variable and consent requirement.

Normalize and hash only as current official documentation requires. Do not double-hash a value when the selected template performs hashing. Do not send a raw value where pre-hashing is required.

## Resolve feature ownership per destination

Treat every destination feature independently even when it reads the same source:

| Decision | Required proof |
| --- | --- |
| Google enhanced conversions | Exact conversion product, current Google tag/template field, raw/pre-hashed mode, account-side activation, and applicable Google consent types. |
| Meta advanced matching | Exact Pixel/template capability, accepted browser fields, automatic/manual mode, normalization/hash ownership, and Meta consent route. |
| Microsoft user-data feature | Exact UET product/template, current accepted fields and mode, account dependency, and Microsoft consent route. |
| Other media matching | Current official browser documentation, installed template, explicit accepted field set, source approval, and product-specific consent. |

Do not create one shared `hashed user data` object for several vendors unless current schemas,
normalization, hash representation, consent, lifetime, consumers, and ownership are all proven
identical. Prefer vendor-owned variables so a later policy or schema change cannot silently affect
another destination.

## Configure Google first-party data natively

For an explicitly authorized browser-side Google feature, inspect the current native Google Ads or
Google tag fields before creating transformations:

1. Identify whether the requested feature is Google Ads enhanced conversions, GA4
   user-provided-data collection, or another exact Google product. They are not interchangeable.
2. Prefer GTM's native User-Provided Data variable when the selected tag field accepts it. Select
   manual fields, a controlled dataLayer variable, or current automatic collection only as the
   approved feature and documentation permit.
3. Map only supported identifiers required by the approved feature. Keep raw source,
   normalization, and hash ownership explicit.
4. When the native tag/template hashes normalized raw data, provide the accepted raw form and do
   not pre-hash it. When a documented pre-hashed mode is selected, supply only the required
   SHA-256 representation and mark the saved mode so it cannot be hashed again.
5. Apply the exact Google consent types, especially `ad_user_data` for advertising transmission,
   plus the selected basic or advanced route.
6. Record Google Ads/GA4 account-side activation, diagnostics, and terms as external dependencies;
   a saved GTM variable does not complete them.

Select the narrowest native owner that matches the approved scope:

| Approved use | Default GTM owner |
| --- | --- |
| GA4 `user_id` consumed by one Google tag | Configure it directly on that Google tag. |
| The same `user_id` contract reused by multiple compatible Google tags | Use a Google tag Configuration Settings variable only when the shared source, lifecycle, reset behavior, consent, and consumers are all identical. |
| GA4 user-provided-data collection on specific customer-data events | Use the native User-Provided Data variable through the `user_data` field on each authorized GA4 Event tag. |
| Google Ads tag-wide user-provided data | Use the current documented Google tag or Google Ads route only when tag-wide collection was explicitly authorized. |
| Google Ads event-specific enhanced conversions | Configure the exact conversion tag and its current native user-data field. |
| Another vendor's browser matching feature | Use the supported installed template field owned by that vendor and approved consumer scope. |

A Configuration Settings or Event Settings variable is a reuse mechanism, not a default layer.
Follow the general direct-versus-shared decision rules in
[analytics-tags.md](analytics-tags.md). Do not put GA4 user-provided data in a shared Event Settings
variable merely to make it reach more events, and do not create a Configuration Settings variable
for a value consumed by only one Google tag.

Do not use GA4 `user_id`, event parameters, or user properties to transport advertising
user-provided data. Do not add a Custom HTML hashing library when the native variable/template owns
normalization and hashing.

## Separate analytics identifiers from advertising matching

Do not send email, phone, name, postal address, or other personally identifiable information to GA4 event parameters, user properties, URLs, titles, or debug fields.

Do not reuse an advertising matching variable in an analytics tag without independently validating that the analytics destination permits that value.

Keep these Google concepts separate:

| Concept | Purpose and owner |
| --- | --- |
| GA4 `user_id` | An approved stable, non-PII identifier for signed-in user-state stitching. It is a Google tag configuration contract with explicit set, omit, and reset behavior. |
| GA4 user-provided data | A separately activated matching feature for supported customer identifiers. Its native User-Provided Data variable is consumed only by the authorized collection events or pages. |
| GA4 user properties | Approved analysis attributes with their own scope and lifecycle. They are not a transport for `user_id` or user-provided data. |
| Advertising matching data | A destination-specific Google Ads or other media feature owned by its conversion/base tag and browser schema, not by GA4 event parameters. |

## Design safe GTM objects

- Give each user-data variable a clear vendor/purpose owner.
- Keep normalization transformations narrow and null-safe.
- Do not persist user data in a GTM constant, lookup table, cookie, local storage, or debug log.
- Avoid exposing resolved personal data in handoff screenshots or reports.
- Do not broaden an existing shared variable's consumers without checking its data-handling contract.
- Use template-native user-data variables when current official documentation requires them.
- Record whether the template receives raw values, normalized values, or final hashes and verify the
  saved mode explicitly.

## Apply consent before collection and transmission

Map each identifier feature to the client-approved consent state and current vendor requirement. Under the default strict/basic route, block both the base tag and matching-enabled event tag until the required vendor consent is granted.

For explicitly approved advanced/native consent, verify whether denied-state requests can contain user-provided data. Configure the vendor controls so disallowed identifiers are not collected or transmitted under denied state.

Do not assume that hashing replaces consent or makes a value anonymous.

## Validate without leaking data

Use synthetic test values when possible. Verify:

- source availability at the exact event according to the approved contract;
- the saved collection mode and complete authorized consumer set;
- unrelated tags and events do not inherit the first-party data;
- the selected direct tag field, Configuration Settings variable, Event Settings variable, or
  native User-Provided Data variable is the narrowest correct owner;
- normalization and hash ownership;
- template field resolution;
- configured collection fields remain blocked before required consent;
- configured denied-state routes omit user data when prohibited by the approved contract;
- no PII in GA4, URLs, logs, reports, or unrelated tags;
- missing input produces no invented fallback.

Record validation results without reproducing real personal data.

## Current client-side boundary

Configure only the browser-side feature explicitly requested. Do not add server-side user-data events, Conversions API, enhanced conversions for leads uploads, offline conversion uploads, or browser/server deduplication in the current scope.
