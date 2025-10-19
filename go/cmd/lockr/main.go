package main

import (
	"github.com/lockr/go/internal/cli"
)

var (
	// Version information - set by build flags
	version = "dev"
	commit  = "unknown"
	date    = "unknown"
)

func main() {
	cli.SetVersion(version, commit, date)
	cli.Execute()
}
