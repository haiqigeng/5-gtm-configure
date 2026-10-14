# Meta Pixel browser tags

Apply the [media contract](../../media/common.md) and its linked implementation owners.

## Resolve Meta semantics

Establish Pixel/dataset ID, account/environment, business action and optimization/conversion/audience
use, current standard/custom event, catalog identifier convention, applicable value/currency/order
and item fields, and selected matching scope. Inspect the current official Pixel reference and exact
installed template publisher/version, fields, defaults, permissions and automatic behavior.
Critical event/schema decisions require current Meta evidence, including an alternative official
source when a page is unavailable.

## Configure the collection owner

Reconcile GTM, site, plugin, partner and automatic initialization. `Meta - Config` represents a
required uncovered initialization path. `Meta - Event - PageView` represents the approved page-view
occurrence; business events such as `Meta - Event - Purchase` use their approved source action.
Events Manager Custom Conversion/optimization setup has separate platform evidence.

## Project the exact browser payload

`content_ids` and `contents` have their own documented array contracts. Preserve all approved items,
the actual Meta catalog identifiers, exact number/string types and approved value/currency rules.
Each selected `content_type`, quantity or other optional field requires its approved meaning/source.
Use direct values for compatible terminal shapes; necessary projections can use
`CJS - Meta - content_ids` or `CJS - Meta - contents` with the shared static vectors.

## Bind approved advanced matching

[Identity](../../data/identity.md) owns feature scope, source and hash lifecycle. For native
`advancedMatchingList`, create a scalar mapping/route for each approved matching field (`em`, `ph`,
etc.). Each route binds its own source and exact value cell through `consumer_bindings.user_data_path`,
for example `["parameter", "advancedMatchingList", "list", 0, "map", "value", "value"]`.
The row's `name` matches the selected field. Bind `activation_paths` to
`["parameter", "advancedMatching", "value"]` and record `field_review`.

## Verify the Meta decisions

Check initialization/occurrence ownership, event/dataset identity, complete item projections,
matching cells and consent in the saved graph. Use the
[capability classification](../../consent/product-capabilities.md) for any proposed Meta-native
limited-data route. Catalog, Custom Conversion, optimization and publication remain separate actions.

## Official entry point

- https://developers.facebook.com/docs/meta-pixel/reference/

## Server route

For Meta Conversions API, load [Server](server.md). Map CAPI independently and reconcile Pixel/CAPI
overlap through the exact Meta occurrence-ID contract.
