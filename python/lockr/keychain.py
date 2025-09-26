"""
Cross-platform keychain/keyring integration for Lockr.

Supports secure password storage using:
- macOS: Keychain Access
- Windows: Windows Credential Store
- Linux: Secret Service API (GNOME Keyring, KWallet, etc.)
"""

import platform
import logging
import hashlib
import secrets
import base64
from pathlib import Path

try:
    import keyring
    from keyring.errors import KeyringError, KeyringLocked, NoKeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None  # type: ignore

    class KeyringError(Exception):  # type: ignore[no-redef]
        pass

    class KeyringLocked(KeyringError):  # type: ignore[no-redef]
        pass

    class NoKeyringError(KeyringError):  # type: ignore[no-redef]
        pass


logger = logging.getLogger(__name__)


class KeychainManager:
    """Cross-platform keychain manager for storing vault passwords."""

    SERVICE_NAME = "com.lockr.vault"

    def __init__(self, enabled: bool = True):
        """
        Initialize keychain manager.

        Args:
            enabled: Whether keychain integration is enabled
        """
        self.enabled = enabled and KEYRING_AVAILABLE
        self.platform = platform.system().lower()

        if not KEYRING_AVAILABLE and enabled:
            logger.warning("Keyring library not available. Keychain integration disabled.")

        if self.enabled:
            self._ensure_keyring_available()

    def _ensure_keyring_available(self) -> None:
        """Ensure keyring backend is available and working."""
        try:
            # Test keyring availability
            backend = keyring.get_keyring()
            logger.debug(f"Using keyring backend: {backend}")

            # Check if backend is viable
            if hasattr(backend, 'priority') and backend.priority < 1:
                logger.warning(f"Keyring backend {backend} may not be reliable")

        except (KeyringError, NoKeyringError) as e:
            logger.warning(f"Keyring not available: {e}")
            self.enabled = False

    def _get_username(self, vault_path: str) -> str:
        """Generate unique username for vault path."""
        # Use absolute path to ensure uniqueness
        abs_path = str(Path(vault_path).resolve())
        return f"vault:{abs_path}"

    def _derive_keychain_key(self, master_password: str, vault_path: str) -> str:
        """
        Derive a key for keychain storage from master password and vault path.

        This creates a deterministic but unique key that can be regenerated
        from the master password, avoiding storing the master password directly.

        Args:
            master_password: The user's master password
            vault_path: Path to the vault file

        Returns:
            Base64-encoded derived key for keychain storage
        """
        # Use vault path as salt to ensure unique keys per vault
        salt = str(Path(vault_path).resolve()).encode('utf-8')

        # Derive key using PBKDF2
        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            master_password.encode('utf-8'),
            salt,
            100000,  # iterations
            32  # key length (256 bits)
        )

        # Return as base64 for storage
        return base64.b64encode(derived_key).decode('ascii')

    def _verify_derived_key(self, master_password: str, vault_path: str, stored_key: str) -> bool:
        """
        Verify that a stored derived key matches the master password.

        Args:
            master_password: The master password to verify
            vault_path: Path to the vault file
            stored_key: The stored derived key from keychain

        Returns:
            True if the derived key matches
        """
        expected_key = self._derive_keychain_key(master_password, vault_path)
        return secrets.compare_digest(expected_key, stored_key)

    def is_supported(self) -> bool:
        """Check if keychain is supported on current platform."""
        return self.enabled

    def get_platform_info(self) -> str:
        """Get platform-specific keychain information."""
        if not self.enabled:
            return "Keychain integration disabled"

        platform_info = {
            "darwin": "macOS Keychain Access",
            "windows": "Windows Credential Manager",
            "linux": "Linux Secret Service (GNOME Keyring/KWallet)"
        }

        backend_name = "Unknown"
        try:
            backend = keyring.get_keyring()
            backend_name = backend.__class__.__name__
        except Exception:
            pass

        platform_name = platform_info.get(self.platform, f"Platform: {self.platform}")
        return f"{platform_name} ({backend_name})"

    def store_password(self, vault_path: str, password: str) -> bool:
        """
        Store derived key for vault password in system keychain.

        Args:
            vault_path: Path to vault file
            password: Master password to derive key from

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Keychain disabled, not storing password")
            return False

        try:
            username = self._get_username(vault_path)
            derived_key = self._derive_keychain_key(password, vault_path)
            keyring.set_password(self.SERVICE_NAME, username, derived_key)
            logger.debug(f"Derived key stored in keychain for vault: {vault_path}")
            return True

        except KeyringLocked:
            logger.warning("Keychain is locked. Cannot store password.")
            return False
        except KeyringError as e:
            logger.error(f"Failed to store password in keychain: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing password: {e}")
            return False

    def has_stored_password(self, vault_path: str) -> bool:
        """
        Check if there's a stored derived key for this vault.

        Args:
            vault_path: Path to vault file

        Returns:
            True if a derived key is stored, False otherwise
        """
        if not self.enabled:
            return False

        try:
            username = self._get_username(vault_path)
            stored_key = keyring.get_password(self.SERVICE_NAME, username)
            return stored_key is not None

        except (KeyringLocked, KeyringError, Exception):
            return False

    def verify_password(self, vault_path: str, password: str) -> bool:
        """
        Verify if the given password matches the stored derived key.

        Args:
            vault_path: Path to vault file
            password: Master password to verify

        Returns:
            True if password matches stored derived key, False otherwise
        """
        if not self.enabled:
            return False

        try:
            username = self._get_username(vault_path)
            stored_key = keyring.get_password(self.SERVICE_NAME, username)

            if not stored_key:
                logger.debug(f"No derived key found in keychain for vault: {vault_path}")
                return False

            is_valid = self._verify_derived_key(password, vault_path, stored_key)
            if is_valid:
                logger.debug(f"Password verified against keychain for vault: {vault_path}")
            else:
                logger.debug(f"Password verification failed for vault: {vault_path}")

            return is_valid

        except KeyringLocked:
            logger.warning("Keychain is locked. Cannot verify password.")
            return False
        except KeyringError as e:
            logger.error(f"Failed to verify password from keychain: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error verifying password: {e}")
            return False

    def delete_password(self, vault_path: str) -> bool:
        """
        Remove vault derived key from system keychain.

        Args:
            vault_path: Path to vault file

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            username = self._get_username(vault_path)
            keyring.delete_password(self.SERVICE_NAME, username)
            logger.debug(f"Derived key deleted from keychain for vault: {vault_path}")
            return True

        except KeyringLocked:
            logger.warning("Keychain is locked. Cannot delete password.")
            return False
        except KeyringError as e:
            # Password might not exist, which is fine
            logger.debug(f"Could not delete derived key from keychain: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting derived key: {e}")
            return False

    def list_stored_vaults(self) -> list[str]:
        """
        List vault paths that have passwords stored in keychain.

        Note: This is a best-effort implementation as keyring doesn't
        provide a standard way to list all stored credentials.

        Returns:
            List of vault paths (may be empty if not supported)
        """
        # This is difficult to implement generically across all platforms
        # as keyring doesn't provide a standard list method
        logger.debug("list_stored_vaults not implemented for current keyring backend")
        return []

    def test_keychain_access(self) -> bool:
        """
        Test keychain access by storing and verifying a test derived key.

        Returns:
            True if keychain is working, False otherwise
        """
        if not self.enabled:
            return False

        test_service = f"{self.SERVICE_NAME}.test"
        test_username = "test"
        test_password = "test_password_123"
        test_vault_path = "/tmp/test_vault.lockr"

        try:
            # Generate test derived key
            test_derived_key = self._derive_keychain_key(test_password, test_vault_path)

            # Store test credential
            keyring.set_password(test_service, test_username, test_derived_key)

            # Retrieve test credential
            retrieved = keyring.get_password(test_service, test_username)

            # Clean up test credential
            try:
                keyring.delete_password(test_service, test_username)
            except Exception:
                pass  # Cleanup failure is not critical

            # Check if test passed
            success = retrieved == test_derived_key
            if success:
                logger.debug("Keychain access test passed")
            else:
                logger.warning("Keychain access test failed")

            return success

        except Exception as e:
            logger.error(f"Keychain access test failed: {e}")
            return False


def get_keychain_manager(enabled: bool = True) -> KeychainManager:
    """
    Get a configured keychain manager instance.

    Args:
        enabled: Whether keychain integration should be enabled

    Returns:
        KeychainManager instance
    """
    return KeychainManager(enabled=enabled)