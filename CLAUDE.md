# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lockr is a personal vault CLI application for secure storage and retrieval of secrets (passwords, tokens, etc.) with interactive fuzzy search capabilities. Built with SQLCipher for encrypted storage and designed to handle thousands of entries efficiently.

**Multi-Language Implementation:**
- **Python**: Rapid prototyping and reference implementation
- **Go**: Performance-optimized single binary
- **Zig**: Future consideration for maximum performance
- **Compatibility**: All implementations create identical vault files

## Development Commands

### Python Implementation
```bash
cd python/
uv sync --dev

# Run CLI
uv run python -m lockr --help

# Testing
uv run pytest tests/ -v --cov=lockr

# Type checking and formatting
uv run mypy lockr/
uv fmt
```

### Go Implementation
```bash
cd go/
go mod download

# Build binary
make build

# Run CLI
./bin/lockr --help

# Testing
make test
make benchmark

# Linting
golangci-lint run
```

### Cross-Implementation Testing
```bash
# Compatibility tests
./tests/compatibility/test_vault_compatibility.sh

# Performance comparison
./tests/performance/benchmark_all.sh

# Security validation
./tests/security/validate_all.sh
```

## Architecture

### Core Components
- **SQLCipher Database**: Encrypted storage with AES-256
- **Interactive Fuzzy Search**: FZF-like interface with real-time filtering
- **Session Management**: 15-minute authentication timeout
- **Clipboard Integration**: Auto-copy with 60-second auto-clear
- **CLI Interface**: Click-based command structure

### Key Files

**Shared:**
- `schema/vault.sql` - Shared database schema across implementations
- `tests/compatibility/` - Cross-implementation tests

**Python Implementation:**
- `python/lockr/database/manager.py` - SQLCipher database operations
- `python/lockr/session/manager.py` - Authentication and session handling
- `python/lockr/search/fuzzy.py` - Interactive fuzzy matching engine
- `python/lockr/search/interactive.py` - prompt_toolkit UI implementation
- `python/lockr/clipboard/manager.py` - macOS clipboard operations
- `python/lockr/cli.py` - Main CLI interface

**Go Implementation:**
- `go/internal/database/manager.go` - SQLCipher database operations
- `go/internal/session/manager.go` - Authentication and session handling
- `go/internal/search/fuzzy.go` - Interactive fuzzy matching engine
- `go/internal/search/interactive.go` - bubbletea UI implementation
- `go/internal/clipboard/manager.go` - macOS clipboard operations
- `go/internal/cli/root.go` - Main CLI interface

### Database Schema
- `secrets` table: encrypted key-value storage with metadata
- `auth_attempts` table: failed authentication logging
- `sessions` table: session management and timeout

## Development Guidelines

### Security Requirements
- All secrets encrypted at rest with SQLCipher
- No plaintext storage of sensitive data
- Secure memory handling and cleanup
- Session-based authentication with timeout

### Performance Targets
- < 10ms database operations
- < 100ms fuzzy search for 10,000 entries
- < 50ms interactive response time

### Key Features
- Case-insensitive key matching
- Keys limited to 256 chars (alphanumeric + common punctuation)
- Interactive fuzzy search (top 5 results + "more" indicator)
- Automatic clipboard management
- Failed attempt logging with username and timestamp

## Testing Strategy

Run all tests before committing:
```bash
# Unit tests
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# Performance tests
uv run python tests/performance/test_large_dataset.py

# Security tests
uv run python tests/security/test_encryption.py
```