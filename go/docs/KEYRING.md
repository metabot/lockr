# Keyring Integration - Master Key Approach

Lockr's keyring integration uses a **master key encryption** approach that provides automatic authentication while keeping your vault files fully portable across environments.

## Key Benefit: Portable Vault Files

Unlike storing passwords directly, Lockr encrypts your password with a master key. This means:
- ✅ Auto-login on trusted devices (convenience)
- ✅ Vault files work on any machine (portability)
- ✅ Use different passwords per environment (flexibility)
- ✅ No keyring dependency for vault files (independence)

**Example**: Copy your `vault.lockr` file to another machine and open it with any password - it just works!

## How It Works

### Architecture

```
System Keyring stores:
├── Master Key (256-bit random key)
└── Encrypted Password (AES-256-GCM encrypted)

Vault File (vault.lockr):
└── Encrypted with SQLCipher (independent of keyring)
```

### Process

**Saving Credentials:**
1. Generate random 256-bit master key
2. Encrypt your password with master key (AES-256-GCM + PBKDF2)
3. Store both in system keyring

**Auto-Login:**
1. Retrieve master key and encrypted password from keyring
2. Decrypt password
3. Authenticate with vault

**Portability:**
- Vault file encryption is independent of keyring
- Copy vault to any machine and use with any password
- Keyring provides local convenience only

## Supported Platforms

| Platform | Backend | Status |
|----------|---------|--------|
| macOS    | Keychain | ✅ Supported |
| Linux    | Secret Service (GNOME Keyring, KWallet) | ✅ Supported |
| Windows  | Credential Manager | ✅ Supported |

## Quick Start

```bash
# First use - you'll be prompted to save credentials
$ lockr list
Enter vault password: ••••••••
Save password to system keyring for auto-login? (y/N): y
Password saved to keyring (vault file remains portable)

# Subsequent uses - automatic authentication
$ lockr list
[no password prompt!]

# Check keyring status
$ lockr keyring status
Keyring Status:
  Service: lockr
  Username: masterkey
  Enabled: true
  Has Stored Data: true
```

## Commands

### Status

```bash
lockr keyring status
```

Shows keyring configuration and whether credentials are stored.

### Save Credentials

```bash
lockr keyring set
```

Prompts for your vault password, validates it, then stores encrypted credentials.

**Options:**
- `--force`, `-f`: Overwrite existing credentials without confirmation

### Clear Credentials

```bash
lockr keyring clear
```

Removes stored credentials from keyring. You'll need to enter password manually next time.

**Options:**
- `--force`, `-f`: Skip confirmation prompt

### Enable/Disable

```bash
# Temporarily disable without removing credentials
lockr keyring disable

# Re-enable
lockr keyring enable
```

## Use Cases

### 1. Development Machine (Auto-Login)

```bash
# Set up once
lockr keyring set
Enter vault password to store: ••••••••
Password saved to keyring successfully

# Use without passwords
lockr get api-key
lockr set new-key "value"
lockr list
```

### 2. Multiple Environments (Portable Vaults)

```bash
# Development machine
lockr set secret "dev-value"
tar czf vault-backup.tar.gz ~/.lockr/vault.lockr

# Production server (copy vault file)
scp vault-backup.tar.gz prod:/tmp/
ssh prod
tar xzf /tmp/vault-backup.tar.gz -C ~/
lockr --vault ~/.lockr/vault.lockr get secret
Enter vault password: [prod-password]  # Different password, same vault!
```

### 3. Shared Computer (No Keyring)

```bash
# Disable keyring on shared machines
lockr keyring disable

# Always prompts for password
lockr list
Enter vault password: ••••••••
```

### 4. Password Rotation

```bash
# Change vault password
# (Note: Changing SQLCipher password is separate from keyring)

# Update keyring with new password
lockr keyring set --force
Enter vault password to store: [new-password]
Password saved to keyring successfully
```

## Security

### Encryption Layers

1. **OS Keyring Encryption**: Master key and encrypted password stored in system keyring
2. **Master Key Encryption**: Password encrypted with AES-256-GCM + PBKDF2 (100,000 iterations)
3. **Vault Encryption**: SQLCipher AES-256 encryption (independent)

### Security Properties

- Master key: 256-bit cryptographically secure random
- Password encryption: AES-256-GCM with PBKDF2-derived keys
- Authentication: GCM mode provides integrity verification
- Memory safety: Master keys cleared from memory after use

### Best Practices

✅ **DO:**
- Use keyring on your personal, trusted devices
- Use different passwords on different environments for defense in depth
- Clear keyring when selling/disposing of machines
- Keep vault files backed up separately

❌ **DON'T:**
- Enable keyring on shared/public computers
- Rely solely on keyring for backups (backup vault files!)
- Store production passwords in development keyrings

## Troubleshooting

### Keyring Not Working

```bash
# Check status
lockr keyring status

# Re-save credentials
lockr keyring clear
lockr keyring set

# Test with verbose mode
lockr --verbose list
```

### Platform-Specific Setup

**Linux:**
```bash
# Install Secret Service provider
sudo apt-get install gnome-keyring  # Ubuntu/Debian
sudo dnf install gnome-keyring      # Fedora
sudo pacman -S gnome-keyring        # Arch
```

**macOS:**
- Keychain Access should work by default
- Check System Settings → Privacy & Security if issues occur

**Windows:**
- Credential Manager should work by default (Windows 7+)
- Check Control Panel → Credential Manager

### Wrong Password Stored

```bash
lockr keyring set --force
Enter vault password to store: [correct-password]
```

### Authentication Loops

If lockr keeps asking for password despite keyring:

```bash
# Verify credentials exist
lockr keyring status  # Should show "Has Stored Data: true"

# Clear and re-set
lockr keyring clear
lockr keyring set

# Check verbose output
lockr --verbose get test
```

## Technical Details

### Storage Format

Keyring stores JSON data:
```json
{
  "master_key": "base64-encoded-256-bit-key",
  "encrypted_password": "base64(salt+nonce+ciphertext)"
}
```

### Encryption Details

**Master Key:**
- Algorithm: Random 256-bit key
- Source: `crypto/rand` (cryptographically secure)

**Password Encryption:**
- Algorithm: AES-256-GCM
- Key Derivation: PBKDF2 with SHA-256 (100,000 iterations)
- Salt: 128-bit random
- Nonce: 96-bit random
- Output: `base64(salt || nonce || ciphertext || tag)`

### Why Master Key Approach?

**Alternative 1: Store Password Directly**
- ❌ Vault tied to specific keyring
- ❌ Can't change password without updating keyring everywhere
- ❌ Less portable

**Alternative 2: Don't Use Keyring**
- ❌ No auto-login convenience
- ✅ Maximum portability

**Our Approach: Master Key Encryption**
- ✅ Auto-login convenience
- ✅ Full portability
- ✅ Independent password management
- ✅ Multiple security layers

## Examples

### Multi-Machine Workflow

```bash
# Machine A (development)
lockr keyring set  # Set up auto-login
lockr set prod-api-key "abc123"

# Copy vault to Machine B
scp ~/.lockr/vault.lockr machineB:~/

# Machine B (production)
lockr --vault ~/vault.lockr keyring set  # Different password!
Enter vault password to store: [different-password]

# Both machines can access same vault with different passwords
```

### Temporary Keyring Disable

```bash
# Presentation/demo mode
lockr keyring disable
lockr list  # Prompts for password

# Resume normal use
lockr keyring enable
lockr list  # Auto-login
```

### Debugging

```bash
# Verbose keyring status
lockr --verbose keyring status

# Trace authentication
lockr --verbose list
# Output shows: "[DEBUG] Authenticated using keyring" or error

# Check keyring data (advanced)
# On macOS:
security find-generic-password -s lockr -a masterkey
```

## FAQ

**Q: Can I use the same vault on multiple machines?**
A: Yes! That's the whole point. Copy the vault file anywhere - it's independent of keyring.

**Q: Do I need the same password everywhere?**
A: No. Each machine can have its own password and keyring. The vault file itself is portable.

**Q: What if I lose my keyring data?**
A: No problem. Just enter your password manually. The vault file is independent.

**Q: Is my password secure?**
A: Yes. It's encrypted with AES-256-GCM using a PBKDF2-derived key from a random master key.

**Q: Can other apps access my password?**
A: No. OS keyrings restrict access to the lockr application only.

**Q: Does keyring make my vault less secure?**
A: No. Vault encryption is completely independent. Keyring only provides convenience.

**Q: Should I backup keyring data?**
A: No. Keyring is local convenience. Always backup your vault files instead.

**Q: Can I use this in CI/CD?**
A: Keyring is for interactive use. For CI/CD, use environment variables or dedicated secret management.

**Q: What's stored in the keyring exactly?**
A: A randomly generated master key and your password encrypted with that key. Not your password in plaintext.

**Q: Can I audit what's in my keyring?**
A: Yes:
```bash
# macOS
security find-generic-password -s lockr -a masterkey -g

# Linux
secret-tool lookup service lockr username masterkey

# Windows
cmdkey /list | findstr lockr
```

## Code References

- [internal/crypto/masterkey.go](../internal/crypto/masterkey.go) - Master key encryption
- [internal/keyring/manager.go](../internal/keyring/manager.go) - Keyring operations
- [internal/session/manager.go](../internal/session/manager.go) - Session management
- [internal/cli/keyring.go](../internal/cli/keyring.go) - CLI commands
