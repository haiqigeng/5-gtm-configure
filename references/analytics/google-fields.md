# Google field ownership

## Choose the narrowest correct owner

Assign each Google field by semantic lifetime, consumer set, destination and consent route. A
single-event field belongs to that event. Shared settings apply when the enumerated consumers have
identical source/type/missing behavior, destination/consent compatibility and intended change scope.
Inspect every consumer before editing a shared setting.

[GA4 ownership](ga4-ownership.md) owns destination identity and page-view occurrences;
[identity](../data/identity.md) owns identity features/lifecycle;
[ecommerce](ga4-ecommerce.md) owns the event's commerce route. This matrix owns native placement.

## Use the ownership matrix

| Field or behavior | Authoritative GTM owner |
| --- | --- |
| Measurement ID / Google tag ID  |  Google tag or exact native destination field; a Constant may hold a repeated stable ID |
| `send_page_view` and other Google-tag initialization behavior  |  Google tag or Configuration Settings variable shared by every enumerated compatible Google tag |
| `server_container_url` / transport URL  |  Google tag or compatible shared Configuration Settings variable |
| Cross-domain linker/configuration fields  |  Google tag or compatible Configuration Settings variable |
| Initial automatic page-view context (`page_title`, `page_location`, `page_referrer`)  |  Documented Google tag configuration fields resolved before its automatic view |
| Explicit page-view context or another one-event GA4 parameter  |  The owning GA4 Event tag; with exclusive ownership of that occurrence |
| Repeated GA4 event parameter  |  Event Settings variable only after all consumers and lifecycle match |
| GA4 user property  |  GA4 Event tag user-properties area, or a narrowly shared Event Settings user-properties area |
| GA4 `user_id`  |  Google tag configuration, with the documented login/logout lifecycle |
| GA4 user-provided data (`user_data`)  |  Native User-Provided Data variable selected on only the authorized GA4 Event tag(s) |
| Google Ads enhanced-conversion user data  |  Authorized tag-wide Google tag collection, a documented event override bound to inspected native Ads conversion-tag fields, or a User-Provided Data Event tag for earlier-page capture. Reuse sufficient existing collection; follow the [Ads procedure](../vendors/google-ads/web.md#configure-enhanced-conversions-only-explicitly). |
| Google Ads server enhanced-conversion transport  |  `google-ads-server-user-data-transport`: documented event-scoped `user_data` on the GA4 sender with native UPD; web-only scope records the external receiver dependency. Pipeline scope binds the receiving server Ads Conversion Tracking tag; separately authorized tag-wide scope remains a pipeline route. |
| Google Ads server prior-page user-data event  |  `google-ads-server-user-provided-data-event`: Google tag or documented GA4 Event override resolves `user_data` on the approved capture event; the server User-provided Data Event tag consumes it |
| GA4 ecommerce object  |  One GA4 Event tag ecommerce route: native Data Layer or compatible Custom Object |
| Google Ads conversion value, currency, transaction ID, and vendor fields  |  Exact installed Google Ads template fields on the conversion tag, or a narrowly shared supported setting |

The site's dataLayer is a shared source contract. Map its actual keys to the selected product fields
and inspect browser defaults before overriding them. User-ID, user properties, matching data and
ordinary event parameters retain these separate native namespaces.

## Verify inherited fields

Expand every inherited Configuration Settings/Event Settings variable into each consumer's effective
payload. The shared native resolver preserves stored representation and applies local overrides by
exact parameter name, including documented empty overrides. Effective ownership requires resolved,
unique, acyclic references and the complete consumer context.

For scalar GA4 event mappings, destination identity (including a literal Constant) can establish
one unpaused same-target Google tag supplying defaults. Event settings and local rows override
those defaults. Record static field proof separately from variable evaluation timing and Google-tag
initialization, which require their own lifecycle evidence. Read back the settings variable and
every changed/reused consumer.

## Treat browser transport as client-side configuration

A web Google tag's `server_container_url` routes its browser request to the endpoint. Measurement
identity and endpoint jointly describe that route. Preserve its consumers and occurrence ownership.
Web-only scope records receiver work externally; authorized pipeline scope models separate receiving
objects under [authority](../core/authority.md).

Expand inherited sender settings through the proved wire field, claiming Client/Event Data path and
server consumer using the [transport contract](../pipeline/transport-data-contract.md).
