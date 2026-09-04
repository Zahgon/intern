Package intern interns strings. This is a Python port of
[`josharian/intern`](https://github.com/josharian/intern).

Interning is best effort only. Interned strings may be removed automatically at
any time without notification. All functions may be called concurrently with
themselves and each other.

For a blog post introducing string interning, see:
https://commaok.xyz/post/intern-strings/

## Usage

```python
import intern

s = intern.string("hello")        # -> str
t = intern.bytes(b"hello")        # -> str
assert s is t                     # interning is observable as object identity
```

## API map

| Go | Python |
|---|---|
| `intern.String(s string) string` | `intern.string(s: str) -> str` |
| `intern.Bytes(b []byte) string` | `intern.bytes(b: bytes) -> str` |

`intern.bytes` shadows the builtin inside the module's namespace only;
`intern.bytes(...)` at a call site is unambiguous.

## Behaviour

Interning is observable through object identity: two equal values handed to
`intern.string` come back as the same object, which is what Go's test checks via
`reflect.StringHeader.Data`.

Three properties are inherited from Go's `sync.Pool` and were measured against
the Go package, not assumed:

- **Per-thread tables.** Go interns per-P; two threads can hold different
  canonical instances of the same value. This is why interning is "best effort".
- **Erased by a full garbage collection.** A single `gc.collect()` drops every
  interned value, matching a single `runtime.GC()` in Go.
- **No size cap.** The table grows until a collection clears it.

A Go `string` is an immutable byte sequence, which CPython splits into `str` and
`bytes`. `intern.bytes` decodes with `surrogateescape`, so every distinct byte
string maps to a distinct interned value and `.encode("utf-8", "surrogateescape")`
recovers the input exactly, including invalid UTF-8.

## Development

```sh
python -m unittest discover -s tests -t . -v   # tests
python bench/bench_intern.py                   # benchmarks
python verification/differential.py            # equivalence vs. the Go package
```

License: MIT
