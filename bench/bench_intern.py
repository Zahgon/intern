"""Port of BenchmarkString / BenchmarkBytes from intern_test.go.

Go's ``b.RunParallel`` spreads the loop across GOMAXPROCS goroutines; the
analogue is a thread per core. Under CPython the GIL serialises the work, so the
parallel numbers measure contention rather than throughput -- which is the point,
since the port's tables are per-thread exactly as Go's are per-P.

Benchmarks are not part of the test gate, matching ``go test`` (which does not
run benchmarks unless asked).
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import intern  # noqa: E402

N = 2_000_000


def _run_parallel(body, workers):
    per_worker = N // workers
    threads = [threading.Thread(target=body, args=(per_worker,)) for _ in range(workers)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - start


def benchmark_string(workers):
    value = "hello brad"[1:5]

    def body(n):
        s = None
        for _ in range(n):
            s = intern.string(value)
        return s

    return _run_parallel(body, workers), len("hello brad")


def benchmark_bytes(workers):
    value = b"hello brad"[1:5]

    def body(n):
        s = None
        for _ in range(n):
            s = intern.bytes(value)
        return s

    return _run_parallel(body, workers), len(b"hello brad")


def main():
    workers = int(os.environ.get("BENCH_WORKERS", os.cpu_count() or 1))
    print("workers=%d  iterations=%d" % (workers, N))
    for name, fn in (("BenchmarkString", benchmark_string), ("BenchmarkBytes", benchmark_bytes)):
        elapsed, nbytes = fn(workers)
        ns_per_op = elapsed * 1e9 / N
        mb_per_s = (nbytes * N) / elapsed / 1e6
        print("%-16s %10.2f ns/op  %8.2f MB/s" % (name, ns_per_op, mb_per_s))


if __name__ == "__main__":
    main()
