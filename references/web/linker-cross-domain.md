# Conversion Linker and cross-domain architecture

## Establish attribution ownership

Inspect Google tags/destinations, Ads/Floodlight consumers, existing linkers, site/plugin paths,
domains/forms and property settings. Determine whether each requirement belongs to GTM, GA4 Admin,
Google settings or website code. GA4 cross-domain configuration normally belongs to Admin; record
that externally unless an exact GTM override is authorized.

## Decide whether a Conversion Linker is required

Select a linker when current product architecture requires its attribution-cookie/incoming-parameter
behavior and existing compatible coverage is insufficient. Reuse one for consumers with aligned
triggers, domains, consent/settings and ownership.

[Google guidance](https://support.google.com/tagmanager/answer/7549390) says a Google tag on every
page supplies browser linker behavior, and Ads/Floodlight tags initiate a Google tag before events.
Inspect actual landing-page coverage and custom domain/cookie needs before adding or retiring a
linker. Server Conversion Linker requirements are established separately for that server product.

## Configure cross-domain behavior

Use an approved domain list and current native fields. Resolve exact domain matching, incoming
acceptance, form decoration, query/fragment position, scope/order and `_gl`/click/cookie behavior.
Form decoration uses Query Parameter placement. Third-party/payment domains require approved
journey participation and a supported return path. Match behavior must fit the intended domain set.

[Google consent](../consent/google.md) owns compatible policy across the linker and connected
execution units. Distinct GA4/Ads/Floodlight destinations retain their domain/policy requirements;
unresolved shared-unit incompatibility holds that configuration.

## Verify saved configuration

Compare linker fields, domains, triggers, incoming/decoration/position settings, consent and
consumer references. Establish one compatible attribution owner. Record Admin/site/provider work
and runtime journey/decoration checks as external dependencies under
[acceptance](../core/acceptance.md).
