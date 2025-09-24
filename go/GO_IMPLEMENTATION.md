# Go Implementation Plan

## Overview
Go implementation focuses on performance, single-binary distribution, and production-ready deployment. Leverages Go's strengths in concurrency, static compilation, and minimal runtime dependencies.

## Dependencies

### Core Dependencies
```go
// go.mod
module github.com/username/lockr

go 1.21

require (
    github.com/mutecomm/go-sqlcipher/v4 v4.4.2    // SQLCipher bindings
    github.com/spf13/cobra v1.7.0                 // CLI framework
    github.com/charmbracelet/bubbletea v0.24.2    // Interactive TUI
    github.com/charmbracelet/lipgloss v0.8.0      // Terminal styling
    github.com/atotto/clipboard v1.4.0            // Clipboard operations
    golang.org/x/crypto v0.12.0                   // Additional crypto utilities
    golang.org/x/term v0.11.0                     // Terminal utilities
)

require (
    github.com/stretchr/testify v1.8.4            // Testing framework
    github.com/golang/mock v1.6.0                 // Mocking framework
    github.com/go-delve/delve v1.21.0             // Debugging
)
```

## Project Structure

```
go/
├── go.mod
├── go.sum
├── Makefile
├── README.md
├── cmd/
│   └── lockr/
│       └── main.go                # Application entry point
├── internal/                      # Private application code
│   ├── cli/
│   │   ├── root.go               # Root command
│   │   ├── add.go                # Add command
│   │   ├── get.go                # Get command (interactive)
│   │   ├── list.go               # List command
│   │   ├── update.go             # Update command
│   │   ├── delete.go             # Delete command
│   │   └── info.go               # Info command
│   ├── database/
│   │   ├── manager.go            # Database operations
│   │   ├── schema.go             # Schema management
│   │   ├── migrations.go         # Database migrations
│   │   └── models.go             # Data models
│   ├── session/
│   │   ├── manager.go            # Session management
│   │   ├── auth.go               # Authentication
│   │   └── timeout.go            # Session timeout handling
│   ├── search/
│   │   ├── fuzzy.go              # Fuzzy matching algorithm
│   │   ├── interactive.go        # Interactive search UI
│   │   └── scorer.go             # Scoring algorithms
│   ├── clipboard/
│   │   ├── manager.go            # Clipboard operations
│   │   ├── autoclear.go          # Auto-clear functionality
│   │   └── platforms.go          # Platform-specific code
│   ├── config/
│   │   ├── config.go             # Configuration management
│   │   └── validation.go         # Input validation
│   └── errors/
│       └── errors.go             # Custom error types
├── pkg/                          # Public API (if needed)
├── tests/
│   ├── unit/
│   │   ├── database_test.go
│   │   ├── session_test.go
│   │   ├── fuzzy_test.go
│   │   └── validation_test.go
│   ├── integration/
│   │   ├── cli_test.go
│   │   ├── workflow_test.go
│   │   └── security_test.go
│   └── performance/
│       ├── benchmark_test.go
│       └── memory_test.go
├── scripts/
│   ├── build.sh                  # Build script
│   ├── test.sh                   # Test script
│   └── benchmark.sh              # Benchmarking script
└── docs/
    └── API.md                    # API documentation
```

## Implementation Details

### 1. Database Manager (`internal/database/manager.go`)

```go
package database

import (
    "database/sql"
    "time"
    _ "github.com/mutecomm/go-sqlcipher/v4"
)

type VaultDatabase struct {
    db   *sql.DB
    path string
}

type Secret struct {
    ID          int       `json:"id"`
    Key         string    `json:"key"`
    Value       string    `json:"value"`
    CreatedAt   time.Time `json:"created_at"`
    LastAccessed time.Time `json:"last_accessed"`
    AccessCount int       `json:"access_count"`
}

func NewVaultDatabase(path string) *VaultDatabase {
    return &VaultDatabase{path: path}
}

func (v *VaultDatabase) Connect(password string) error {
    db, err := sql.Open("sqlite3", v.path+"?_pragma_key="+password)
    if err != nil {
        return err
    }

    // Test connection
    if err := db.Ping(); err != nil {
        return err
    }

    v.db = db
    return v.initializeTables()
}

func (v *VaultDatabase) AddSecret(key, value string) error {
    query := `
        INSERT INTO secrets (key, value, created_at, last_accessed)
        VALUES (?, ?, datetime('now'), datetime('now'))
    `
    _, err := v.db.Exec(query, key, value)
    return err
}

func (v *VaultDatabase) GetSecret(key string) (*Secret, error) {
    query := `
        SELECT id, key, value, created_at, last_accessed, access_count
        FROM secrets WHERE key = ? COLLATE NOCASE
    `
    var secret Secret
    err := v.db.QueryRow(query, key).Scan(
        &secret.ID, &secret.Key, &secret.Value,
        &secret.CreatedAt, &secret.LastAccessed, &secret.AccessCount,
    )

    if err != nil {
        return nil, err
    }

    // Update last accessed
    go v.updateLastAccessed(secret.ID)

    return &secret, nil
}

func (v *VaultDatabase) SearchKeys(pattern string) ([]string, error) {
    query := `
        SELECT key FROM secrets
        WHERE key LIKE ? COLLATE NOCASE
        ORDER BY
            CASE WHEN key = ? THEN 0 ELSE 1 END,
            CASE WHEN key LIKE ? THEN 0 ELSE 1 END,
            length(key),
            key COLLATE NOCASE
    `

    likePattern := "%" + pattern + "%"
    prefixPattern := pattern + "%"

    rows, err := v.db.Query(query, likePattern, pattern, prefixPattern)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var keys []string
    for rows.Next() {
        var key string
        if err := rows.Scan(&key); err != nil {
            return nil, err
        }
        keys = append(keys, key)
    }

    return keys, nil
}
```

### 2. Fuzzy Search (`internal/search/fuzzy.go`)

```go
package search

import (
    "sort"
    "strings"
)

type Match struct {
    Key   string
    Score float64
}

type FuzzyMatcher struct {
    caseSensitive bool
}

func NewFuzzyMatcher() *FuzzyMatcher {
    return &FuzzyMatcher{caseSensitive: false}
}

func (f *FuzzyMatcher) Search(pattern string, candidates []string) []Match {
    if pattern == "" {
        matches := make([]Match, len(candidates))
        for i, candidate := range candidates {
            matches[i] = Match{Key: candidate, Score: 1.0}
        }
        return matches
    }

    var matches []Match
    pattern = strings.ToLower(pattern)

    for _, candidate := range candidates {
        score := f.calculateScore(pattern, candidate)
        if score > 0 {
            matches = append(matches, Match{
                Key:   candidate,
                Score: score,
            })
        }
    }

    // Sort by score (descending)
    sort.Slice(matches, func(i, j int) bool {
        return matches[i].Score > matches[j].Score
    })

    return matches
}

func (f *FuzzyMatcher) calculateScore(pattern, candidate string) float64 {
    candidateLower := strings.ToLower(candidate)

    // Exact match
    if pattern == candidateLower {
        return 1.0
    }

    // Substring match
    if strings.Contains(candidateLower, pattern) {
        return 0.8 + (0.2 * float64(len(pattern)) / float64(len(candidate)))
    }

    // Prefix match
    if strings.HasPrefix(candidateLower, pattern) {
        return 0.7 + (0.2 * float64(len(pattern)) / float64(len(candidate)))
    }

    // Character sequence matching
    return f.sequenceMatchScore(pattern, candidateLower)
}

func (f *FuzzyMatcher) sequenceMatchScore(pattern, candidate string) float64 {
    if len(pattern) == 0 {
        return 1.0
    }

    patternIdx := 0
    consecutiveMatches := 0
    maxConsecutive := 0

    for _, char := range candidate {
        if patternIdx < len(pattern) && rune(pattern[patternIdx]) == char {
            patternIdx++
            consecutiveMatches++
            if consecutiveMatches > maxConsecutive {
                maxConsecutive = consecutiveMatches
            }
        } else {
            consecutiveMatches = 0
        }
    }

    if patternIdx == len(pattern) {
        // All characters matched
        return float64(maxConsecutive) / float64(len(pattern)) * 0.6
    }

    return 0.0
}
```

### 3. Interactive Search (`internal/search/interactive.go`)

```go
package search

import (
    "fmt"
    "strings"

    "github.com/charmbracelet/bubbletea"
    "github.com/charmbracelet/lipgloss"
)

const maxDisplayResults = 5

type InteractiveModel struct {
    input       string
    matches     []Match
    selected    int
    width       int
    height      int
    allKeys     []string
    fuzzyMatcher *FuzzyMatcher
    quitting    bool
    cancelled   bool
    chosen      string
}

func NewInteractiveModel(keys []string) InteractiveModel {
    return InteractiveModel{
        allKeys:      keys,
        fuzzyMatcher: NewFuzzyMatcher(),
        matches:      []Match{},
    }
}

func (m InteractiveModel) Init() tea.Cmd {
    return nil
}

func (m InteractiveModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "ctrl+c", "esc":
            m.cancelled = true
            m.quitting = true
            return m, tea.Quit

        case "enter":
            if len(m.matches) > 0 && m.selected < len(m.matches) {
                m.chosen = m.matches[m.selected].Key
                m.quitting = true
                return m, tea.Quit
            }

        case "up":
            if m.selected > 0 {
                m.selected--
            }

        case "down":
            if m.selected < len(m.matches)-1 && m.selected < maxDisplayResults-1 {
                m.selected++
            }

        case "backspace":
            if len(m.input) > 0 {
                m.input = m.input[:len(m.input)-1]
                m.updateMatches()
                m.selected = 0
            }

        default:
            if len(msg.String()) == 1 {
                m.input += msg.String()
                m.updateMatches()
                m.selected = 0
            }
        }

    case tea.WindowSizeMsg:
        m.width = msg.Width
        m.height = msg.Height
    }

    return m, nil
}

func (m *InteractiveModel) updateMatches() {
    m.matches = m.fuzzyMatcher.Search(m.input, m.allKeys)
}

func (m InteractiveModel) View() string {
    if m.quitting {
        return ""
    }

    var b strings.Builder

    // Input line
    b.WriteString(fmt.Sprintf("Search: %s\n", m.input))
    b.WriteString(strings.Repeat("─", m.width) + "\n")

    // Results
    displayCount := len(m.matches)
    if displayCount > maxDisplayResults {
        displayCount = maxDisplayResults
    }

    if displayCount == 0 {
        b.WriteString("No matches found.\n")
    } else {
        for i := 0; i < displayCount; i++ {
            match := m.matches[i]
            style := lipgloss.NewStyle()

            if i == m.selected {
                style = style.Background(lipgloss.Color("240")).Foreground(lipgloss.Color("15"))
            }

            line := fmt.Sprintf("  %s", match.Key)
            b.WriteString(style.Render(line) + "\n")
        }

        // Show "more" indicator
        if len(m.matches) > maxDisplayResults {
            remaining := len(m.matches) - maxDisplayResults
            b.WriteString(fmt.Sprintf("  ...and %d more\n", remaining))
        }
    }

    b.WriteString("\n")
    b.WriteString("Use ↑/↓ to navigate, Enter to select, Esc to cancel")

    return b.String()
}

func RunInteractiveSearch(keys []string, initialPattern string) (string, bool, error) {
    model := NewInteractiveModel(keys)
    model.input = initialPattern
    model.updateMatches()

    program := tea.NewProgram(model, tea.WithAltScreen())
    finalModel, err := program.Run()
    if err != nil {
        return "", false, err
    }

    final := finalModel.(InteractiveModel)
    return final.chosen, !final.cancelled, nil
}
```

### 4. CLI Interface (`internal/cli/root.go`)

```go
package cli

import (
    "fmt"
    "os"

    "github.com/spf13/cobra"
)

var vaultFile string

var rootCmd = &cobra.Command{
    Use:   "lockr",
    Short: "Personal vault for secure storage of secrets",
    Long: `Lockr is a personal vault CLI application for secure storage and retrieval
of secrets with interactive fuzzy search capabilities.`,
}

func Execute() {
    if err := rootCmd.Execute(); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(1)
    }
}

func init() {
    rootCmd.PersistentFlags().StringVarP(&vaultFile, "vault-file", "f",
        "vault.lockr", "Path to vault file")

    rootCmd.AddCommand(addCmd)
    rootCmd.AddCommand(getCmd)
    rootCmd.AddCommand(listCmd)
    rootCmd.AddCommand(updateCmd)
    rootCmd.AddCommand(deleteCmd)
    rootCmd.AddCommand(infoCmd)
}
```

### 5. Clipboard Manager (`internal/clipboard/manager.go`)

```go
package clipboard

import (
    "context"
    "time"

    "github.com/atotto/clipboard"
)

type Manager struct {
    autoClearSeconds int
}

func NewManager(autoClearSeconds int) *Manager {
    return &Manager{
        autoClearSeconds: autoClearSeconds,
    }
}

func (m *Manager) CopyWithAutoClear(text string) error {
    if err := clipboard.WriteAll(text); err != nil {
        return err
    }

    // Start auto-clear timer
    go m.autoClear(text)

    return nil
}

func (m *Manager) autoClear(originalText string) {
    ctx, cancel := context.WithTimeout(context.Background(),
        time.Duration(m.autoClearSeconds)*time.Second)
    defer cancel()

    <-ctx.Done()

    // Check if clipboard still contains our text
    current, err := clipboard.ReadAll()
    if err == nil && current == originalText {
        clipboard.WriteAll("") // Clear clipboard
    }
}

func (m *Manager) Clear() error {
    return clipboard.WriteAll("")
}
```

## Build System

### Makefile
```makefile
.PHONY: build test lint clean install

BINARY_NAME=lockr
VERSION?=$(shell git describe --tags --always --dirty)
LDFLAGS=-ldflags "-X main.version=${VERSION}"

build:
	go build ${LDFLAGS} -o bin/${BINARY_NAME} cmd/lockr/main.go

build-all:
	GOOS=darwin GOARCH=amd64 go build ${LDFLAGS} -o bin/${BINARY_NAME}-darwin-amd64 cmd/lockr/main.go
	GOOS=darwin GOARCH=arm64 go build ${LDFLAGS} -o bin/${BINARY_NAME}-darwin-arm64 cmd/lockr/main.go
	GOOS=linux GOARCH=amd64 go build ${LDFLAGS} -o bin/${BINARY_NAME}-linux-amd64 cmd/lockr/main.go
	GOOS=windows GOARCH=amd64 go build ${LDFLAGS} -o bin/${BINARY_NAME}-windows-amd64.exe cmd/lockr/main.go

test:
	go test -v ./...

test-coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

lint:
	golangci-lint run

benchmark:
	go test -bench=. -benchmem ./tests/performance/

clean:
	rm -rf bin/
	rm -f coverage.out coverage.html

install: build
	cp bin/${BINARY_NAME} /usr/local/bin/

.DEFAULT_GOAL := build
```

## Performance Optimizations

### Concurrency
- Goroutines for clipboard auto-clear
- Concurrent database operations where safe
- Background session cleanup

### Memory Management
```go
// Secure memory clearing for sensitive data
func clearString(s *string) {
    if s == nil {
        return
    }

    // Convert to byte slice and clear
    bytes := []byte(*s)
    for i := range bytes {
        bytes[i] = 0
    }
    *s = ""
}

// Pool for frequently allocated objects
var matchPool = sync.Pool{
    New: func() interface{} {
        return make([]Match, 0, 100)
    },
}
```

### Database Optimizations
- Prepared statements for frequent queries
- Connection pooling
- Index optimization
- Batch operations where possible

## Testing Strategy

### Unit Tests
```go
func TestFuzzyMatcher_ExactMatch(t *testing.T) {
    matcher := NewFuzzyMatcher()
    candidates := []string{"password", "email", "api-key"}

    matches := matcher.Search("password", candidates)

    assert.Len(t, matches, 1)
    assert.Equal(t, "password", matches[0].Key)
    assert.Equal(t, 1.0, matches[0].Score)
}
```

### Benchmark Tests
```go
func BenchmarkFuzzySearch(b *testing.B) {
    keys := generateTestKeys(10000)
    matcher := NewFuzzyMatcher()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        matcher.Search("test", keys)
    }
}
```

## Security Features

### Memory Security
- Secure string clearing
- No string interning for secrets
- Minimal memory allocations
- Garbage collection optimization

### File Security
```go
func createSecureFile(path string) (*os.File, error) {
    return os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
}
```

## Distribution

### Release Binaries
- macOS (amd64, arm64)
- Linux (amd64, arm64)
- Windows (amd64)

### Package Managers
- Homebrew formula
- Go modules: `go install github.com/username/lockr/cmd/lockr@latest`
- GitHub releases with checksums

## Performance Targets

- **Startup Time**: < 50ms cold start
- **Database Operations**: < 5ms CRUD operations
- **Fuzzy Search**: < 50ms for 10,000 entries
- **Interactive Response**: < 25ms keystroke response
- **Memory Usage**: < 20MB for 10,000 entries
- **Binary Size**: < 10MB static binary