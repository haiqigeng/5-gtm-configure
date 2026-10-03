# GA4 configuration and collection ownership

Author native GA4 Event (`gaawe`) parameters with `eventSettingsTable` LIST rows containing
`parameter`/`parameterValue` MAP cells. Do not write legacy `eventParameters` name/value rows.
Native ecommerce uses `sendEcommerceData` BOOLEAN and the inspected `getEcommerceDataFrom`
source (for example `dataLayer`); `sendEcommerce` is not the native enable field. Semantic analysis
of existing saved objects does not authorize obsolete forms for a new write.

## Contents

- Configure the Google tag deliberately
- Resolve Google tag and destination identity
- Assign exactly one page-view owner
- Reconcile Enhanced Measurement and manual events
- Configure lifecycle and diagnostic fields explicitly
- Record external Google and GA4 administration
- Route GA4 through a server container

## Configure the Google tag deliberately

Use current Google documentation to distinguish:

- the Google tag/configuration tag;
- a Google tag Configuration Settings variable;
- a Google tag Event Settings variable;
- GA4 event tags and event-specific parameters;
- settings managed in the GA4 data stream or Google tag destination UI.

Inspect the actual installed/native tag fields and current connected destinations before designing
or updating settings. Do not configure a field because it exists in a newer documentation surface
when the target container cannot store or apply it.

Use these naming patterns unless the analyst supplies an explicit naming decision or the relevant
object family has a consistent, equally clear presentation convention. Naming compatibility never
changes the selected technical architecture:

| Object | Name |
| --- | --- |
| Primary Google tag | `GA4 - Config` |
| Qualified Google tag | `GA4 - Config - main` |
| Configuration Settings variable, when justified | `GA4 - Config Setting` |
| Event Settings variable, when justified | `GA4 - Event Setting` |
| Measurement ID constant | `CST - GA4 measurement_id` |

Reference the measurement ID through a compatible constant rather than hard-coding it repeatedly. Do not create a settings variable merely because GTM offers one.

Use a Configuration Settings variable only for a coherent set of configuration-level values reused across applicable Google tags. Use an Event Settings variable only for a coherent set of event parameters or user properties genuinely shared across applicable events. Keep transaction, item, search, form, and other event-specific values on the event tag.

Inspect consumers before changing either settings variable because one edit may affect many tags and destinations.

Use [google-field-ownership.md](google-field-ownership.md) as the authoritative placement matrix
for configuration fields, event fields, settings variables, `user_id`, `user_data`, ecommerce,
Google Ads fields, and browser transport. This playbook adds GA4 behavior but does not override that
matrix.

Use this semantic decision matrix; do not apply a fixed numerical threshold:

| Decision | Keep directly on tag | Use shared settings variable |
| --- | --- | --- |
| Ownership | Event-specific or independently owned | Same owner and change lifecycle across every consumer |
| Value/source | Transaction, item, form, search, or other event-specific value | Identical source or literal with identical type and missing behavior |
| Consent/destination | Different route or destination behavior | Compatible consent route and destination behavior |
| Change risk | A change should affect one event | A change intentionally should affect every enumerated consumer |

For multiple streams, properties, regions, or environments, load the multi-destination routing
playbook. Never place a production measurement ID as a lookup default.

## Resolve Google tag and destination identity

Do not use `Google tag`, `GA4 configuration`, `measurement ID`, and `destination` as synonyms.
Read the current saved fields and Google administration surfaces before mutation:

- `GT-...` identifies a Google tag;
- `G-...` identifies a GA4 web data stream and is the measurement ID used by GA4 Event tags;
- `AW-...` identifies a Google Ads destination and may also identify the Google tag used by that
  product;
- a destination receives data from a Google tag but is not itself another executable GTM tag;
- one Google tag can have connected destinations and inherited settings that affect more than the
  label visible on the GTM object.

For every Google execution unit, record the saved tag ID, every connected destination, the ID used
by each event tag, inherited configuration/event settings, and all consumers. Do not point a GA4
Event tag at a `GT-...` value merely because the Google tag UI displays it; use the exact current
GA4 measurement-ID contract. Do not create a second Google tag when connecting or reusing a
destination is the documented compatible architecture, and do not connect or remove a destination
without explicit authority because that changes routing outside one event tag.
An absent or deprecated destination-link action does not grant authority to combine tags, move IDs,
or select a different destination; use a supported authorized surface or record the dependency.

## Assign exactly one page-view owner

Do not default `send_page_view` to either `true` or `false`. Before changing a Google tag, inspect
the saved Google-tag fields, GA4 Event tags, Enhanced Measurement page-load/history behavior, SPA
routing, hard-coded/partner installations, and the approved page-view contract. Record exactly one
owner per destination and occurrence role. Initial page load and virtual navigation are distinct;
multiple tags are valid only when their occurrence domains are proved mutually exclusive:

| Owner | Google-tag decision | When valid |
| --- | --- | --- |
| Google tag automatic page view | `send_page_view: true` | Its timing, page fields, SPA behavior, and consent opportunity satisfy the approved requirement without another owner. |
| Dedicated `GA4 - Event - page_view` | `send_page_view: false` | The approved event needs explicit parameters, timing, routing, or SPA ownership that the automatic route cannot supply. |
| Internal non-Google tag | Not applicable | A Matomo, Amplitude, or other in-container tag owns the named destination/occurrence. |
| External/hard-coded owner | Not applicable | Authoritative evidence proves the external owner and its compatible destination/consent behavior. |
| Intentionally no page view | Not applicable | The approved destination/occurrence is intentionally excluded; record the reason. |

Ambiguous, missing, or overlapping ownership blocks the affected change. When a dedicated GA4
page-view tag owns initial load, every applicable Google tag has `send_page_view: false`. When the
Google tag owns initial load, do not create another initial page-view tag. Google-tag automatic
page view cannot own virtual navigation; use an explicit, proved virtual-navigation owner.

Derive capability from effective stored fields and every connected GA4 destination, including
inherited Configuration Settings and the documented default when `send_page_view` is absent.
An empty declaration cannot hide an automatic or explicit `page_view` emitter. An Ads-only Google
tag does not become a GA4 page-view owner. Resolve a `GT-...` tag's connected destinations before
assigning ownership.

`send_page_view: false` suppresses the configuration command's page view. Enhanced Measurement
history-change collection is independent and must also be reconciled when an explicit SPA event
owns virtual views. See [Google's page-view guide](https://developers.google.com/analytics/devguides/collection/ga4/views).

Under strict/basic consent, a page-load owner that cannot use the original pre-CMP event uses the
CMP's verified one-time readiness/grant event as its normal trigger and retains the vendor blocking
trigger. Do not use a repeatable consent-change event without an explicit duplicate and later-grant
policy. Revalidate every page parameter at the later CMP event; an earlier event-scoped payload is
not assumed to persist.

For a separate SPA `page_view`, update the applicable Google configuration fields before sending
the event. Google's [GTM SPA procedure](https://developers.google.com/analytics/devguides/collection/ga4/measure-spa-gtm)
uses a setup-only Google tag with `update: true`, followed by a History Change GA4 event, with
automatic history page views disabled. A shared trigger or higher tag priority does not prove
that ordering. Apply the [sequencing capability boundary](triggers-and-variables.md#use-tag-sequencing-only-when-required):
until that topology is supported by the contract and runtime, report this recipe as unsupported
and block the affected new implementation. Preserve an already verified external owner when it
satisfies the approved contract; do not silently replace it or represent it as the same recipe.

## Reconcile Enhanced Measurement and manual events

Inspect the target stream's confirmed Enhanced Measurement settings and the current Google tag
before adding a manual GA4 event. At minimum reconcile page views/history, scrolls, outbound clicks,
site search, video engagement, file downloads, and form interactions when the approved requirement
overlaps them.

| Situation | Configuration decision |
| --- | --- |
| Confirmed automatic event exactly satisfies the approved contract | Reuse that owner; do not add a duplicate manual tag. |
| Approved manual event must own collection | Configure the manual event and record the exact external Enhanced Measurement setting that must be disabled or narrowed. |
| Property-side state is unknown and collision is material | Block the affected mutation or record an explicit external dependency; do not assume either state. |
| Automatic event differs in timing or semantics | Preserve the approved contract and document why the two events are distinct or why one owner must change. |

## Configure lifecycle and diagnostic fields explicitly

- Use `traffic_type` for an approved internal-traffic filter design. Developer-traffic filters
  act on debug-mode traffic instead. Both GA4 Admin filters remain external dependencies; setting
  either collection field does not create or activate a filter. See Google's
  [internal](https://support.google.com/analytics/answer/10104470) and
  [developer](https://support.google.com/analytics/answer/13296662) traffic guides.
- Set `debug_mode` only for an approved diagnostic route. To disable it, omit the parameter from
  production collection; do not assume a literal `false` disables DebugView classification.
- Keep environment lookup behavior explicit and never route an unknown/no-match environment to a
  production measurement ID.
- Record default, authenticated, logout/reset, and environment transitions whenever a persistent
  configuration field can outlive the event that set it.

## Record external Google and GA4 administration

For every collected field or event, determine whether the approved reporting use also requires work outside the authorized GTM change. Record, without silently changing:

- GA4 custom dimensions or metrics for custom event, item, or user fields;
- GA4 key-event designation;
- data-stream or Enhanced Measurement settings that can duplicate or alter the selected event;
- Google tag destinations, shared settings, cross-domain configuration, unwanted-referral handling, or other current administration surfaces;
- advertising or audience activation settings owned outside GTM.

Resolve the current configuration surface from official documentation. Classify each dependency as already confirmed, separately authorized, required external work, intentionally untouched, or blocking.

## Route GA4 through a server container

When a server endpoint is in scope, first inspect whether one compatible Google tag can own the
measurement identity and transport endpoint. Create a dedicated transport Google tag only when
identity, endpoint, consent, page-view ownership, environment routing, or lifecycle isolation
requires it. A server URL variable is useful for reuse or deterministic environment routing, not a
mandatory helper.

Decide page-view ownership before setting `send_page_view`: automatic Google-tag page view,
dedicated GA4 event, another proved owner, or intentionally none. Reconcile Enhanced Measurement,
SPA behavior, hard-coded tags, and direct-browser versus server-routed destinations so one
occurrence is not sent twice.

Keep field ownership explicit. Stable Google-tag transport/configuration values belong in Google
tag Configuration Settings when genuinely shared. GA4 event parameters belong in Event Settings
or the event tag; GA4 user properties use the dedicated user-property area. `user_id` and
`user_data` are not interchangeable, and `user_data` is never a GA4 user property. For a server
enhanced-conversion route, follow the current Google feature procedure and transport approved
event-scoped user data without attaching it globally by convenience.

Configure and read back the server GA Client and server GA4 destination before a live endpoint
cutover. Load `server/analytics-ga4.md` and the pipeline files for receiver, shape, consent, and
rollout rules.
