# Affiliate browser tags

## Scope and authority

Use this category route for an explicitly requested client-side affiliate conversion or journey tag
when no deeper platform file exists. The media brief owns the commercial action, program/network,
advertiser identity, destination/environment, and approved commercial fields. Current official
network documentation owns the browser event, template, parameter, basket, and deduplication schema.

Do not infer one network from another. A sale, lead, basket, commission, voucher, publisher, or
journey parameter has network-specific semantics even when its label looks familiar.

## Resolve the browser architecture

Before mutation, establish:

1. exact affiliate network, advertiser/program identity, region and environment;
2. official supported GTM/native/community template and installed version;
3. base/journey/page tag requirements and whether another site/plugin/partner path already owns it;
4. conversion event and platform-side goal/action identity;
5. browser cookie/link-decoration, attribution, consent, and cross-domain requirements;
6. external feed, voucher, commission-group, product-code, or platform activation dependencies.

Use a supported template first. When the template is not installed, install it only through an
authorized Gallery/template path after publisher, permissions, version, fields, and automatic
behavior are verified. Do not silently paste an affiliate script into Custom HTML; block when the
supported installation path or required authority is unavailable. Custom HTML is allowed only when
the network's current official browser documentation requires it and no suitable supported template
exists.

## Map conversion and basket fields

Build a browser-specific field matrix with requirement status, type, source, GTM variable, installed
template field, consent, and evidence. Common decision families include:

- order/transaction or lead reference used for network-side duplicate control;
- amount, tax, shipping, discount, commission or revenue basis, and currency;
- voucher/coupon, new-customer, customer-segment, program, campaign, or publisher values;
- product/basket rows with the exact network item ID, name, category, price, quantity, and line
  amount rules;
- explicit conversion type, group, or goal identifier.

Do not assume GA4 `items`, `item_id`, `value`, or `transaction_id` already match the affiliate
contract. Transform only the real shape difference and preserve zero, false, one item, and every
approved item. Map fields directly when the source already matches. Do not add an `Eligible`
Custom JavaScript variable or filter out runtime rows merely because recette evidence is absent.

Treat an approved order/reference field as the network's browser conversion key only when current
documentation says so. Do not invent a random event ID. Browser/server deduplication and server
postbacks remain deferred even if the same order reference will later participate in them.

## Prevent duplicate owners

Inspect existing GTM, site code, ecommerce plugin, affiliate module, tag template, and known
platform rules. Configure one browser owner for the approved conversion. Reconcile page-load versus
dataLayer timing, refresh/revisit behavior, SPA navigation, once-per-event/page settings, and any
documented network duplicate-control field. Never disable an existing path without explicit
remove/update authority.

## Consent and readback

Apply strict/basic CMP blocking to base/journey and conversion tags by default. Use another
network-specific consent route only when explicitly requested and established by current official
browser documentation.

Read back advertiser/program identity, base and conversion tags, every field and basket mapping,
template/version, triggers, consent, firing options, duplicate owner, consumers, and external
platform dependencies. `Configured` proves the saved browser graph, not affiliate attribution,
commission calculation, network receipt, or server postback behavior.

## Server route

For a partner postback/server pixel, load `server/media-affiliate.md` and require the exact official
partner contract. There is no universal affiliate server payload or dedup rule.
