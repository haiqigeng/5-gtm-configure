# First-party user data

## Contents

- [Classify the feature before mapping data](#classify-the-feature-before-mapping-data)
- [Require explicit authority and activation](#require-explicit-authority-and-activation)
- [Use exact Google ownership and timing](#use-exact-google-ownership-and-timing)
- [Choose a controlled source](#choose-a-controlled-source)
- [Normalize, hash, and omit correctly](#normalize-hash-and-omit-correctly)
- [Apply the PII firewall](#apply-the-pii-firewall)
- [Govern the GA4 user ID lifecycle](#govern-the-ga4-user-id-lifecycle)
- [Apply consent independently](#apply-consent-independently)
- [Validate and hand off without leaking data](#validate-and-hand-off-without-leaking-data)
- [Keep the client-side boundary](#keep-the-client-side-boundary)
- [Official Google entry points](#official-google-entry-points)

## Classify the feature before mapping data

Do not use “first-party data,” `user_data`, “enhanced matching,” and `user_id` as synonyms. Assign
the request to one exact browser feature before creating any variable:

| Feature | Purpose | Default GTM owner |
| --- | --- | --- |
| GA4 `user_id` | Signed-in, cross-session identity using an approved stable non-PII identifier | Google tag configuration with explicit set/omit/reset lifecycle |
| GA4 user-provided-data collection | GA4's separately activated collection of consented first-party identifiers | Native User-Provided Data variable selected in `user_data` on only the authorized GA4 Event tag(s) |
| Google Ads enhanced conversions for web | Improve a specific web conversion with consented first-party identifiers | Current native Google tag / Google Ads conversion field; event override when the conversion event owns the data |
| Google Ads tag-wide user-provided data | Make a documented user-data value available to compatible Google Ads conversions | Current documented Google tag route, only after explicit tag-wide authorization |
| Google Ads User-Provided Data Event | Capture user data on an earlier page when it is unavailable at the later conversion event | Native User-Provided Data Event tag on the exact earlier event; the conversion remains a separate tag |
| Media-vendor advanced matching | Vendor-specific browser matching such as Meta or TikTok | That vendor's supported installed template field and consent route |

The same email source can therefore require different GTM variables or consumers. Never copy the
GA4 `user_data` implementation into Google Ads or another media template by analogy. Follow
[google-field-ownership.md](google-field-ownership.md) for the authoritative Google placement
matrix.

## Require explicit authority and activation

Do not enable automatic or manual collection by default. Require an explicit feature request,
approved purpose and consumer scope, current official product support, an approved source
contract, and representative synthetic test data. Do not make the legal or sensitive-category
eligibility decision.

Record every authorized consuming tag, page, and event. Approval of one lead event does not
authorize attaching `user_data` to every analytics event or placing it in a shared Event Settings
variable. Tag-wide collection needs separate explicit authority and proof that every consumer,
destination, consent route, and page scope is compatible.

In the durable run, bind each feature route to one exact mapped destination field and every
authorized consumer object. Read the consumer target back and prove that field is configured on
the correct product surface: GA4 `user_id` on a Google configuration tag, GA4 `user_data` on the
authorized GA4 Event tag, Google Ads enhanced conversion on its Ads consumer, tag-wide Google Ads
`user_data` on the authorized Google tag, and prior-page collection on the User-Provided Data Event
tag. Record positive product identity, implementation kind, saved tag type, and—for a community
template—the exact installed template identity with current official/template evidence. A route
label, consumer name, or negative “not GA4” test is insufficient. Custom HTML/Image cannot claim
native product identity; use the supported product surface or block the route.

Before considering the browser graph complete, record the applicable external or account-side activation:

- **GA4 user-provided data:** eligible property, accepted terms/feature activation, compatible
  Google tag capability, Google Ads link where required by the intended use, and any current
  industry restriction;
- **Google Ads enhanced conversions:** account and conversion-action enablement, customer-data
  terms and policies, supported conversion source/category, destination/linking state, and the
  current unified enhanced-conversion setting;
- **Other media matching:** vendor account/pixel activation, terms, destination identity, and
  template-specific enablement.

A saved GTM field cannot prove an account-side switch, eligibility, link, diagnostic, or policy
review. Keep each as an external dependency with an owner and status.

## Use exact Google ownership and timing

Choose the Google implementation by when the approved value exists:

| Availability and scope | Implementation |
| --- | --- |
| GA4 `user_id` lifecycle on one Google tag | Configure it directly on that Google tag. |
| Same GA4 `user_id` lifecycle across several enumerated compatible Google tags | A Configuration Settings variable is allowed only when source, set/reset behavior, consumers, destination, and consent are identical. |
| GA4 user-provided data exists on a selected event | Native User-Provided Data variable in the `user_data` field of that GA4 Event tag only. |
| Google Ads enhanced-conversion data exists on the conversion event | Current native enhanced-conversion field on the exact conversion tag, or its documented event override. |
| Google Ads enhanced-conversion data exists only on an earlier page/event | Native User-Provided Data Event tag on that earlier event, using the same approved feature and exact timing documented by Google. Do not delay or fabricate the later conversion payload. |
| Google Ads data is explicitly authorized tag-wide | Current native Google tag route; enumerate every conversion consumer before saving. |

Do not put GA4 `user_data` in a shared Event Settings variable. Do not transport advertising user
data through GA4 event parameters, user properties, or `user_id`. Do not attach one event's user
data to unrelated events to compensate for uncertain timing.

## Choose a controlled source

Use this source priority, recording the exact lifecycle and pages for every field:

1. a deliberate dataLayer field available on the required event;
2. an existing controlled first-party JavaScript value with a documented global path and timing;
3. a stable DOM element or selector only when explicitly approved and documented;
4. automatic collection or DOM scanning only when explicitly requested and its full page/field
   collection scope is understood.

Direct DLV mapping is correct only when the complete source shape matches the installed native
field. Use a narrow synchronous formatter when the approved raw source needs documented
normalization or object assembly. Do not use Custom HTML hashing, an imported hashing library, an
unverified asynchronous Custom JavaScript promise, or a payload-eligibility variable.

Never persist personal data in a GTM Constant, Lookup Table, Regex Table, cookie, local storage,
object note, variable/tag/trigger name, mutation journal, run artifact, change log, or debug output.
The configuration stores source paths and field names, never resolved real values.

## Normalize, hash, and omit correctly

Prefer the native User-Provided Data variable/template with raw input when current documentation
says Google normalizes and hashes it. Record `native-raw` ownership and do not pre-hash it. Use
pre-hashed input only when the selected native field explicitly supports it and the source is a
lowercase hexadecimal SHA-256 value produced by a controlled process. Never hash an existing hash.

Apply the exact current product rules to each field. At minimum:

- trim leading/trailing whitespace;
- lowercase email and other fields where Google requires it;
- normalize a phone to E.164 before hashing; a French local value such as `0101010101` needs an
  approved country context before it can become `+33101010101`—never infer a country from the
  browser locale or site host without authority;
- use a two-letter ISO country code where required;
- meet the product's address completeness rules rather than sending an arbitrary partial object;
- apply Google Ads' documented Gmail address normalization only for the Google Ads feature where
  the current rule requires it;
- remove null, empty, whitespace-only, invalid, literal `null`, and literal `undefined` fields from
  the user-data object instead of hashing or transmitting them;
- preserve only supported single/array shapes and never invent a fallback identifier.

For every field, record source mode, raw/pre-hashed mode, normalization owner, hashing owner,
missing behavior, and exact consumer. A native template that accepts raw data owns the hash; a
documented pre-hashed source owns the hash; GTM must not own both.

## Apply the PII firewall

Google Analytics prohibits sending personally identifiable information except through a
specifically permitted user-provided-data feature. Hashing ordinary analytics PII does not make it
an acceptable custom dimension.

Block any design that can place raw or hashed email, phone, name, postal address, or another direct
identifier in:

- ordinary GA4 event parameters, user properties, custom dimensions, or custom metrics;
- GA4 `user_id`;
- page URLs, titles, search terms, form fields, campaign parameters, or ecommerce descriptive
  fields;
- GTM constants, tables, names, notes, run artifacts, logs, screenshots, or human change logs;
- an unrelated media tag or consumer outside the explicitly sanctioned native matching feature.

Treat GA4 data redaction and unwanted-referral/query-parameter controls as external safety nets,
not permission to send PII and not proof that the source is safe. Record the property-side redaction
review as an external dependency when URLs or form/search sources could expose identifiers.

## Govern the GA4 user ID lifecycle

Use only a client-generated, stable, opaque, non-PII identifier. Enforce the current GA4 maximum
length of 256 characters. Do not use an email address, hashed email, phone number, name, device ID,
advertising ID, blank value, dummy value, or literal `null`/`undefined` string.

Implement the lifecycle explicitly:

1. before authentication, omit `user_id`;
2. after the authenticated identity is available, set the approved identifier on the Google tag;
3. on logout or identity clearance, send JavaScript `null` through the documented Google-tag
   lifecycle so the previous identity is not retained;
4. verify account switching, SPA state changes, and every shared consumer;
5. never register `user_id` as a custom dimension or duplicate it as a user property.

Do not assume that hashing an email creates a valid `user_id`.

## Apply consent independently

Under this skill's default strict/basic route, the owning base/config tag and every user-data event
or conversion tag receive the required vendor block. Hashing does not replace consent.

For Google advertising features, treat `ad_user_data` independently from `ad_storage`:

- `ad_user_data: denied` means Google advertising user data, including enhanced-conversion data and
  `user_id` used for advertising purposes, must not be sent;
- `ad_storage` controls advertising storage and is not a substitute for the user-data decision;
- `analytics_storage`, `ad_personalization`, and the product's other required types remain separate
  decisions.

In explicitly approved advanced/native mode, do not add a blocking trigger or Additional Consent
Check that suppresses the intended denied-state request. Still prove that a denied `ad_user_data`
state excludes user-provided fields. Never infer that a vendor's advanced mode behaves like Google
Consent Mode.

## Validate and hand off without leaking data

Use synthetic identities. Saved readback must prove:

- the exact feature, native field/mode, authorized consumers, timing, and supported field keys;
- no empty, placeholder, double-hashed, invalid, or unauthorized field;
- unrelated events and tags do not inherit the data;
- the configured `user_id` set/omit/reset lifecycle when applicable;
- exact consent topology and the required user-data consent type;
- external account/property actions remain honestly separated;
- no resolved PII appears in the machine artifact or human change log.

The recette handoff names expected keys, consent states, and network cues without recording values.
For Google Ads/GA4 enhanced matching, include the documented `em` request cue and the empty-data cue
such as `tv.1~em` only where current Google documentation applies. Treat Diagnostics and match-rate
reporting as external platform evidence, not static GTM proof.

## Keep the client-side boundary

Configure only the requested browser feature. Do not create server-side GTM transformations,
Conversions API, enhanced conversions for leads uploads, offline conversion uploads, CRM jobs, or
browser/server deduplication. A browser Google tag routed through `server_container_url` remains in
scope, but the receiving server container remains external.

## Official Google entry points

Reopen the current pages during each implementation; these URLs are discovery entry points, not a
cached field catalogue:

- GA4 user-provided data overview: https://support.google.com/analytics/answer/14077171
- GA4 manual GTM implementation: https://support.google.com/analytics/answer/14179229
- GA4 user-data field formatting: https://support.google.com/analytics/answer/14179230
- GA4 PII policy: https://support.google.com/analytics/answer/6366371
- GA4 User-ID: https://support.google.com/analytics/answer/9213390
- GA4 data redaction: https://support.google.com/analytics/answer/13544947
- Google Ads enhanced conversions with GTM: https://support.google.com/google-ads/answer/13262500
- Google Ads enhanced-conversion setup and formatting: https://support.google.com/google-ads/answer/13258081
- Google customer-data policies: https://support.google.com/google-ads/answer/7475709
- Google Consent Mode: https://developers.google.com/tag-platform/security/concepts/consent-mode
