# Vendor consent-mode capability map

## Contents

- [Classify behavior before naming it](#classify-behavior-before-naming-it)
- [Research every browser product independently](#research-every-browser-product-independently)
- [Use the current verified capability map](#use-the-current-verified-capability-map)
- [Configure an approved advanced route](#configure-an-approved-advanced-route)
- [Handle partial or unknown support](#handle-partial-or-unknown-support)
- [Record and validate the decision](#record-and-validate-the-decision)
- [Official entry points](#official-entry-points)

## Classify behavior before naming it

Do not use `advanced consent mode` as a synonym for any built-in consent check. Classify the selected browser product from current official documentation:

| Classification | Denied or unknown behavior | Skill treatment |
| --- | --- | --- |
| `strict/basic blocked` | The vendor loader and event requests do not run before the required grant. | Default for every platform. Use the CMP vendor block. |
| `native stop/hold` | A vendor API may load or remain present, but event delivery is stopped or held and no denied-state measurement is documented. | Not advanced. Use only when explicitly selected and proven; otherwise retain strict/basic blocking. |
| `native cookie-control` | A vendor API changes cookie use, but the complete denied-state event payload or data-use contract is not established. | Not automatically advanced. Prove the remaining behavior or use strict/basic blocking. |
| `advanced consent-aware` | The tag intentionally loads under a denied default and sends officially documented cookieless, anonymized, or otherwise limited requests while restricting storage or data use. | Explicit approval required. Do not add a block that defeats the documented denied-state behavior. |
| `adaptive/anonymous analytics` | The analytics product can collect a reduced cookieless or anonymous dataset without cookie consent, often under a separate policy or exemption decision. | Treat as a vendor-native advanced-equivalent route, not automatically as legal permission or as the vendor's branded Advanced Consent Mode. |
| `unverified` | The denied-state request, storage, or data-use behavior cannot be established. | Use strict/basic blocking or mark the advanced request `Blocked`. |

Advanced matching, enhanced conversions, modeled reporting, restricted-data processing, and a template's GTM consent checkbox do not by themselves prove `advanced consent-aware` behavior.

## Research every browser product independently

Classify per browser product, not only per vendor. A vendor can expose different consent behavior for analytics, advertising, helper, and integrated products.

For every affected product and installed template, establish from current official sources:

1. the official feature name and supported browser product;
2. whether the loader executes while consent is denied or unknown;
3. whether an event or consent request is transmitted in that state;
4. the exact fields, identifiers, URL data, IP handling, and user-provided data included;
5. cookies, local storage, reads, writes, deletion, and revocation behavior;
6. whether limited signals support modeling, aggregate reporting, or another documented purpose;
7. the consent API/types, defaults, updates, regional behavior, and ordering requirements;
8. the current GTM template fields and whether the CMP supports that product;
9. the client-approved policy for that exact denied-state behavior.

Re-open the sources at execution time. The map below is a dated discovery aid, not permanent
authority and not an expansion of the selected tag-configuration scope. Matomo and Piwik PRO entries
classify consent capability only; actual tag configuration must also pass the generic analytics
destination and installed-template route.

Discovery baseline last reviewed: 2026-07-21. Record a new access date and current official evidence for every implementation.

## Use the current verified capability map

The following map was verified from official browser documentation on 2026-07-18. Current official documentation and the installed template always override it.

| Product | Officially documented denied-state capability | Classification and default |
| --- | --- | --- |
| Google tag | Contains built-in consent checks and adjusts behavior from Google consent states. | Google `advanced consent-aware` capable; strict/basic remains this skill's default. |
| Google Analytics 4 | Sends measurements without analytics cookies when the applicable storage consent is denied. | Google `advanced consent-aware` capable. Verify every applicable consent type, not only `analytics_storage`. |
| Google Ads Conversion Tracking and Remarketing | Google consent-aware tags can send restricted/cookieless measurements under denied states. Official support for Phone Call Conversions is still listed as pending. | Google `advanced consent-aware` capable for the documented tags; do not generalize to the pending phone-call product. |
| Floodlight | Listed by Google as containing built-in consent checks. | Google `advanced consent-aware` capable; verify the selected Counter/Sales and linker architecture. |
| Conversion Linker | Listed by Google as containing built-in consent checks. | Google consent-aware helper; apply the same explicitly selected Google architecture as its consumers. |
| Microsoft Advertising UET | Advanced UET Consent Mode loads immediately with `ad_storage` denied and sends anonymized data used in aggregate modeling until grant. | Microsoft `advanced consent-aware` capable; strict/basic remains the default. |
| Microsoft Clarity | Clarity's script operates in advanced mode, loads regardless of consent, and uses a limited cookieless mode without consent. `analytics_Storage` and `ad_Storage` are separate. | `advanced consent-aware` capable. Treat Clarity separately from UET even when they are integrated. |
| Matomo | `requireCookieConsent` keeps tracking requests active without cookies; `requireConsent` prevents both cookies and tracking requests. | `adaptive/anonymous analytics` capable only under an explicitly approved client policy. Do not confuse cookie consent with tracking consent. |
| Piwik PRO Analytics | Its own tracking tag can switch among consent, anonymous, or no-collection modes and can collect anonymous data from non-consenting visitors. | `adaptive/anonymous analytics` capable only when explicitly approved. The anonymous mode does not automatically apply to third-party tags. |
| TikTok Pixel | TikTok documents a Pixel cookie-consent mode and cookie enable/disable controls, while also documenting tag-manager/CMP control of the base tag. The public help page does not establish the complete denied-state event payload or an advertiser-specific advanced modeling contract. | `native cookie-control`, not automatically `advanced consent-aware`. Use strict/basic unless current product documentation and template prove the intended limited-data route. |
| Pinterest tag | `setconsent(false)` prevents events from being sent and deletes first-party session storage. | `native stop/hold`, not advanced denied-state measurement. Strict/basic remains valid. |
| Meta Pixel | No current official browser source in the implementation record proves an approved cookieless/anonymized denied-state measurement contract equivalent to Google or UET. | `unverified` for advanced behavior; use strict/basic. A grant/revoke API alone would not prove advanced measurement. |
| Snap Pixel | No current official browser source in the implementation record proves limited denied-state measurement. | `unverified` for advanced behavior; use strict/basic. |
| LinkedIn Insight Tag, Reddit Pixel, X Pixel, and Criteo OneTag | No current primary browser source in this discovery record proves a general denied-state measurement contract equivalent to Google advanced Consent Mode. | `unverified` for advanced behavior; use strict/basic until exact current product/template evidence proves another route. |

For another analytics product or any other unlisted vendor, run the same research procedure. Never infer support from a CMP toggle or a similarly named feature.

## Configure an approved advanced route

When the analyst explicitly approves a documented advanced or adaptive route:

1. Name the exact product, feature, consent types, denied-state behavior, region policy, and official sources in the plan.
2. Verify that the CMP, current template, and product account settings support that route.
3. Set the documented denied defaults early enough for that product and send stored-choice/update/revocation signals in the required order.
4. Allow only the tags and requests covered by the approved denied-state contract. Do not remove blocks from unrelated products.
5. Do not send user-provided data, advanced-matching identifiers, or another field under denial unless current official documentation and the approved policy explicitly permit that exact field.
6. Keep page-view and automatic-event decisions separate from consent initialization.
7. Derive denied, granted, late-grant, returning-visitor, and revocation expectations from the configured defaults, updates, triggers, template, and approved contract. Keep them explicitly labeled as static configuration expectations.

Make the decision per product. GA4 and Google Ads may use different approved routes. UET and Clarity require separate decisions. A vendor-wide CMP category is not sufficient evidence that all its products behave identically.

## Handle partial or unknown support

If documentation proves only cookie suppression, do not claim that event requests are anonymous. If it proves only a consent API, do not claim modeling. If it proves only modeled reporting, do not assume the browser tag may transmit under denied consent.

When any denied-state request, field, storage, or revocation behavior remains unresolved:

- keep or implement strict/basic blocking;
- record the missing official fact;
- mark an explicitly requested advanced route `Blocked` rather than approximating another vendor's design.

## Record and validate the decision

For each product, add a consent-capability row to the configuration result:

| Product | Official mode | Selected classification | Loads denied | Request denied | Storage denied | Consent API/types | CMP/template | Approval | Static status / optional supplied evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Use exact documented language for denied-state transmission. Label the final result `strict/basic blocked`, `native stop/hold`, `native cookie-control`, `advanced consent-aware`, or `adaptive/anonymous analytics`. Do not collapse them into `consent gated`.

## Official entry points

- https://developers.google.com/tag-platform/security/concepts/consent-mode
- https://developers.google.com/tag-platform/security/guides/consent
- https://developers.google.com/tag-platform/security/guides/privacy
- https://learn.microsoft.com/en-us/advertising/msa-help/hlp_ba_conc_uet_consent
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/consent-mode
- https://learn.microsoft.com/en-us/clarity/setup-and-installation/cmp-integration-guide
- https://developer.matomo.org/guides/tracking-consent
- https://matomo.org/faq/how-to/how-do-i-enforce-tracking-without-cookies/
- https://help.piwik.pro/support/privacy/setting-consent-manager/
- https://help.piwik.pro/support/questions/how-can-i-collect-anonymous-visitor-data-if-i-dont-use-piwik-pro-tag-manager-and-consent-manager/
- https://ads.tiktok.com/help/article/how-to-use-cookies-with-tiktok-pixel
- https://help.pinterest.com/en/business/article/install-the-base-code

## Non-Google server destinations

Do not infer a universal advanced consent mode from Google or Microsoft. For each server media
product, inspect whether its installed template has a native consent field/check and whether the
official server product supports limited, anonymous, cookieless, opt-out, or suppression behavior.
Use that exact mechanism only with explicit policy and evidence.

Otherwise forward an approved CMP state and apply one server blocking trigger that fails unknown
state closed. Prove event coverage for every destination trigger. Do not invent grant events such
as `microsoft_ads_consent_granted`; use the verified CMP lifecycle/state and current product
mechanics.
