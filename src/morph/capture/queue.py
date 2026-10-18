"""Thread-safe bounded frame queue for camera capture and worker ingestion."""

from __future__ import annotations

import collections
import threading
from typing import Generic, TypeVar

T = TypeVar("T")


class BoundedFrameQueue(Generic[T]):
    """Thread-safe bounded queue that drops oldest items when capacity is reached."""

    def __init__(self, max_size: int = 2):
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self.max_size = max_size
        self._deque: collections.deque[T] = collections.deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._dropped_frames: int = 0

    def push(self, item: T) -> bool:
        """Push an item onto queue.

        If full, drops the oldest item and increments dropped_frames.
        Returns True if item was added without dropping, False if an older item was dropped.
        """
        with self._lock:
            dropped = False
            if len(self._deque) >= self.max_size:
                self._dropped_frames += 1
                dropped = True
            self._deque.append(item)
            self._not_empty.notify()
            return not dropped

    def pop(self, timeout_sec: float | None = None) -> T | None:
        """Pop the oldest item from the queue, blocking up to timeout_sec."""
        with self._lock:
            if not self._deque:
                if timeout_sec is not None and timeout_sec > 0:
                    self._not_empty.wait(timeout_sec)
                else:
                    return None
            if self._deque:
                return self._deque.popleft()
            return None

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped_frames

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._deque)

    def clear(self) -> None:
        with self._lock:
            self._deque.clear()
