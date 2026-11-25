# A round trip is two ordinary lists sharing a `pair_id`

The outbound and return lists are two ordinary lists that know about each
other. Pairing is navigational: it lets the two be viewed together and says
nothing more. There is deliberately **no logic across the pair** — nothing
infers that something carried out must come back, because the return genuinely
differs, and a system that assumes otherwise generates noise.

Rejected: **one list with two check-off states**, which models the two
journeys as identical when they are not.

**A shared `pair_id`, not a `paired_list_id` self-pointer.** It was designed as
a self-reference and built as a shared key. A pointer holds two copies of one
fact and can desync — A points at B while B points at C, and nothing complains.
And 自動保存 counts a pair as one slot, which is a distinct-count against a
shared key but an awkward self-join against a pointer.

**A pair is one 自動保存 slot** because the pair is how a trip is actually
thought about; charging it two would punish the round trip for being modelled
honestly. The slot rules are in `business-rules.md`.
