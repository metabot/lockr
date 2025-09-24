# Lockr

A secure personal vault CLI for storing and retrieving secrets with interactive fuzzy search.

## Features

- 🔒 **Secure Storage**: SQLCipher encryption with AES-256
- 🔍 **Interactive Fuzzy Search**: FZF-like real-time search with Tab navigation
- 📋 **Clipboard Integration**: Auto-copy secrets with 60-second auto-clear
- ⚡ **Fast Performance**: Optimized for thousands of entries
- 🎯 **Smart Matching**: Intelligent scoring for better search results
- 🛡️ **Session Management**: 15-minute authentication timeout

## Installation

### From PyPI (when published)
```bash
pip install lockr
```

### From Source
```bash
git clone https://github.com/lockr-dev/lockr.git
cd lockr/python
pip install -e .
```

### Development Installation
```bash
git clone https://github.com/lockr-dev/lockr.git
cd lockr/python
pip install -e ".[dev]"
```

## Quick Start

```bash
# Create a new vault and add your first secret
lockr add github_token

# Interactive search and retrieve (default behavior)
lockr get

# Search for specific patterns
lockr get github

# List all secrets
lockr list

# Update existing secrets
lockr update github_token

# Delete secrets
lockr delete github_token
```

## Interactive Search

Lockr's standout feature is its **interactive fuzzy search**:

- **Real-time matching**: See results as you type each character
- **Smart scoring**: Prioritizes exact matches, prefixes, and word boundaries
- **Tab navigation**: Use Tab/↓ and Shift+Tab/↑ to navigate results
- **Match counts**: Shows "5 matches (showing top 3)" for context
- **Auto-clipboard**: Selected secrets are automatically copied and auto-cleared

### Search Examples

```bash
# Start interactive search
lockr get

# Search with partial key (falls back to fuzzy search)
lockr get api      # Finds "github_api_key", "stripe_api_token", etc.

# Exact key lookup (bypass interactive mode)
lockr get exact_key_name --no-interactive
```

## Keyboard Shortcuts

- **Tab** / **↓**: Move to next result
- **Shift+Tab** / **↑**: Move to previous result
- **Enter**: Select highlighted result
- **Esc**: Cancel and exit

## Vault Management

- **Default vault**: `vault.lockr` in current directory
- **Custom vault**: Use `-f/--vault-file` option
- **Master password**: Required for all operations (prompted securely)
- **Session timeout**: 15 minutes of inactivity

## Security

- All secrets encrypted at rest with SQLCipher (AES-256)
- Master password never stored, only used for key derivation
- Failed authentication attempts logged
- Clipboard auto-cleared after 60 seconds
- No plaintext storage of sensitive data

## Requirements

- Python 3.12+
- SQLCipher (installed via sqlcipher3-wheels)
- Cross-platform: macOS, Linux, Windows

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy lockr/

# Build package
python -m build
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.