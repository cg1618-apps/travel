# Decisions

Why travel is the way it is. Unlike the rest of `docs/`, this page is allowed to
talk about the past: it records what was chosen, what was rejected, and the
reasoning that is still load-bearing.

## Platform decisions this app inherits

Recorded in `cg1618-apps/platform` rather than here, and summarised only so far
as they bind this app:

- **It is its own repository**, sharing no code with the other applications. The
  platform connects them by configuration, not by git pointers.
- **It shares one PostgreSQL**, with its own database and its own role.
- **It is `public`**, because repository rulesets and environments with required
  reviewers are free only for public repositories, and both gates depend on it.
- **No `pull_request`-triggered job may run on the self-hosted runner.**

## Decisions for this application

- **FastAPI, PostgreSQL, React + Vite, Alembic** — the media tracker's stack.
  Rejected: Django and a server-rendered frontend, for the same reasons
  recorded across the other apps; the deciding factor was consistency with an
  app that already works.
- **Cloudflare Access over the whole hostname, and no auth code in the app.**
  One user, no accounts. Rejected: an app-level single-user password with a JWT
  cookie, copying the media tracker — roughly 150 lines of security-sensitive
  code, written to duplicate a gate that already exists. Its one real advantage
  is failing closed: Access failing open, if a policy is deleted, exposes
  everything. That risk is accepted for now and is the reason the flip to
  `public` is treated as a deliberate, tested event rather than a config edit.
- **Sharing is anticipated, not built.** `/s/...` as the prefix for anything
  shareable, a `visibility` field from the first migration, and share tokens
  rather than accounts. All three are nearly free now and expensive to
  retrofit; none of them is implemented until sharing is actually wanted.
