# Decisions

One file per decision: `YYYY-MM-DD-<topic>.md`, dated the day it was made.
Each holds a `# Title`, the reasoning, and the alternatives that were rejected,
so nobody proposes them again unaware.

- **A decision file holds the *why*, not the *what*.** Present-tense
  behaviour, rules and schema are on the matching page in `docs/`
  (`business-rules.md`, `data-model.md`, `api.md`, …). Only reasoning that
  still binds lives here.
- **There is no index.** The date-prefixed file names are the index. A list
  here would be a file every pull request appends to, which is the merge
  conflict this layout exists to avoid.
- **Delete a decision when it stops binding** — when the code it is about is
  gone, or a later decision reverses it. A reversal is a new file, and the
  file it overturns is deleted in the same commit. Git keeps the history.
- A deliberate divergence from `media`, the platform's reference app, is
  recorded here with its reason, so a later reader can tell a decision from an
  accident.

The convention is the platform's: `CLAUDE.md`, "Decisions are one file each".
