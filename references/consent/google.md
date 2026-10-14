# Google product-family Consent Mode

## Coordinate product policies with execution units

Verify current supported products: Google tag, GA4, Ads Conversion Tracking/Remarketing, Floodlight
and Conversion Linker. Phone Call Conversions has been listed as pending; establish current support
for the exact product at implementation time.

A shared Google tag/helper is one executable consent surface. Inventory connected destinations and
consumers; their selected policies must all be compatible with that unit's actual behavior. A
supported destination-specific separation requires official capability and analyst authority.
Otherwise hold the affected architecture for resolution.

[Web consent](web.md) owns the default strict/basic eligibility mechanism and existing conventions.
Explicitly approved advanced behavior permits documented limited/cookieless execution under denied
defaults. Explain the measurement choice: basic sends nothing under denial and supports general
modeling; advanced may support advertiser-specific modeling from its limited signals, subject to
Google's eligibility requirements. See the
[official comparison](https://developers.google.com/tag-platform/security/concepts/consent-mode).

## Verify consent types and their owner

Map the client-approved policy independently for each applicable type:

| Type | Product behavior |
| --- | --- |
| `analytics_storage` | Analytics storage. |
| `ad_storage` | Advertising storage. |
| `ad_user_data` | Transmission of user data for Google advertising. |
| `ad_personalization` | Personalized advertising. |

Establish any additional feature-specific types/settings from current sources. Record applicable
products/regions and the single default/update owner: site, CMP template, existing tag or authorized
new CMP tag. Google's [EEA guidance](https://support.google.com/tagmanager/answer/13695607) and
[EU user consent policy](https://www.google.com/about/company/user-consent-policy/) identify their
applicable territories and uses. The client owns the legal decision; the configuration proves its
required signal ownership and timing. External owners retain separately evidenced dependencies.

## Configure state and eligibility at their owners

| Surface | Responsibility |
| --- | --- |
| Default/update state | Defaults precede affected tags; current choice and revocation update on the interaction page before transition. |
| Built-in checks | Native changes to storage/transmission in executing consent-aware tags. |
| Strict/basic eligibility | Complete grant before execution, through the selected [web mechanism](web.md). |
| Custom-template consent APIs | Permissioned CMP implementation uses `setDefaultConsentState` and `updateConsentState`; unknown-state handling accounts for `isConsentGranted` treating unset as granted. |

Use the supported CMP/template APIs for in-GTM state ownership. Preserve independent values unless
the approved CMP mapping establishes equivalence. Match each helper/config/event/conversion/linker
to compatible product policy and recorded built-in behavior. Basic-mode signal verification occurs
when the tag becomes eligible; network propagation requires field testing.

## Configure approved advanced behavior

Consent-default logic fires on Consent Initialization before affected Google tags. Set the approved
defaults and update promptly on stored choice, interaction and revocation. The selected execution
path allows exactly the documented denied-state requests with their native storage/data behavior.
Eligibility controls align with that selected policy.

Optional settings require their own approved purpose and current product support: `region` with
precedence understood, `wait_for_update` with an expected bounded update, `ads_data_redaction` for
the selected advertising behavior, `url_passthrough` with approved same-domain URL handling, and
linker/cross-domain settings from the domain architecture.

## Record static consent assertions

Derive defaults, update/revocation order, per-type values, eligibility and permitted denied-state
behavior from the complete graph and product evidence. Record built-in and additional checks.
[GA4 ownership](../analytics/ga4-ownership.md) independently resolves page-view occurrences;
[consent lifecycle](lifecycle.md) resolves initialization and later-grant opportunities.

Label the result `strict/basic blocked` or `advanced consent-aware` with static expectations.
[Acceptance](../core/acceptance.md) distinguishes this proof from observed browser behavior.

## Server pipeline ownership

The web default/update owner supplies Google consent state through the Google request. Receiving
consent-aware Google tags use `incoming-google-consent-native` under the current product contract.
Prove web timing, carried signals and each server tag's native behavior. Strict/basic transport may
be absent until grant; approved advanced transport can carry limited requests. A separate server
condition requires its own documented product purpose under [server consent](server.md).

## Official entry points

- https://developers.google.com/tag-platform/security/concepts/consent-mode
- https://developers.google.com/tag-platform/security/guides/consent
- https://developers.google.com/tag-platform/security/guides/privacy
- https://support.google.com/tagmanager/answer/10718549
- https://developers.google.com/tag-platform/security/guides/consent-debugging
