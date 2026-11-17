"""PROTOTYPE (path B): a single-process, in-memory playable Texas hold'em table.

Not the product architecture: no real authentication, no database, no idempotency, no
reconnect replay, no timeouts. It exists to try the engine with real players. The Phase 5
work (SECURITY.md) replaces it; do not expose it to the public internet.
"""
