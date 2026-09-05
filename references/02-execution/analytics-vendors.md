# Non-GA4 analytics destinations

## Contents

- [Scope](#scope)
- [Authority](#authority)
- [Research and template gate](#research-and-template-gate)
- [Design the analytics graph](#design-the-analytics-graph)
- [Consent and identity](#consent-and-identity)
- [Vendor-specific routing](#vendor-specific-routing)
- [Acceptance](#acceptance)

## Scope

Use this generic route for an approved client-side analytics requirement whose destination is not
Google tag/GA4. GA4 remains the deepest first-class analytics playbook. Lack of a dedicated vendor
file never permits schema inference.

## Authority

Use the approved tracking plan or exact direct analytics decision for business meaning, event,
fields, literals, source mappings, filters, and success timing. Use current official destination
documentation and the installed GTM template for technical validity and field implementation.

Do not translate a GA4 event or ecommerce payload by analogy. A similarly named event in Adobe,
Matomo, Piwik PRO, Piano, Amplitude, Mixpanel, or another product is a separate destination contract.

## Research and template gate

Before design:

1. open the vendor's current official browser collection documentation;
2. identify product/edition, site/property identity, library or endpoint, event method, and schema;
3. inspect the exact native, official, gallery, organization-owned, or custom template;
4. establish template permissions, code/version, automatic behavior, and available fields;
5. confirm source types, arrays, null behavior, limits, reserved names, identity fields, and consent;
6. record property-side administration separately.

Use the native tag first, then an official/vendor-supported template, then a verified organization-
owned template, then another reviewed Gallery template. Block the affected requirement when no
current primary schema or safe supported-template install/update path can be established. Custom
HTML is allowed only when the vendor currently documents that browser implementation and no suitable
supported template exists; it is never an automatic fallback for missing product knowledge or
permission.

## Design the analytics graph

Determine whether the product requires a base/configuration tag, event tags, command queue, shared
settings variable, or one event-dispatch template. Reconcile hard-coded, plugin, partner, or existing
container implementations before adding another initialization path.

For every destination, resolve this operational surface rather than stopping at generic research:

- property/site/project identity and environment routing;
- one compatible base/configuration path and its page-load or initialization ownership;
- official browser event method/name and every approved event field;
- page, session, user, group, content, ecommerce, and campaign identities only where the approved
  analytics contract and product support them;
- automatic page views, click/scroll/form capture, SPA tracking, and duplicate ownership;
- consent, anonymous/adaptive behavior, cookies/storage, and reset/revocation mechanics;
- property-side definitions, goals/conversions, filters, or settings that remain external.

Map every field through source, GTM resolution, installed-template field, and official destination
parameter. Preserve exact approved semantics and map runtime values directly. A design-time missing
required field blocks; a value absent at runtime is a source/recette dependency and does not justify
a speculative Boolean eligibility variable. For SPAs, establish state update order, virtual
page-view ownership, retained values, and duplicate prevention from current product documentation.

## Consent and identity

Default to strict/basic CMP blocking. Use another consent route only when explicitly approved and
currently documented for the exact browser product. Keep anonymous, adaptive, cookie-control, and
no-request behavior distinct; do not call each one advanced consent.

Do not pass advertising matching data, raw PII, or another product's user identifier into an
analytics destination unless the exact approved analytics contract and current product terms permit
it. Treat property/site IDs as controlled destination inputs.

For an approved ordinary non-Google analytics identity, use the `analytics-user-id` first-party
route with the product's actual `user_id` field, truthful tag-wide or same-event timing, and
`hashing_owner: not-applicable`. Record the login/identify source and the logout/reset behavior in
the requirement and implementation evidence; do not relabel it as advertising matching.

## Vendor-specific routing

Use current official entry points for the exact product. Examples include:

- Matomo browser tracking and GTM installation: https://matomo.org/faq/new-to-piwik/how-do-i-use-matomo-analytics-within-gtm-google-tag-manager/
- Matomo consent: https://developer.matomo.org/guides/tracking-consent
- Piwik PRO tracking code through GTM: https://help.piwik.pro/support/getting-started/google-tag-manager-install-a-tracking-code/
- Piwik PRO consent: https://help.piwik.pro/support/privacy/setting-consent-manager/
- Adobe Experience Platform/Web SDK: https://experienceleague.adobe.com/docs/experience-platform/web-sdk/home.html

Treat vendor-owned tag managers such as Adobe Tags or Matomo Tag Manager as other systems. This
skill configures their browser destination from GTM only when a current supported path exists; it
does not administer those tag managers.

## Acceptance

### Useful supported routes to investigate

These are decision aids, not a frozen template catalogue. Reopen the linked feature guide and
inspect the actual installed version before selecting fields:

| Product | Configuration opportunity / correctness check | Official feature guide |
| --- | --- | --- |
| Matomo | Separate tracker initialization/page tracking from event dispatch. Its documented GTM templates can map ecommerce; verify native event/category/action semantics and item shapes instead of copying GA4 names. Do not confuse Matomo Tag Manager with Google Tag Manager. | [GTM ecommerce](https://matomo.org/faq/tag-manager/how-to-track-google-tag-manager-ecommerce-events-in-matomo/) |
| Piwik PRO | Distinguish browser tracker installation, proxy/script serving, and actual server event forwarding. A proxy alone is not server-side destination configuration. | [Server GTM integration](https://help.piwik.pro/support/integrations/google-tag-manager-server-side-integration/) |
| Adobe Analytics | Select AppMeasurement versus Web SDK deliberately. For AppMeasurement SPA work, page/link calls and variable clearance are distinct responsibilities; retained variables must not leak across hits. Adobe Tags instructions do not establish a GTM template. | [AJAX implementation](https://experienceleague.adobe.com/en/docs/analytics/implementation/other/ajax) |
| Piano Analytics | The PA SDK GTM template exposes configuration, events, consent updates, and a native GA ecommerce bridge. Use the bridge only after checking its event/property mapping against the approved Piano contract; do not build redundant CJS when the native bridge fits. | [PA SDK template](https://analytics-docs.piano.io/en/analytics/v1/google-tag-manager-pa-sdk-template) |
| Amplitude | Inspect autocapture, attribution, identity reset, region, and initialization consumers. Configuration precedence can replace a whole nested object through a shallow merge; read back the effective options. Do not accidentally enable replay or unrequested automatic events. | [GTM client template](https://amplitude.com/docs/data/source-catalog/google-tag-manager) |
| Mixpanel | Inspect the native template's instance initialization, identity/reset, persistence, automatic collection and region. Keep initialization options consistent; template defaults can differ from the JavaScript SDK. | [Official GTM integration](https://docs.mixpanel.com/docs/tracking-methods/integrations/google-tag-manager) |

For another product, establish its exact official GTM/SDK route and inspected template. These
research routes are not certification of an installed implementation.

### Saved acceptance

Read back base/event separation, destination identity, complete field set, triggers, consent,
settings, template version, automatic behavior, and all references. Report external property setup
and required runtime recette separately. `Configured` proves the saved GTM graph, not that the
vendor received or processed data.
