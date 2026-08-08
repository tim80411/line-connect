"""Admin dashboard: a single POST endpoint with an action registry, plus the
static SPA ported from the upstream Dify plugin.

The whole package is only wired up when ADMIN_PASSWORD is set (main.py) — an
unset password means the routes do not exist at all, not that they 401.
"""
