# The SPA catch-all serves real files, with media's resolve-and-confine block

The catch-all resolves `dist / full_path` and serves it when it is a real file
inside the dist directory; otherwise it serves `index.html`. That is media's
block, adopted rather than redesigned, because media is where a convention is
looked up. Nothing sits in front of this app to serve static files instead:
cloudflared connects straight to uvicorn.

Rejected:

- **Special-casing the icon paths** — `/favicon.svg`, `/favicon.ico`,
  `/robots.txt` and whatever comes next. Shorter today, and a list somebody has
  to remember to extend, with the same silent failure each time a file is
  added to `frontend/public/`.
- **Mounting the whole dist as `StaticFiles` with `html=True`.** It would serve
  the files, but hand the client-route fallback to Starlette, and with it the
  `/api` 404 guard this app cannot give up.

**The `/api` guard is the only prefix guard.** This app's health path is
`/api/health`, so the `api` prefix already covers the deploy probe. `food`
carries a second, `health` guard because its health path is `/health`; copying
it here would guard nothing this app serves and would read as a rule rather
than as the consequence of a per-app path.

**The guard refuses `/api` explicitly rather than relying on registration
order.** Registering the API routers first is necessary but not sufficient:
the `path` converter matches any string it reaches, so ordering protects only
routes that exist, and a mistyped endpoint would come back as a 200 carrying
the bundle.

**`.resolve()`, `is_relative_to()` and `is_file()` are security, not
tidiness.** `full_path` is user-controlled; without the confinement,
`/..%2F.env` reads the app's credentials from beside the bundle.
