"""Token buffer + flush policy for edit-in-place streaming.

Channel-agnostic: caller pushes tokens, asks `should_flush(now)` to decide
when to commit a visible update, then `take()` to drain the buffer.

Flush rule (mirrors Hermes-Agent's `stream_consumer.py`):
  - `time_since_last_flush >= interval` AND `len(buffer) >= threshold`, OR
  - `len(buffer) >= force_size`  — overrides the time gate so we never hold
                                   pathologically long bursts.
"""
from __future__ import annotations


class StreamBuffer:
    def __init__(
        self,
        *,
        interval: float = 1.0,
        threshold: int = 40,
        force_size: int = 1500,
    ) -> None:
        self.interval = interval
        self.threshold = threshold
        self.force_size = force_size
        self._buf: list[str] = []
        self._buf_len = 0
        self._last_flush: float = 0.0

    def push(self, text: str) -> None:
        if not text:
            return
        self._buf.append(text)
        self._buf_len += len(text)

    def should_flush(self, now: float) -> bool:
        if self._buf_len == 0:
            return False
        if self._buf_len >= self.force_size:
            return True
        return (now - self._last_flush) >= self.interval and self._buf_len >= self.threshold

    def take(self, now: float) -> str:
        out = "".join(self._buf)
        self._buf.clear()
        self._buf_len = 0
        self._last_flush = now
        return out

    @property
    def pending(self) -> int:
        return self._buf_len

    def mark_flushed(self, now: float) -> None:
        """Reset the time gate without draining (used after a manual edit)."""
        self._last_flush = now

    def widen_interval(self, factor: float, cap: float) -> None:
        """Adaptive backoff after a rate-limit hit."""
        self.interval = min(self.interval * factor, cap)
