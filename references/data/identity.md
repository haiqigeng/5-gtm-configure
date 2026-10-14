# First-party user data

## Classify the feature before mapping data

Select one exact feature, purpose and delivery route before creating a variable. Site source keys,
GTM assembly variables, product fields and collection tags are distinct parts of that route.
[Google fields](../analytics/google-fields.md) owns placement; this guide owns identity semantics,
authorization, normalization and lifecycle.

| Feature | Purpose and consuming surface |
| --- | --- |
| GA4 `user_id` | Signed-in identity through an approved stable non-PII ID on Google tag configuration. |
| GA4 user-provided data | Separately activated collection through a native User-Provided Data variable on the authorized GA4 Event tag's `user_data`. |
| Google Ads enhanced conversions for web | Matching for an approved conversion through sufficient existing collection, authorized tag-wide collection or inspected native event override. |
| Google Ads tag-wide user data | Documented Google tag collection with authority for every enumerated consumer. |
| Google Ads User-Provided Data Event | Earlier-event collection when data is available before the separate conversion event. |
| Google Ads server enhanced conversions | Approved sender `user_data`, claiming Client/Event Data and receiving Ads Conversion Tracking tag. |
| Google Ads server prior-page collection | Approved earlier capture event received by the separate server User-provided Data Event tag. |
| Media advanced matching | Exact vendor/browser or server feature through its supported installed fields. |

## Require explicit authority and activation

Each route requires an explicit feature request, approved purpose, events/pages/consumers, current
product support, approved source contract and synthetic examples. The client owns eligibility,
sensitive-category and legal decisions. Tag-wide scope enumerates all consumers, destinations and
consent routes; event-scoped authority applies to its named event consumers.

Bind each route to its exact mapped field and actual consumer objects. Record positive product
identity, implementation kind, saved native tag type and, for a community template, installed
identity and official/template evidence. Supported product surfaces establish native identity.

Account-side activation has its own evidence and owner:

- GA4: eligible property, accepted terms/activation, compatible Google tag, applicable Ads link and current industry restrictions;
- Google Ads: account/conversion enablement, customer-data terms, supported source/category, destination/linking and current enhanced-conversion setting;
- other media: account/pixel activation, terms, destination and template enablement.

Record these as external dependencies, separate from saved field proof.

## Use exact Google ownership and timing

Resolve availability at the actual consuming event. GA4 `user_id` belongs to the Google
configuration lifecycle. Identical approved lifecycle across enumerated compatible Google tags
can use Configuration Settings. GA4 collection `user_data` belongs to the selected Event tag.

For Ads, use the [feature selection procedure](../vendors/google-ads/web.md#configure-enhanced-conversions-only-explicitly)
to choose existing collection, tag-wide authority, native conversion override or earlier-page
capture. Earlier collection has its own supported trigger: Google's GTM procedure specifies Form
Submission for that route. Establish exact current template/feature compatibility and capture scope
independently from the later conversion's business trigger.

Google Ads server carriage has the distinct sender/receiver bindings below. Its feature activation
and consumer scope are assessed as Ads transport. Google tag settings have tag-wide lifetime;
event-level overrides resolve at their own event.

## Choose a controlled source

Prefer a deliberate event dataLayer field, then a controlled first-party JavaScript value with
known path/timing, then an explicitly approved stable DOM source. Automatic collection requires
explicit approval of its full page/field scope. Use a direct DLV for a compatible complete shape or
a narrow synchronous formatter for documented normalization/object assembly.

Configuration and evidence persist source paths, field names and synthetic values. Operational
personal data stays in the sanctioned native matching flow. Native earlier-collection storage is
part of that feature's explicitly approved lifecycle and consent scope. Use the native variable or
a controlled upstream process for supported hashing; [mapping](mapping.md) owns variable selection.

## Normalize, hash, and omit correctly

Each field has one normalization owner and one hashing owner, recorded with source mode,
raw/pre-hashed mode, missing behavior and consumer. A native raw-input route uses `native-raw`;
a supported pre-hashed route receives a controlled lowercase hexadecimal SHA-256 value.

Apply the exact current product contract: trimming, required lowercasing, E.164 phone with approved
country context, required ISO country code, complete address groups, and feature-specific Gmail
normalization. For example, conversion of `0101010101` to `+33101010101` requires approved French
country context. The output contains supported, meaningful values with exact scalar/array shapes;
empty, invalid and placeholder inputs resolve to omission under the documented field contract.

## Apply the PII firewall

Direct identifiers, raw or hashed, have one permitted destination class: an explicitly sanctioned
user-provided-data/matching feature for its approved consumer. Ordinary analytics parameters,
properties, dimensions, metrics, User-ID, page context and ecommerce descriptive fields contain
non-PII analytical values. Persistent artifacts follow
[privacy enforcement](../core/execution.md#handle-secrets-without-false-equality).

Property-side data redaction and URL/query controls are additional external protections. When
page/form/search sources could expose identifiers, record the source remediation and property
review dependency; configured matching permission remains scoped to the matching feature.

## Govern the GA4 user ID lifecycle

Use a client-generated stable opaque non-PII identifier within the current 256-character limit.
Its semantics represent the authenticated user, independently of device/advertising identifiers.
The `ga4-user-id` route records approved `identity_lifecycle`: `initial: omit`,
`authenticated: set`, `cleared: javascript-null`, `changed: replace`. The shared schema owns these
states. Bind `configuration_fields.user_id` to the authorized Google configuration consumer.
Saved proof establishes the mapping; field QA verifies login, logout, account switching, SPA changes
and every shared consumer against that lifecycle.

## Apply consent independently

Use [web consent](../consent/web.md), [Google consent](../consent/google.md) and
[server consent](../consent/server.md) for eligibility. For Google advertising user data,
`ad_user_data` controls transmission, including User-ID used for advertising; `ad_storage` controls
storage. Other required types retain their separate decisions. A denied `ad_user_data` state yields
omitted user-provided fields even where approved advanced behavior permits limited requests.

## Validate and hand off

Synthetic vectors and saved readback establish exact feature/field/mode, source timing, authorized
consumer set, meaningful supported keys, single hashing ownership, lifecycle and consent topology.
The report records keys and dependencies while operational values remain private. Applicable
Google request cues such as `em` and empty-data `tv.1~em` are instructions for later runtime checks;
Diagnostics and match rate require separate platform evidence.

## Extend first-party data through the server pipeline

Trace each approved route:

`source -> normalization/hash owner -> transported user_data -> claiming Client -> Event Data -> scoped Transformation -> destination`

| Feature and timing | Sender binding | Receiver binding |
| --- | --- | --- |
| `google-ads-server-user-data-transport`, `same-event` | Actual GA4 Event carrying native UPD; product `google-ads-transport` | Server Ads Conversion Tracking consumers matching proved object-shaped field flows. |
| Same feature, separately approved `tag-wide` pipeline | Actual Google tag carrying `user_data`; product `google-ads-transport` | Enumerated server Ads Conversion Tracking consumers and matching field flows. |
| `google-ads-server-user-provided-data-event`, `prior-page` | Google tag or documented GA4 Event override resolving data on the approved capture event | Server Google Ads User-provided Data Event tag for that earlier event. |

Set `consumer_object_keys` and `server_consumer_object_keys` to those actual objects. Earlier-event
capture and later conversion have independent occurrence/field proof. When a value first exists
after initialization, its capture-event sender supplies the native UPD override.

A web-only same-event transport route uses `server_consumer_object_keys: []` and a
requirement-scoped `external_receiver_dependency_id`, also in `external_dependency_ids`, with the
receiver owner and required action. Its proof covers the saved sender. Pipeline scope includes
actual receivers and proved field flows. [Server identity](server-identity.md) owns receiving-path
inspection; [authority](../core/authority.md) owns target boundaries.

## Govern user properties and identifiers

A user property requires an approved stable analysis purpose, permitted name/limits, source, scope
and reset behavior. Shared Event Settings apply only across compatible intended events. Content
groups are separately approved configuration fields with explicit source and timing. The User-ID
and matching routes retain their dedicated product surfaces.

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
