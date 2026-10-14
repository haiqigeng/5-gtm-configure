# GA4 native ecommerce

## Use native GA4 ecommerce mechanics

Each approved ecommerce event has one complete commerce representation. Inspect the GA4 Event
native controls and select its source:

| Source contract | Configuration |
| --- | --- |
| Compatible GA4-shaped `ecommerce` in the event push | Native Data Layer source; additional approved event fields cover values outside that object. |
| Complete compatible object at another approved path | Native Custom Object referencing that variable. |
| Approved source needs shape conversion | Narrow Custom Object projection returning the complete object. |
| Native route cannot represent the approved contract | Explicit manual fields supported by current template evidence. |

The selected representation owns transaction values and the complete item array for that event.
Apply [mapping](../data/mapping.md) and [transformation vectors](../data/transformations.md) for
cardinality, meaningful zero/false values, missing runtime data and approved field conversions.

The site owns freshness and clearing of persistent ecommerce state, commonly through
`ecommerce: null` before the next object. Record that source-contract dependency when applicable.
Approved business requirements determine the implemented event set.
