# Google field ownership

## Contents

- [Choose the narrowest correct owner](#choose-the-narrowest-correct-owner)
- [Use the ownership matrix](#use-the-ownership-matrix)
- [Keep identifiers and user data distinct](#keep-identifiers-and-user-data-distinct)
- [Keep ecommerce on one route](#keep-ecommerce-on-one-route)
- [Treat browser transport as client-side configuration](#treat-browser-transport-as-client-side-configuration)
- [Verify inherited fields](#verify-inherited-fields)

## Choose the narrowest correct owner

Assign every Google field to exactly one GTM surface before mutation. Choose by semantic lifetime,
consumer set, destination, and consent route—not by whichever UI table is easiest to populate.
Shared settings variables are optional reuse mechanisms, not default storage locations.

Bind the page-view decision to actual in-scope objects. An automatic owner must be the referenced
Google tag with the exact destination identity and effective `send_page_view: true`. A dedicated `page_view` owner must be a referenced
GA4 Event tag while its referenced Google tag has effective `send_page_view: false`. External or
intentionally-none ownership must keep the Google tag false when one exists; an external owner also
names the external dependency. A declaration without these object/field checks is not proof.

Use the narrowest owner that matches the field's real lifecycle. A field owned by one event stays on
that event. A configuration value shared by the same enumerated Google tags may use a Configuration
Settings variable. A genuinely shared event parameter or GA4 user property may use an Event
Settings variable only when every consumer has the same source, type, missing behavior,
destination, and consent route.

## Use the ownership matrix

| Field or behavior | Authoritative GTM owner | Do not place it in |
| --- | --- | --- |
| Measurement ID / Google tag ID | Google tag or exact native destination field; a Constant may hold a repeated stable ID | Event Settings variable, arbitrary DLV inferred from its destination name |
| `send_page_view` and other Google-tag initialization behavior | Google tag or Configuration Settings variable shared by every enumerated compatible Google tag | GA4 event parameters or Event Settings variable |
| `server_container_url` / transport URL | Google tag or compatible shared Configuration Settings variable | GA4 event parameters, user properties, or a server-container object invented in this client-side run |
| Cross-domain linker/configuration fields | Google tag or compatible Configuration Settings variable | Event Settings variable |
| One-event GA4 parameter | That GA4 Event tag | Google tag configuration or broadly shared Event Settings variable |
| Repeated GA4 event parameter | Event Settings variable only after all consumers and lifecycle match | Configuration Settings variable |
| GA4 user property | GA4 Event tag user-properties area, or a narrowly shared Event Settings user-properties area | Event-parameter table, Google tag configuration fields |
| GA4 `user_id` | Google tag configuration, with the documented login/logout lifecycle | GA4 user properties, custom dimensions, `user_data`, dummy or hashed-email substitutes |
| GA4 user-provided data (`user_data`) | Native User-Provided Data variable selected on only the authorized GA4 Event tag(s) | Shared Event Settings variable, GA4 user properties, ordinary analytics parameters |
| Google Ads enhanced-conversion user data | Native Google tag / Google Ads enhanced-conversion field, event override, or User-Provided Data Event tag according to timing | GA4 `user_data` by analogy, ordinary conversion parameters, Custom HTML hashing |
| GA4 ecommerce object | One GA4 Event tag ecommerce route: native Data Layer or compatible Custom Object | Shared Event Settings variable, parallel manual `items`, `items.0.*` scalar fields |
| Google Ads conversion value, currency, transaction ID, and vendor fields | Exact installed Google Ads template fields on the conversion tag, or a narrowly shared supported setting | GA4 parameter table merely because names overlap |

This matrix is authoritative for Google-field placement. Platform playbooks may add
product-specific requirements, but must link here rather than restating a conflicting owner.

## Keep identifiers and user data distinct

`user_id`, GA4 user-provided data, Google Ads enhanced-conversion data, and a media vendor's advanced
matching are separate features. They have different identifiers, destinations, activation steps,
consent behavior, timing, and supported fields. Never move a value between them by analogy.

Load `first-party-data.md` whenever any of those features is in scope. In particular, do not make
`user_id` a GA4 user property and do not distribute `user_data` through a shared Event Settings
variable.

## Keep ecommerce on one route

For one GA4 event, select exactly one ecommerce owner:

1. native **Data Layer** ecommerce when the approved event push contains a compatible GA4
   ecommerce object;
2. native **Custom Object** when one approved GTM variable returns the complete compatible object;
3. explicit manual parameters only when the native route cannot represent the approved contract and
   current template documentation supports the manual field.

Never enable native ecommerce and also map `items` manually. Never put transaction-specific
ecommerce or `items` in a broadly shared Event Settings variable. Preserve the complete array; do
not flatten it into `items.0.*`, filter it through an eligibility helper, or suppress the event
because runtime values may be absent.

## Treat browser transport as client-side configuration

A client-side Google tag that carries `server_container_url` still executes in the web container
and remains in this skill's scope. Its browser request is routed to the supplied server endpoint;
the tag does not send one independent copy to the normal Google endpoint and another to the server
endpoint merely because both the measurement ID and transport URL are present.

Inspect and preserve the client tag, transport setting, consumers, and page-view ownership when
authorized. In a web-only run, treat the server container's clients, transformations, tags,
routing, and browser/server deduplication as external. In an authorized pipeline run, model and
verify them as separate server-target objects; never infer server authority from the web setting.

## Verify inherited fields

Before saving, expand every inherited Configuration Settings and Event Settings variable into each
consumer's effective payload. Verify no event receives an unintended parameter, user property,
ecommerce object, identifier, user-data field, destination, or consent behavior. Read back both the
settings variable and every changed/reused consumer.

## Add transport ownership without mixing field layers

For a server route, add one owner for the Google tag's server endpoint and one owner for effective
`send_page_view`. Configuration Settings may own stable transport/config values shared by their
consumers. Event Settings may own genuinely shared event parameters, but must not become a global
bucket for event-specific data. Put GA4 user properties in their dedicated section; keep
`user_data` in the current feature-specific user-provided-data route and never in user properties.

Expand inherited settings through every web sender and prove the resulting wire field, claiming
Client Event Data path, and server consumer. Do not assume that a value visible in the web tag UI
survives the Client unchanged.
