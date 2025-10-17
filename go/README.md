# Lockr - Go Implementation

High-performance personal vault CLI application for secure storage and retrieval of secrets with interactive fuzzy search capabilities.

## Features

- **SQLCipher Encryption**: AES-256 encrypted storage for maximum security
- **Interactive Fuzzy Search**: FZF-like interface with real-time filtering
- **Session Management**: 15-minute authentication timeout with auto-renewal
- **Keyring Integration**: Store vault password in system keyring for automatic authentication
- **Clipboard Integration**: Auto-copy with 60-second auto-clear (macOS)
- **Cross-platform**: macOS, Linux, Windows support
- **Single Binary**: No dependencies, just download and run

## Installation

### Build from Source

```bash
cd go/
make build
./bin/lockr --help
```

### Binary Release

Download the latest release from the releases page.

## Quick Start

### Initialize a New Vault

```bash
lockr init
```

You'll be prompted to create a master password. This password encrypts your vault.

### Store a Secret

```bash
# Interactive prompt
lockr set github-token

# Auto-generate a random secret
lockr set -g api-key

# Generate with specific length
lockr set -g -l 32 database-password
```

### Retrieve a Secret

```bash
# Interactive fuzzy search
lockr get

# Direct retrieval
lockr get github-token
```

The secret is automatically copied to your clipboard (macOS) and cleared after 60 seconds.

### List All Secrets

```bash
# List all keys
lockr list

# Search for specific keys
lockr list api
```

### Delete a Secret

```bash
# With confirmation
lockr delete github-token

# Force delete
lockr delete -f github-token
```

## Keyring Integration

Lockr can store your vault password in your system keyring for automatic authentication.

### Quick Setup

```bash
# Save password to keyring
lockr keyring set

# Check status
lockr keyring status

# Remove from keyring
lockr keyring clear
```

### Supported Platforms

- **macOS**: Keychain
- **Linux**: Secret Service (GNOME Keyring, KWallet)
- **Windows**: Credential Manager

See [docs/KEYRING.md](docs/KEYRING.md) for detailed documentation.

## Usage

### Commands

```
Secret Operations:
  delete      Delete a secret from the vault
  get         Retrieve and copy a secret to clipboard
  set         Store or update a secret

Management Commands:
  init        Initialize a new vault
  keyring     Manage keyring integration
  list        List all keys or search with a pattern
  status      Show session and vault status
  version     Show version information
```

### Global Flags

- `--vault, -v`: Path to vault database (default: `~/.lockr/vault.lockr`)
- `--config, -c`: Path to config file (default: `~/.lockr/config.yml`)
- `--force, -f`: Force operation without confirmation
- `--verbose`: Enable verbose/debug output

### Session Management

Lockr uses session-based authentication:
- Sessions last 15 minutes with activity-based renewal
- Automatic logout on session expiration
- View session status: `lockr status`

With keyring enabled:
- First authentication saves password to keyring (with your permission)
- Subsequent commands authenticate automatically
- No password prompts until session expires

## Configuration

### Vault Location

Default: `~/.lockr/vault.lockr`

Use a custom location:
```bash
lockr --vault /path/to/vault.lockr list
```

### Environment Variables

```bash
# Set custom vault path
export LOCKR_VAULT_PATH=/secure/location/vault.lockr

# Disable keyring
export LOCKR_KEYRING_DISABLED=1
```

## Development

### Prerequisites

- Go 1.24 or later
- CGO enabled (for SQLCipher)
- macOS/Linux: gcc/clang
- Windows: MinGW

### Build

```bash
cd go/
make build
```

### Test

```bash
# Run all tests
make test

# Run specific package tests
go test ./internal/keyring/... -v

# Run with coverage
make test-coverage
```

### Benchmarks

```bash
make benchmark
```

## Security

### Encryption

- AES-256 encryption via SQLCipher
- PBKDF2 key derivation
- Encrypted at rest, decrypted only in memory

### Key Storage (Keyring)

- **macOS**: Keychain with user-level access control
- **Linux**: Secret Service API (encrypted storage)
- **Windows**: Credential Manager (encrypted)

### Best Practices

1. **Use strong master passwords**: 16+ characters, mixed case, numbers, symbols
2. **Enable keyring only on trusted devices**
3. **Regular password rotation**: Change master password periodically
4. **Secure your system**: Keyring security depends on system security
5. **Clear keyring when done**: Run `lockr keyring clear` when finished

## Performance

### Benchmarks

Tested on M1 MacBook Pro:
- Database operations: < 10ms
- Fuzzy search (10,000 entries): < 100ms
- Interactive response: < 50ms

### Scalability

- Supports 10,000+ secrets
- Efficient indexing for fast lookups
- Minimal memory footprint

## Architecture

```
go/
├── cmd/lockr/          # Main entry point
├── internal/
│   ├── cli/            # CLI commands and interface
│   ├── database/       # SQLCipher database operations
│   ├── session/        # Authentication and session management
│   ├── keyring/        # System keyring integration
│   ├── search/         # Fuzzy search engine
│   ├── clipboard/      # Clipboard management
│   └── ...
├── docs/               # Documentation
└── Makefile           # Build automation
```

## Troubleshooting

### Build Issues

**CGO Errors**: Ensure CGO is enabled:
```bash
export CGO_ENABLED=1
go build ./cmd/lockr
```

**SQLCipher Missing**:
- macOS: `brew install sqlcipher`
- Ubuntu: `sudo apt-get install libsqlcipher-dev`
- Fedora: `sudo dnf install sqlcipher-devel`

### Runtime Issues

**Authentication Fails**: Check vault path and password
```bash
lockr --verbose --vault ~/.lockr/vault.lockr list
```

**Keyring Not Working**: See [docs/KEYRING.md](docs/KEYRING.md) troubleshooting section

**Clipboard Issues**: macOS only currently supported
```bash
# Check clipboard manager availability
lockr --verbose get mykey
```

## Compatibility

### Cross-Implementation

All Lockr implementations (Python, Go, Zig) create compatible vault files:
- Same database schema
- Same encryption format
- Portable across implementations

Switch between implementations:
```bash
# Create with Python
python -m lockr set mykey

# Read with Go
./bin/lockr get mykey
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines.

## License

See [LICENSE](../LICENSE) for details.

## Related Documentation

- [Keyring Integration](docs/KEYRING.md) - Detailed keyring documentation
- [Architecture](docs/ARCHITECTURE.md) - System design and components
- [Security](docs/SECURITY.md) - Security considerations and best practices
- [API Reference](docs/API.md) - Internal API documentation

## Comparison: Python vs Go

| Feature | Python | Go |
|---------|--------|-----|
| Performance | Good | Excellent |
| Binary Size | N/A (interpreted) | ~10MB (static) |
| Startup Time | ~100ms | ~10ms |
| Dependencies | Multiple (pip) | None (static binary) |
| Keyring Support | ✅ Yes | ✅ Yes |
| Use Case | Development, scripting | Production, distribution |

Choose **Go** for:
- Production deployments
- Performance-critical use cases
- Single binary distribution
- Minimal dependencies

Choose **Python** for:
- Rapid prototyping
- Integration with Python ecosystem
- Development and testing
