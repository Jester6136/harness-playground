"""Best-effort webhook to trigger downstream MongoDB sync.

After any write to the TTCP collection — `save_ttcp` / `update_ttcp` /
`delete_ttcp`, or a batch run that produced new docs — we POST to
`settings.ttcp_sync_url` so the user's other apps re-sync their own DB.

Hard rule: a sync-hook outage must NEVER break or block the write that
triggered it. So:
  - `notify_ttcp_sync()` (default) fires the POST in a daemon thread and
    returns immediately — for the agent's interactive write tools.
  - `notify_ttcp_sync(block=True)` does a blocking POST — for the offline
    batch, which is about to exit and would otherwise kill the daemon
    thread before the request completes.

Either way, all errors are logged and swallowed.
"""
from __future__ import annotations

import logging
import threading

import httpx

from harness import tenant
from harness.config import settings

log = logging.getLogger(__name__)


def notify_ttcp_sync(reason: str = "", *, block: bool = False) -> None:
    """POST to the TTCP sync endpoint so downstream apps re-sync.

    `reason` goes in the JSON body for the downstream service's logs
    (e.g. "save_ttcp", "delete_ttcp", "batch"). No-op if no URL configured.
    Never raises.
    """
    # Read in the calling thread/context (before any daemon thread spawn) so
    # the active tenant's webhook is used; "" in the account disables it.
    url = tenant.ttcp_sync_url()
    if not url:
        return

    def _post() -> None:
        try:
            httpx.post(url, json={"reason": reason}, timeout=settings.ttcp_sync_timeout)
            log.info("ttcp sync notified (%s)", reason)
        except Exception as exc:
            log.warning("ttcp sync notify failed (%s): %s", reason, exc)

    if block:
        _post()
    else:
        threading.Thread(target=_post, name="ttcp-sync-notify", daemon=True).start()
