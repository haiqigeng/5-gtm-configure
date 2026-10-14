# GA4 configuration and collection ownership

Native GA4 Event (`gaawe`) parameters use `eventSettingsTable` LIST rows with
`parameter`/`parameterValue` MAP cells. Native ecommerce uses `sendEcommerceData` BOOLEAN and
inspected `getEcommerceDataFrom` source. The schema and native validators enforce current writes.

## Configure the Google tag deliberately

Inspect native fields, connected destinations and current product capability. Apply
[Google field ownership](google-fields.md) for placement and shared-setting consumer analysis.
Reuse a compatible constant for repeated measurement IDs. Optional settings variables represent
coherent values deliberately shared across compatible consumers.

Use the analyst's naming decision or a consistent clear family convention; otherwise:

| Object | Name |
| --- | --- |
| Primary Google tag | `GA4 - Config` |
| Qualified Google tag | `GA4 - Config - main` |
| Configuration Settings variable | `GA4 - Config Setting` |
| Event Settings variable | `GA4 - Event Setting` |
| Measurement ID constant | `CST - GA4 measurement_id` |

[Routing](../routing.md) owns multi-stream/property/region/environment selection.

## Resolve Google tag and destination identity

`GT-...` identifies a Google tag; `G-...` identifies a GA4 web stream and supplies the GA4 Event
measurement ID; `AW-...` identifies an Ads destination and may identify its Google tag. A connected
destination receives data through the executable Google tag. Record saved tag ID, every connected
destination, event-tag IDs, inherited settings and consumers.

Reuse/connect destinations only through the supported architecture and explicit destination-change
authority. An unavailable administration action becomes an external dependency. Exact identity and
scope remain the basis for selecting the execution unit.

## Assign exactly one page-view owner

Inspect effective Google-tag fields, GA4 Event tags, Enhanced Measurement/history, SPA routing and
supplied site/partner evidence. Each destination and occurrence role has one effective owner.
Initial load and virtual navigation are separate domains; multiple collectors require proved
mutually exclusive domains. The selected owner determines `send_page_view`:

| Owner | Google-tag decision | When valid |
| --- | --- | --- |
| Google tag automatic page view | `send_page_view: true` | Its timing, page fields, SPA behavior, and consent opportunity satisfy the approved requirement without another owner. |
| Dedicated `GA4 - Event - page_view` | `send_page_view: false` | The approved event needs explicit parameters, timing, routing, or SPA ownership that the automatic route cannot supply. |
| Internal non-Google tag | Not applicable | A Matomo, Amplitude, or other in-container tag owns the named destination/occurrence. |
| External/hard-coded owner | Not applicable | Authoritative evidence proves the external owner and its compatible destination/consent behavior. |
| Intentionally no page view | Not applicable | The approved destination/occurrence is intentionally excluded; record the reason. |

A dedicated, external or intentionally absent initial owner requires automatic initial collection
disabled on each linked Google tag. The automatic Google-tag route owns initial load; virtual
navigation needs its own proved owner. Resolve all connected GA4 destinations and inherited settings,
including documented absent-field defaults. Ads-only execution has its own destination domain.
Unresolved or overlapping ownership holds the affected change.

`send_page_view: false` governs configuration-command views. Enhanced Measurement history collection
has independent controls; reconcile them for an explicit SPA owner. See
[Google's view guide](https://developers.google.com/analytics/devguides/collection/ga4/views).
[Consent lifecycle](../consent/lifecycle.md) owns initial/later opportunities and field freshness.

Google's [GTM SPA recipe](https://developers.google.com/analytics/devguides/collection/ga4/measure-spa-gtm)
uses setup-only Google tag `update: true`, then History Change GA4 Event, with automatic history
views disabled. It requires ordered setup/event execution. Apply the
[sequencing capability](../web/execution.md#use-tag-sequencing-only-when-required): the current model
holds a new implementation of this unsupported topology. An already verified external owner can
satisfy the approved occurrence contract under its own evidence.

## Reconcile Enhanced Measurement and manual events

Inspect confirmed stream settings for overlapping page/history, scroll, outbound click, search,
video, download and form collection. An automatic event satisfying the approved contract remains
its owner. A selected manual owner records the exact external setting to disable/narrow. Unknown
material overlap becomes a blocker or explicit external dependency. Distinct events document their
different timing/semantics and occurrence domains.

## Configure lifecycle and diagnostic fields explicitly

`traffic_type` serves approved internal-traffic filtering; debug-mode traffic serves developer
filters. Both Admin filters are separate external actions; see Google's
[internal](https://support.google.com/analytics/answer/10104470) and
[developer](https://support.google.com/analytics/answer/13296662) guides.
An approved diagnostic route may set `debug_mode`; production disabling uses parameter omission.
Persistent fields declare default/authenticated/reset/environment transitions.

## Record external Google and GA4 administration

Record required custom dimensions/metrics, key-event designation, stream/Enhanced Measurement,
connected destinations/shared settings/cross-domain/referral controls, and advertising/audience
activation. Each has current official evidence and status: confirmed, separately authorized,
required external work, intentionally untouched or blocking.

## Route GA4 through a server container

Reuse a compatible Google tag for identity/endpoint. A dedicated transport tag requires lifecycle,
consent, destination, environment or occurrence isolation. An endpoint variable serves actual reuse
or routing. Apply field placement above and the [identity route](../data/identity.md) for matching.

Configure and verify the [server GA4 receiver](../server/ga4.md) before endpoint cutover according to
[pipeline ordering](../pipeline/architecture-and-workflow.md#build-receiver-first). Reconcile browser
and server destinations under the same occurrence ownership.
