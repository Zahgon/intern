// Driver that replays a corpus of intern calls against the real Go package and
// prints one record per call: the resulting value and an identity group id.
//
// The identity group is what makes the two languages comparable. Go exposes
// interning through reflect.StringHeader.Data and Python through `is`; neither
// number means anything to the other, but "which earlier call returned this
// same instance" means the same thing in both.
package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"unsafe"

	"github.com/josharian/intern"
)

type op struct {
	Fn  string `json:"fn"`
	Arg string `json:"arg"`
}

type record struct {
	Value string `json:"value"`
	Group int    `json:"group"`
}

func data(s string) uintptr {
	return (*reflect.StringHeader)(unsafe.Pointer(&s)).Data
}

func main() {
	var ops []op
	if err := json.NewDecoder(os.Stdin).Decode(&ops); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	groups := map[[2]uintptr]int{}
	out := make([]record, 0, len(ops))

	for _, o := range ops {
		raw, err := hex.DecodeString(o.Arg)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}

		var got string
		switch o.Fn {
		case "string":
			got = intern.String(string(raw))
		case "bytes":
			got = intern.Bytes(raw)
		default:
			fmt.Fprintln(os.Stderr, "unknown fn "+o.Fn)
			os.Exit(1)
		}

		key := [2]uintptr{data(got), uintptr(len(got))}
		if len(got) == 0 {
			key = [2]uintptr{0, 0}
		}
		g, ok := groups[key]
		if !ok {
			g = len(groups)
			groups[key] = g
		}
		out = append(out, record{Value: hex.EncodeToString([]byte(got)), Group: g})
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	json.NewEncoder(w).Encode(out)
}
