# Non-GA4 analytics destinations

Use this route for approved analytics in another browser product. [Authority](../core/authority.md)
and [conformance](intake-and-conformance.md) own exact analytics semantics;
[evidence](../core/evidence.md), [templates](../templates.md) and [mapping](../data/mapping.md) own
current product capability and source-to-native implementation.

## Resolve the product graph

Establish product/edition, property/site/project and environment, library/endpoint/event method,
base/queue/shared-settings/dispatcher architecture, current field types/arrays/limits/names, and
installed version/permissions/defaults. Reconcile site/plugin/partner initialization and automatic
page/click/scroll/form/SPA ownership.

Map approved page/session/user/group/content/ecommerce/campaign semantics into the exact product
contract. SPA state update order, retained values and reset behavior require product-specific proof.
Property definitions/goals/filters remain external administration.

## Consent and identity

Apply [consent classification](../consent/product-capabilities.md) for the exact product and approved
policy. Analytics identity requires permitted purpose, source and product terms. For ordinary
non-Google identity use `analytics-user-id`, the actual `user_id` field, truthful tag-wide/same-event
timing and `hashing_owner: not-applicable`. Record login/identify and logout/reset behavior.
Advertising matching has its separate [identity contract](../data/identity.md).

## Vendor-specific routing


Use current official entry points for the exact product. Examples include:

- Matomo browser tracking and GTM installation: https://matomo.org/faq/new-to-piwik/how-do-i-use-matomo-analytics-within-gtm-google-tag-manager/
- Matomo consent: https://developer.matomo.org/guides/tracking-consent
- Piwik PRO tracking code through GTM: https://help.piwik.pro/support/getting-started/google-tag-manager-install-a-tracking-code/
- Piwik PRO consent: https://help.piwik.pro/support/privacy/setting-consent-manager/
- Adobe Experience Platform/Web SDK: https://experienceleague.adobe.com/docs/experience-platform/web-sdk/home.html

Vendor-owned tag managers are separate administration systems. This route configures their browser
destination through an established GTM implementation.

## Useful supported routes to investigate

These discovery aids require current source and installed-version inspection:

| Product | Configuration opportunity / correctness check | Official feature guide |
| --- | --- | --- |
| Matomo | Separate tracker initialization/page tracking from event dispatch. Its documented GTM templates can map ecommerce; verify native event/category/action semantics and item shapes instead of copying GA4 names. The configured surface is Google Tag Manager. | [GTM ecommerce](https://matomo.org/faq/tag-manager/how-to-track-google-tag-manager-ecommerce-events-in-matomo/) |
| Piwik PRO | Distinguish browser tracker installation, proxy/script serving, and actual server event forwarding. A proxy alone is not server-side destination configuration. | [Server GTM integration](https://help.piwik.pro/support/integrations/google-tag-manager-server-side-integration/) |
| Adobe Analytics | Select AppMeasurement versus Web SDK deliberately. For AppMeasurement SPA work, page/link calls and variable clearance are distinct responsibilities; each hit uses its own current values. Establish GTM template support separately from Adobe Tags. | [AJAX implementation](https://experienceleague.adobe.com/en/docs/analytics/implementation/other/ajax) |
| Piano Analytics | The PA SDK GTM template exposes configuration, events, consent updates, and a native GA ecommerce bridge. Use the bridge only after checking its event/property mapping against the approved Piano contract; prefer a compatible native bridge. | [PA SDK template](https://analytics-docs.piano.io/en/analytics/v1/google-tag-manager-pa-sdk-template) |
| Amplitude | Inspect autocapture, attribution, identity reset, region, and initialization consumers. Configuration precedence can replace a whole nested object through a shallow merge; read back the effective options. Enable only the approved automatic collection/replay scope. | [GTM client template](https://amplitude.com/docs/data/source-catalog/google-tag-manager) |
| Mixpanel | Inspect the native template's instance initialization, identity/reset, persistence, automatic collection and region. Keep initialization options consistent; template defaults can differ from the JavaScript SDK. | [Official GTM integration](https://docs.mixpanel.com/docs/tracking-methods/integrations/google-tag-manager) |

## Acceptance

Verify the saved base/event ownership, identity, full effective fields, consent/settings, template,
automatic behavior and references. [Acceptance](../core/acceptance.md) owns the final verdict and
external property/runtime dependencies.
