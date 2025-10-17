package main

import (
	"github.com/lockr/go/internal/cli"
)

var (
	// Version information - set by build flags
	Version   = "dev"
	BuildTime = "unknown"
	GitCommit = "unknown"
)

func main() {
	cli.Execute()
}
