# A list needs no trip; a leg links it

**A packing list stands on its own.** The list is the thing being used, and
creating a trip first is ceremony, so `packing_list` has no `trip_id` at all.
The same instinct as `food`'s ingredient stubs: the app must never demand
bookkeeping before it is useful.

**A list joins a trip only through a leg**: `trip_leg.packing_list_id`,
nullable, unique, `ON DELETE SET NULL`. A trip with several legs has to say
*which journey* a list is for, and only the leg knows — it is also the thing
with a departure, which is where a linked list takes its date from.

Rejected:

- **`packing_list.trip_id`**, which the first packing revision's docstring
  intended. It cannot say which of a trip's journeys the list belongs to.
- **A trip owning an outbound and a return list**, which fixes every trip to
  two legs and two lists.
- **Routing a round-trip pair through a trip**, which would make a trip
  mandatory in exactly the case where laziness is most likely.
