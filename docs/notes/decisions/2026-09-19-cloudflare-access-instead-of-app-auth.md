# Cloudflare Access gates the app; there is no auth code in it

travel has one user and no accounts. Cloudflare Access covers the whole
hostname (`exposure: cloudflare-access` in the platform's `apps.yml`), and the
app contains no login, session or password.

Rejected: an app-level single-user password with a JWT cookie, copying the
media tracker. That is roughly 150 lines of security-sensitive code written to
duplicate a gate that already exists. Its one real advantage is failing
closed: if the Access policy is deleted, Access fails open and exposes
everything. That risk is accepted, and it is why a move to `public` is treated
as a deliberate, tested event rather than a configuration edit.

## Sharing is anticipated, not built

A single trip is the natural unit to share — a packing list sent without dates
or a destination is little use to anyone — and that is the argument for trips
existing at all, though they are optional. Three things are carried now
because they are nearly free today and expensive to retrofit:

- anything shareable lives under `/s/...`, so opening it is an Access policy
  exempting that prefix rather than a redesign;
- shareable tables carry `visibility` from their first migration, all
  `private`, read by nothing yet;
- a password on a shared thing will be a share token on the object, never a
  second identity or a users table.

None of the sharing itself is built until it is wanted. If sharing ever needs
an unguessable identifier, it belongs on the share token, not on every row.
