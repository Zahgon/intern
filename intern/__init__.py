"""Package intern interns strings.

Interning is best effort only.
Interned strings may be removed automatically
at any time without notification.
All functions may be called concurrently
with themselves and each other.

This is a port of https://github.com/josharian/intern. The Go API maps as:

===================  ==================
Go                   Python
===================  ==================
``intern.String``    :func:`string`
``intern.Bytes``     :func:`bytes`
===================  ==================

Interning is observable through object identity: two equal values passed to
:func:`string` come back as the *same* object, so ``a is b`` holds where Go's
test compares ``reflect.StringHeader.Data``.

A Go ``string`` is an immutable byte sequence, which CPython splits across two
types. :func:`bytes` therefore decodes with ``surrogateescape``, the only codec
that is both total and lossless over arbitrary bytes, so every distinct byte
string still maps to a distinct interned value and ``.encode`` recovers the
input exactly.
"""

from ._pool import Pool

__all__ = ["string", "bytes"]

_pool = Pool()


def string(s):
    """Return *s*, interned."""
    canonical, _ = _pool.tables()
    c = canonical.get(s)
    if c is not None:
        return c
    canonical[s] = s
    return s


def bytes(b):
    """Return *b* converted to a string, interned."""
    canonical, by_bytes = _pool.tables()
    c = by_bytes.get(b)
    if c is not None:
        return c
    s = b.decode("utf-8", "surrogateescape")
    c = canonical.get(s)
    if c is None:
        canonical[s] = s
        c = s
    by_bytes[b] = c
    return c
