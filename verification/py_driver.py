"""Python side of the differential harness. Mirrors verification/go_driver."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import intern  # noqa: E402


def main():
    ops = json.load(sys.stdin)

    groups = {}
    out = []

    for op in ops:
        raw = bytes.fromhex(op["arg"])

        if op["fn"] == "string":
            got = intern.string(raw.decode("utf-8", "surrogateescape"))
        elif op["fn"] == "bytes":
            got = intern.bytes(raw)
        else:
            print("unknown fn " + op["fn"], file=sys.stderr)
            raise SystemExit(1)

        # Go groups by (data pointer, length) and collapses every empty string
        # onto one group, because an empty Go string has no meaningful pointer.
        key = 0 if not got else id(got)
        if key not in groups:
            groups[key] = len(groups)

        out.append(
            {
                "value": got.encode("utf-8", "surrogateescape").hex(),
                "group": groups[key],
            }
        )

    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
