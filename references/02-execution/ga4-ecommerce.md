# GA4 native ecommerce

## Contents

- Use native GA4 ecommerce mechanics

## Use native GA4 ecommerce mechanics

For an approved GA4 ecommerce event, inspect the current GA4 Event tag's native ecommerce controls
before creating variables or transformations. Prefer the native `Send Ecommerce data` route when
the saved tag surface supports it:

| Source contract | Configuration |
| --- | --- |
| Event push contains the current GA4-shaped `ecommerce` object | Select the native Data Layer source and map only approved event-level fields that are not supplied through that object. |
| Approved object exists at another exact source path or needs an approved reusable projection | Select the native Custom Object source and reference that object variable. |
| Source is not GA4-shaped | Use the narrowest approved Custom Object transformation that returns the complete GA4 ecommerce object, or explicit manual fields only when the native route cannot represent the approved contract; do not add a Boolean payload-eligibility helper. |

Select exactly one route per GA4 event. Do not enable native ecommerce and also map `items`
manually. Do not put `items`, transaction-specific ecommerce values, or event-specific commerce
objects in a broadly shared Event Settings variable. Never flatten an item array into scalar
`items.0.*` fields. A manual route is an explicit exception with current template evidence, not a
parallel safety net.

Preserve zero, false, one item, and every approved item. An empty or absent runtime object is a
site/dataLayer or recette dependency, not permission for this skill to invent `CJS - Ecommerce -
Eligible`, filter items, or suppress the tag. A design-time missing required mapping still blocks
configuration.

When persistent ecommerce state could leak into a later event, record that risk and the required
site/dataLayer clearing contract (commonly an `ecommerce: null` push before the next ecommerce
object). This skill does not insert a browser-side clearing script to compensate for application
state. Configure only the approved ecommerce events; an official funnel catalogue is not
authorization to add the rest of the funnel.
