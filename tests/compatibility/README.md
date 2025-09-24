# Compatibility Tests

This directory contains tests to ensure that all language implementations of Lockr create compatible vault files and exhibit identical behavior.

## Test Coverage

### Vault File Compatibility
- **Cross-implementation file reading**: Vault files created by one implementation must be readable by all others
- **Schema consistency**: All implementations must create identical database schemas
- **Data integrity**: Secret values must be identical across implementations

### CLI Behavior Consistency
- **Command interface**: All implementations must support identical command syntax
- **Output formatting**: Error messages and success messages should be consistent
- **Exit codes**: Identical exit codes for success/failure scenarios

### Security Consistency
- **Encryption compatibility**: Same password must unlock vaults across implementations
- **Session behavior**: 15-minute timeout behavior must be identical
- **Failed attempt logging**: Authentication attempts must be logged identically

## Test Scripts

### `test_vault_compatibility.sh`
Tests vault file interoperability between implementations:

```bash
#!/bin/bash

# Create vault with Python implementation
python/lockr add "test-key" "test-value" --vault-file shared.lockr

# Verify Go implementation can read it
go/lockr get "test-key" --vault-file shared.lockr

# Add secret with Go implementation
go/lockr add "go-key" "go-value" --vault-file shared.lockr

# Verify Python implementation can read both
python/lockr list --vault-file shared.lockr
```

### `test_cli_consistency.sh`
Validates CLI interface consistency:

```bash
#!/bin/bash

# Compare help output
python/lockr --help > python_help.txt
go/lockr --help > go_help.txt

# Should be functionally identical (allowing for language-specific differences)
diff -u python_help.txt go_help.txt
```

### `test_performance_parity.sh`
Compares performance characteristics:

```bash
#!/bin/bash

# Generate large test dataset
python/lockr add "test-1000" "value" --vault-file perf.lockr
# ... (add 1000 entries)

# Time fuzzy search performance
time python/lockr get "test" --vault-file perf.lockr > /dev/null
time go/lockr get "test" --vault-file perf.lockr > /dev/null
```

## Validation Criteria

### ✅ Pass Criteria
- Vault files are interchangeable between implementations
- CLI commands produce functionally identical results
- Performance differences are within expected ranges (Go 2-5x faster)
- Security behaviors are identical

### ❌ Fail Criteria
- Vault file incompatibility
- Different command syntax or behavior
- Security vulnerabilities in any implementation
- Data corruption or loss