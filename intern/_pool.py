"""A ``sync.Pool`` analogue for the intern tables.

Go's ``sync.Pool`` has two externally observable properties that a plain module
level ``dict`` does not, both recorded from the real package rather than assumed:

* **Per-P storage.** Each processor gets its own map, so the same value can have
  several canonical instances at once. Measured: with ``GOMAXPROCS`` set to 1, 4
  and 10, the number of distinct canonical instances observed for one value was
  exactly 1, 4 and 10. The Python analogue is one table per *thread*, which also
  removes the need for a lock, exactly as it does in Go.

* **Erasure on garbage collection.** Measured: a single ``runtime.GC()`` is
  enough to lose every interned value; the table survives indefinitely while no
  collection happens. This is what the package doc means by "Interned strings
  may be removed automatically at any time without notification".

Go's collector is not generational, so its closest CPython counterpart is a full
(generation 2) collection, not the frequent gen-0 sweeps.

Erasure is applied lazily: the epoch is bumped from the GC callback and each
thread notices on its next call. That mirrors ``sync.Pool`` dropping the map and
calling ``New`` again on the following ``Get``, and it keeps the callback from
touching another thread's tables while that thread is running.
"""

import gc
import threading

_FULL_COLLECTION = 2


class Pool:
    """Per-thread intern tables that are dropped when a full GC runs."""

    def __init__(self, register=True):
        self._local = threading.local()
        self._epoch = 0
        if register:
            gc.callbacks.append(self._on_gc)

    def _on_gc(self, phase, info):
        if phase == "stop" and info.get("generation") == _FULL_COLLECTION:
            self._epoch += 1

    def tables(self):
        """Return this thread's ``(canonical, by_bytes)`` tables.

        ``canonical`` maps a value to the instance every caller should receive.
        ``by_bytes`` memoises the ``bytes`` -> canonical ``str`` step so that a
        repeated :func:`intern.bytes` call allocates nothing, which is the
        property ``TestBytes`` pins in the Go suite.
        """
        local = self._local
        epoch = self._epoch
        if getattr(local, "epoch", None) != epoch:
            local.epoch = epoch
            local.canonical = {}
            local.by_bytes = {}
        return local.canonical, local.by_bytes

    def drop(self):
        """Discard every table, as a garbage collection would."""
        self._epoch += 1
