package main

import (
	"encoding/json"
	"io"
)

// jsonDecode is a thin wrapper to keep import surface tidy across files.
func jsonDecode(r io.Reader, v interface{}) error {
	return json.NewDecoder(r).Decode(v)
}
