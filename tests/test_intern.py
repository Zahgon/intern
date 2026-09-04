"""Port of intern_test.go.

Go's build tag ``// +build !race`` excludes these under the race detector,
because ``sync.Pool`` degrades to a no-op there. CPython has no equivalent
mode, so the tag has no counterpart; see MIGRATION-REPORT.md, difference A5.
"""

import builtins
import gc
import unittest

import intern


class TestString(unittest.TestCase):
    def test_string(self):
        s = "abcde"
        sub = intern.string(s[1:4])
        interned = intern.string("bcd")
        # Go compares reflect.StringHeader.Data; the Python analogue is `is`.
        if sub is not interned:
            self.fail("failed to intern string")


class _CountingBytes(builtins.bytes):
    """A bytes that reports every conversion to str.

    ``bytes -> str`` is the allocating step that Go's ``AllocsPerRun`` is
    counting: Go's ``m[string(b)]`` is special-cased by the compiler so a lookup
    performs no conversion. Counting ``decode`` therefore measures the same
    thing, and unlike ``tracemalloc`` it sees allocations that are freed again
    before the next snapshot.
    """

    decodes = 0

    def decode(self, *args, **kwargs):
        _CountingBytes.decodes += 1
        return builtins.bytes.decode(self, *args, **kwargs)


class TestBytes(unittest.TestCase):
    def test_bytes(self):
        s = b"abc" * 100
        # Go slices for free, so its AllocsPerRun measures only Bytes(). Python
        # slicing allocates, so the caller-side slices are hoisted out of the
        # measured region to keep the assertion about intern.bytes() alone.
        chunks = [
            _CountingBytes(s[i * len(b"abc"):(i + 1) * len(b"abc")])
            for i in range(100)
        ]
        intern.bytes(chunks[0])

        _CountingBytes.decodes = 0
        gc.disable()
        try:
            for chunk in chunks:
                intern.bytes(chunk)
        finally:
            gc.enable()

        n = _CountingBytes.decodes
        if n > 0:
            self.fail("Bytes allocated %d, want 0" % n)

    def test_bytes_returns_one_instance(self):
        """The identity half of the zero-allocation claim."""
        s = b"abc" * 100
        results = [
            intern.bytes(s[i * 3:(i + 1) * 3])
            for i in range(100)
        ]
        first = results[0]
        for got in results:
            self.assertIs(got, first)


if __name__ == "__main__":
    unittest.main()
