# 已準備完成 is its own flag, gated by readiness, and cleared by the write that breaks it

**`done` is a boolean of its own, not "usage is 過去使用".** The two answer
different questions. `usage: past` is a shelf move with a side effect — it
enters the trip into 自動保存, whose oldest slot it can drop — and it is set
when the trip is over. `done` is the owner marking a trip ready to go, which
happens before it is over. Tying the two would let marking a trip delete
another one, and would leave a template or a saved trip, which has no usage,
unable to be marked. So `done` moves no shelf and touches no queue. A copy
starts not done, because whether the source was ready is state, not
definition.

**The mark stays, but only a ready trip can carry it.** A mark that says
"ready" while a ticket is unpaid is a lie the dashboard would repeat. Computing
the badge from readiness and dropping the column was the other way to keep it
honest, and was rejected: ready is necessary but not sufficient — everything
ticked is not the same as the owner having looked the trip over. So the server
refuses `done: true` on a trip that is not ready.

**A write that makes a done trip not ready clears `done`**, in the same
transaction (`settle_done` in `app/services/domain/trip.py`). Rejected:
refusing the write that would break readiness. That would make unticking a
label on a done trip impossible without first unmarking it, which is
backwards — unticking is how the owner says something came undone.

Reads carry `ready`, computed by the same function as the refusal, so the
screen's disabled control and the server cannot disagree. The rules are in
`business-rules.md`, "Readiness".
