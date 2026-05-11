"""Channel adapters — talk to the harness agent over its FastAPI/SSE API.

Each subpackage is a standalone bot process. Adapters share an SSE client and
thread mapping helpers in `channels._common`. Run a bot with e.g.:

    python -m channels.telegram.bot

Adapters never import from `harness.*` — they only know the HTTP contract,
which keeps deployments decoupled.
"""
