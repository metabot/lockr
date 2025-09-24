# Lockr Personal Vault - Requirements Specification

## Overview
Personal vault CLI application for secure storage and retrieval of secrets (passwords, tokens, etc.) with fuzzy matching and session-based authentication.

## Core Features

### Security & Authentication
- **Encryption**: AES-256 with PBKDF2 key derivation
- **Master Password**: Required for vault access
- **Session Management**: 15-minute timeout after authentication
- **Failed Attempts Logging**: Track timestamp and username for failed authentication attempts
- **Backup Strategy**: Manual file backup (automated recovery deferred to future versions)

### Data Structure
- **Storage Format**: Key-value pairs for secrets
- **Key Properties**:
  - Case-insensitive matching
  - Alphanumeric characters plus common punctuation allowed
  - Maximum length: 256 characters
- **Metadata**: Store created date, last accessed timestamp, failed attempt logs

### CLI Interface & User Experience
- **Commands**:
  - `add <key> [value]` - Add new secret
  - `get [pattern]` - Interactive fuzzy lookup for secret retrieval
  - `list [pattern]` - List keys with optional fuzzy filtering
  - `update <key> <value>` - Update existing secret
  - `delete <key>` - Remove secret
- **Interactive Fuzzy Matching**:
  - FZF-like behavior for `get` command
  - Real-time filtering with fuzzy scoring algorithm
  - Prioritize exact substring matches, then fuzzy matches
  - Arrow key navigation through ranked matches
  - Display: Show top 5 results with "...and X more" indicator if applicable
  - Key names only (no metadata preview)
  - Performance: Optimized for thousands of entries
  - Enter to select and copy to clipboard
  - Esc to cancel selection
- **Clipboard Integration**:
  - Auto-copy retrieved passwords to clipboard
  - Auto-clear clipboard after 60 seconds for security
- **Input Security**: Hidden password entry for sensitive data

### File Format & Storage
- **Format**: Single encrypted JSON file
- **Location**: Local storage only
- **Portability**: Cross-platform file format
- **Structure**: Encrypted container with metadata and key-value data

### Platform Support
- **Primary Target**: macOS
- **Future Compatibility**: Design for Linux and Windows support

## Technical Specifications

### Session Management
- 15-minute authentication timeout
- Store session state securely in memory
- Automatic session cleanup on timeout

### Fuzzy Matching
- Default behavior for key retrieval
- Pattern matching similar to ripgrep functionality
- Auto-complete suggestions for partial matches

### Security Logging
- Log failed authentication attempts with:
  - Timestamp
  - System username
  - Attempt details
- Store logs within encrypted vault file

### Key Validation
- Allowed characters: alphanumeric + common punctuation (`-`, `_`, `.`, `@`, etc.)
- Maximum length: 256 characters
- Case-insensitive storage and matching

### Clipboard Security
- Automatic copy to clipboard on successful retrieval
- Automatic clipboard clearing after configurable timeout
- Platform-specific clipboard integration (starting with macOS)

## Implementation Phases

### Phase 1 (MVP)
- Basic CRUD operations
- AES-256 encryption
- Session-based authentication
- Simple key matching

### Phase 2
- Fuzzy matching with auto-complete
- Failed attempt logging
- Clipboard integration with auto-clear

### Phase 3
- Enhanced security features
- Cross-platform support
- Import/export functionality

## Non-Functional Requirements
- **Performance**:
  - Sub-second response for all operations
  - Interactive fuzzy search optimized for thousands of entries
  - Efficient key indexing and search algorithms
- **Usability**:
  - FZF-like interactive interface
  - Intuitive CLI interface with helpful error messages
- **Security**: No plaintext storage, secure memory handling
- **Maintainability**: Clean, documented codebase for future enhancements