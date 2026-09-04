"""Pins the ``sync.Pool`` semantics recorded from the Go package.

Every expectation here is a probe result, not a design preference. The probe
transcript is reproduced in MIGRATION-REPORT.md, section "Phase 2".
"""

import gc
import threading
import unittest

import intern
from intern._pool import Pool


class TestCanonicalisation(unittest.TestCase):
    def test_first_seen_instance_wins(self):
        """Probe A: the canonical instance is the first one handed in."""
        a = "".join(["hel", "lo1"])
        b = "".join(["hel", "lo1"])
        self.assertIsNot(a, b)

        first = intern.string(a)
        second = intern.string(b)

        self.assertIs(first, a)
        self.assertIs(second, a)
        self.assertIsNot(second, b)

    def test_string_and_bytes_share_one_table(self):
        """Probe B: Bytes hits the entry String created, and vice versa."""
        s = "".join(["sha", "red1"])
        from_string = intern.string(s)
        from_bytes = intern.bytes(b"shared1")
        self.assertIs(from_string, from_bytes)

        t = "".join(["sha", "red2"])
        first_from_bytes = intern.bytes(t.encode())
        self.assertIs(intern.string(t), first_from_bytes)

    def test_value_is_always_preserved(self):
        """Probe H: interning never changes the value."""
        for s in ["", "a", "日本語", "hello brad", "a" * 1000]:
            self.assertEqual(intern.string(s), s)

    def test_empty_inputs_agree(self):
        """Probe D: String(""), Bytes(nil) and Bytes([]byte{}) all agree."""
        self.assertEqual(intern.string(""), "")
        self.assertEqual(intern.bytes(b""), "")
        self.assertIs(intern.string(""), intern.bytes(b""))


class TestByteSemantics(unittest.TestCase):
    def test_arbitrary_bytes_round_trip(self):
        """Probe E: a Go string is arbitrary bytes, including invalid UTF-8."""
        for raw in [b"\xff\xfe\x41", b"A\x00B", b"\x80", bytes(range(256))]:
            got = intern.bytes(raw)
            self.assertEqual(got.encode("utf-8", "surrogateescape"), raw)

    def test_distinct_bytes_stay_distinct(self):
        """Invalid bytes must not collapse onto one replacement character."""
        self.assertNotEqual(intern.bytes(b"\xff"), intern.bytes(b"\xfe"))
        self.assertNotEqual(intern.bytes(b"\xff"), intern.bytes(b"\xef\xbf\xbd"))

    def test_bytes_matches_utf8_text(self):
        self.assertIs(intern.bytes("日本語".encode()), intern.string("日本語"))


class TestGarbageCollection(unittest.TestCase):
    def test_a_full_collection_drops_the_table(self):
        """Probe F2: one GC is enough to lose every interned value."""
        key = "".join(["gc", "key", "A"])
        first = intern.string(key)
        self.assertIs(intern.string("".join(["gc", "key", "A"])), first)

        gc.collect()

        again = intern.string("".join(["gc", "key", "A"]))
        self.assertIsNot(again, first)
        self.assertEqual(again, first)

    def test_stable_while_no_collection_happens(self):
        """Probe F3: without a collection the table is stable."""
        gc.disable()
        try:
            key = "".join(["no", "gc1"])
            first = intern.string(key)
            for _ in range(10000):
                self.assertIs(intern.string("".join(["no", "gc1"])), first)
        finally:
            gc.enable()

    def test_drop_is_equivalent_to_a_collection(self):
        pool = Pool(register=False)
        canonical, by_bytes = pool.tables()
        canonical["k"] = "k"
        by_bytes[b"k"] = "k"

        pool.drop()

        canonical, by_bytes = pool.tables()
        self.assertEqual(canonical, {})
        self.assertEqual(by_bytes, {})


class TestConcurrency(unittest.TestCase):
    def test_tables_are_per_thread(self):
        """Probe G2: distinct canonical instances scale with the worker count."""
        gc.disable()
        try:
            value = "".join(["con", "tended"])
            main = intern.string(value)

            seen = []
            lock = threading.Lock()

            def worker():
                got = intern.string("".join(["con", "tended"]))
                with lock:
                    seen.append(got)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(seen), 4)
            for got in seen:
                self.assertEqual(got, main)
                self.assertIsNot(got, main)
        finally:
            gc.enable()

    def test_concurrent_calls_are_safe_and_correct(self):
        errors = []

        def worker(n):
            try:
                for i in range(2000):
                    key = "k%d" % (i % 50)
                    assert intern.string(key) == key
                    assert intern.bytes(key.encode()) == key
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
