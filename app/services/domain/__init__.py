"""Business rules. Routers call these; they do not reimplement them.

The split follows the media tracker: a router owns request and response
wiring, dependency injection, status-code mapping and the order in which
things happen. The rule itself - what counts toward a cap, what a copy
carries - lives here, where it can be tested without an HTTP client and
cannot be quietly reimplemented differently by a second endpoint.
"""
