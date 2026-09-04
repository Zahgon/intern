"""Phase 11 differential harness: real Go package vs. the Python port.

Both drivers replay the same call sequence and emit, per call, the resulting
value plus an *identity group* — the index of the first call that returned this
same instance. Values must match exactly; identity groups must match exactly.

Determinism requirements, both taken from recorded Go behaviour:

* ``GOMAXPROCS=1`` / a single Python thread — interning is per-P in Go and
  per-thread in the port, so more than one worker makes the grouping legitimately
  non-deterministic (probe G2).
* ``GOGC=off`` / ``gc.disable()`` — one collection erases the table in both
  (probe F2), so a collection landing mid-sequence would shift every later group.
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER_DIR = os.path.join(HERE, "go_driver")
STAGED_SRC = os.path.join(DRIVER_DIR, "_src")
GO_DRIVER = os.environ.get("GO_DRIVER", os.path.join(DRIVER_DIR, "godriver"))
PY_DRIVER = os.path.join(HERE, "py_driver.py")

UPSTREAM = "https://github.com/josharian/intern"
DEFAULT_GO_SOURCE = os.path.normpath(
    os.path.join(HERE, "..", "..", "scraped_repos", "Go", "josharian_intern")
)


def ensure_go_driver(go_source):
    """Stage the Go package next to the driver and build it.

    The package is staged rather than referenced in place because a Go
    ``replace`` directive cannot name a path containing a space, and this
    checkout may well live under one. A *relative* replace sidesteps that: the
    path in go.mod stays space-free and Go resolves it against the module
    directory itself.
    """
    if os.path.exists(GO_DRIVER):
        return

    if not os.path.isdir(go_source):
        if shutil.which("git") is None:
            raise SystemExit(
                "no Go source at %s and git is unavailable" % go_source
            )
        print("staging %s from %s" % (os.path.basename(STAGED_SRC), UPSTREAM))
        if os.path.isdir(STAGED_SRC):
            shutil.rmtree(STAGED_SRC)
        subprocess.run(
            ["git", "clone", "--depth", "1", UPSTREAM, STAGED_SRC], check=True
        )
    else:
        if os.path.isdir(STAGED_SRC):
            shutil.rmtree(STAGED_SRC)
        shutil.copytree(go_source, STAGED_SRC, ignore=shutil.ignore_patterns(".git"))

    if shutil.which("go") is None:
        raise SystemExit("the Go toolchain is required to build the reference driver")

    subprocess.run(
        ["go", "build", "-o", os.path.basename(GO_DRIVER), "."],
        cwd=DRIVER_DIR,
        check=True,
    )

SEEDS = [
    b"",
    b"a",
    b"abc",
    b"bcd",
    b"abcde",
    b"hello brad",
    b"hello",
    b"\x00",
    b"A\x00B",
    b"\xff",
    b"\xfe",
    b"\xff\xfe\x41",
    b"\x80",
    b"\xef\xbf\xbd",
    "日本語".encode(),
    "😀".encode(),
    "café".encode(),
    b"\xc3",
    b"\xc3\xa9",
    b"x" * 300,
    b"__proto__",
    b"constructor",
    b"0",
    b"007",
]


def build_corpus(n, seed):
    rng = random.Random(seed)
    ops = []
    for value in SEEDS:
        ops.append({"fn": "string", "arg": value.hex()})
        ops.append({"fn": "bytes", "arg": value.hex()})
    for _ in range(n):
        value = rng.choice(SEEDS)
        if rng.random() < 0.3:
            value = builtins_bytes(rng.randrange(256) for _ in range(rng.randrange(0, 6)))
        ops.append(
            {"fn": rng.choice(["string", "bytes"]), "arg": value.hex()}
        )
    return ops


def builtins_bytes(iterable):
    return bytes(bytearray(iterable))


def run(cmd, payload, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "driver failed: %s\n%s" % (" ".join(cmd), proc.stderr.decode())
        )
    return json.loads(proc.stdout.decode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=2000)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument(
        "--go-source",
        default=os.environ.get("INTERN_GO_SOURCE", DEFAULT_GO_SOURCE),
        help="checkout of github.com/josharian/intern to diff against",
    )
    args = parser.parse_args()

    ensure_go_driver(args.go_source)

    total = 0
    diffs = 0
    for round_index in range(args.rounds):
        ops = build_corpus(args.cases, seed=round_index)
        go = run([GO_DRIVER], ops, env={"GOMAXPROCS": "1", "GOGC": "off"})
        py = run([sys.executable, PY_DRIVER], ops, env={"PYTHONHASHSEED": "0"})

        if len(go) != len(py):
            raise SystemExit("length mismatch: go=%d py=%d" % (len(go), len(py)))

        for i, (g, p) in enumerate(zip(go, py)):
            total += 1
            if g["value"] != p["value"]:
                diffs += 1
                print(
                    "VALUE  round=%d op=%d arg=%s go=%s py=%s"
                    % (round_index, i, ops[i]["arg"], g["value"], p["value"])
                )
            elif g["group"] != p["group"]:
                diffs += 1
                print(
                    "IDENT  round=%d op=%d arg=%s fn=%s go_group=%d py_group=%d"
                    % (
                        round_index,
                        i,
                        ops[i]["arg"],
                        ops[i]["fn"],
                        g["group"],
                        p["group"],
                    )
                )

    print("\ndifferential: %d cases, %d divergences" % (total, diffs))
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
