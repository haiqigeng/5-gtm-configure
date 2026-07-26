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

Read back base/event separation, destination identity, complete field set, triggers, consent,
settings, template version, automatic behavior, and all references. Report external property setup
and required runtime recette separately. `Configured` proves the saved GTM graph, not that the
vendor received or processed data.
