# Google Ads browser tags

Apply the [media contract](../../media/common.md) and its linked implementation owners.

## Establish the requested Google Ads product

Select the approved architecture: direct conversion action, standard/dynamic remarketing, Google
tag destination, linker, enhanced conversions or imported GA4 key event. Resolve conversion/destination
ID, label, completed business action, fixed/dynamic value/currency, order identity, audience purpose,
business vertical/feed, selected user-data feature and consent policy.

Current official product documentation and native Google tag/Ads/Linker fields establish the
implementation. Stable reused IDs/labels can use named constants.

## Design conversion tracking and remarketing

Each action/label has its event tag unless the current template supports a fully compatible
parameterized design. Map number-valued conversion value, ISO currency and actual stable order ID
to exact native fields. The approved completed business event owns its trigger. Apply
[mapping](../../data/mapping.md) for required-source readiness and runtime missing-data treatment.

Reuse sufficient site-wide remarketing. Dynamic remarketing selects the business vertical's current
event/item contract and actual feed IDs; preserve its complete approved item array and exact types.

## Decide attribution architecture

Inspect existing Google/Ads/Floodlight tags and current guidance to determine linker coverage.
[Linker/cross-domain](../../web/linker-cross-domain.md) owns click identity, domain/form decoration,
approved domain lists and shared consumer analysis. Record the actual landing-page coverage or gap.
Reconcile direct Ads conversion, GA4 import, automatic events and site code as distinct occurrence
owners. Platform conversion/feed/account administration remains external work.

## Configure enhanced conversions only explicitly

[Identity](../../data/identity.md) owns feature authority, source/timing/hash lifecycle and permitted
consumers. [Google fields](../../analytics/google-fields.md) owns placement. This section selects
Google Ads' concrete collection implementation.

### Resolve current account and Google tag settings

Reopen the [2026 settings update](https://support.google.com/google-ads/answer/16884284?hl=en): website,
Data Manager and API collection can coexist, and web/leads share an enhanced-conversions switch.
Inspect effective activation, including automatically migrated settings. Customer lists and offline
uploads retain separate capabilities and scope.

Distinguish activation/terms, [Google tag capability](https://support.google.com/tagmanager/answer/12131703?hl=en),
source collection and consent. Enumerate connected destinations. Enabled forwarding capability
and each destination's product activation require separate evidence and external owners.

### Select the documented collection route

Use the [GTM procedure](https://support.google.com/google-ads/answer/13262500?hl=en) and
[Google tag procedure](https://support.google.com/google-ads/answer/13258081?hl=en).

| Observed situation | Selected implementation |
| --- | --- |
| Existing in-page `gtag('set', 'user_data', ...)` or Google tag collection | Reuse when Ads destination, effective settings, consent and conversion-time availability are sufficient; record website ownership externally. |
| Data available with conversion | Authorized tag-wide Google collection or documented native Ads conversion-event override, with the corresponding consumer scope. |
| Data available earlier only | Native User-Provided Data Event with documented Form Submission trigger and approved forms; establish any custom-event compatibility separately from the later conversion. |
| Automatic collection/CSS/JavaScript selectors | Explicitly approved collection scope, exclusions, timing and sources. |
| URL-based conversion | Google's supported selector or automatic route for that method. |

The browser prior-page tag's native short code still requires authentic readback/export proof.
Inspect saved type and fields against runtime support before mutation; unsupported native capability
holds that route. Display labels and synthetic fixtures establish neither native identity nor support.

The native [User-Provided Data variable](https://support.google.com/tagmanager/answer/7683362?hl=en)
has Manual variable mapping, Code structured DLV/JavaScript input and Automatic collection modes.
A supported structured source can be direct. Determine match-key requirements per selected
procedure; GTM and in-page guides differ on phone-only eligibility.

### Bind inspected native fields before saving

Use `google-ads-tag-wide-user-data` for Google tag collection, or
`google-ads-enhanced-conversions` with `same-event` for a native Ads event override.
Each override's `consumer_bindings` contains:

- `user_data_path`: inspected native parameter value holding the approved UPD variable;
- `activation_paths`: native boolean controls enabled for the selected route, or `[]` when none applies;
- `field_review`: actual UI/export/schema locator reconciled with the current official procedure and event scope.

The supported Ads conversion-event binding selects the `user_data` row in native
`eventSettingsTable`: `["parameter", "eventSettingsTable", "list", <row>, "map", "parameterValue", "value"]`.
The same row's `parameter` cell is exactly `user_data`. Read back that complete native table,
any actual activation controls, the native UPD variable and its source references. Inspected
source/UI capability and saved field retention establish configuration support together.
An unsupported override remains blocked or uses another already-authorized supported route.
Actual installed controls determine capability; unrelated Floodlight/SA360 UI changes have their own
product scope. Earlier collection may use an Ads cookie alongside the independently required
`ad_user_data` and `ad_storage` decisions.

Offline checks exercise field-binding invariants; authentic saved readback establishes configuration.
Request contents, empty-data diagnostics and
match results belong to runtime/platform verification. Server transport and prior-page server
capture use the distinct [identity routes](../../data/identity.md) and [server guide](server.md).

The browser Google-tag collection route selects `user_data` under Event Parameters and has
tag-wide consumer lifetime. The server Google-tag carrier's documented Configuration parameter
has its own pipeline authority. The approved event/consumer scope selects the route before authoring.

## Coordinate consent and verify

[Google consent](../../consent/google.md) owns defaults/updates and compatible policy across each
shared Google/Ads/linker execution unit. Inspect saved destination/label, event fields, feed/value/
currency, user-data controls, consumers, occurrence ownership and the no-op result. Record imported
conversion choice, account activation, feed and platform setup separately.

## Official entry points

- https://support.google.com/google-ads/answer/7521212
- https://support.google.com/tagmanager/answer/6106009
- https://support.google.com/google-ads/answer/7305793
- https://support.google.com/google-ads/answer/13262500
- https://support.google.com/google-ads/answer/13258081
- https://support.google.com/google-ads/answer/16884284
- https://support.google.com/tagmanager/answer/12131703
- https://support.google.com/tagmanager/answer/7683362
- https://developers.google.com/tag-platform/security/concepts/consent-mode

## Server route

For server delivery, load [Server](server.md). Reconcile native migration, Conversion Linker,
enhanced conversions and retained browser conversions under Google's exact product contract.
