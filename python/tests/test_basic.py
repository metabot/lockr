"""
Basic functionality tests for Lockr.
"""

import tempfile
import os
from pathlib import Path

import pytest

from lockr.database.manager import VaultDatabase
from lockr.utils.validation import validate_key, get_validation_error_message
from lockr.exceptions import (
    AuthenticationError,
    DuplicateKeyError,
    KeyNotFoundError,
)


class TestValidation:
    """Test input validation."""

    def test_valid_keys(self):
        """Test that valid keys pass validation."""
        valid_keys = [
            "password",
            "email-password",
            "api_key",
            "user@domain.com",
            "test123",
            "special-chars._-@#$%^&*()",
        ]

        for key in valid_keys:
            assert validate_key(key), f"Key '{key}' should be valid"

    def test_invalid_keys(self):
        """Test that invalid keys fail validation."""
        invalid_keys = [
            "",  # Empty
            "a" * 257,  # Too long
            "key with spaces",  # Spaces
            "key\nwith\nnewlines",  # Newlines
            "key\twith\ttabs",  # Tabs
        ]

        for key in invalid_keys:
            assert not validate_key(key), f"Key '{key}' should be invalid"

    def test_validation_error_messages(self):
        """Test validation error messages."""
        assert "cannot be empty" in get_validation_error_message("")
        assert "longer than 256" in get_validation_error_message("a" * 257)
        assert "invalid characters" in get_validation_error_message("key with spaces")


class TestVaultDatabase:
    """Test vault database operations."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault for testing."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        vault = VaultDatabase(vault_path)
        yield vault

        # Cleanup
        vault.close()
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    def test_vault_creation_and_connection(self, temp_vault):
        """Test vault creation and password authentication."""
        password = "test-password-123"

        # Should be able to connect with password
        assert temp_vault.connect(password)
        assert temp_vault.connection is not None

        # Close and reconnect with same password
        temp_vault.close()
        assert temp_vault.connect(password)

    def test_wrong_password_fails(self, temp_vault):
        """Test that wrong password fails authentication."""
        password = "correct-password"
        wrong_password = "wrong-password"

        # Create vault with correct password
        temp_vault.connect(password)
        temp_vault.close()

        # Should fail with wrong password
        with pytest.raises(AuthenticationError):
            temp_vault.connect(wrong_password)

    def test_add_and_get_secret(self, temp_vault):
        """Test adding and retrieving secrets."""
        password = "test-password"
        temp_vault.connect(password)

        # Add secret
        temp_vault.add_secret("test-key", "test-value")

        # Retrieve secret
        value = temp_vault.get_secret("test-key")
        assert value == "test-value"

        # Case-insensitive retrieval
        value = temp_vault.get_secret("TEST-KEY")
        assert value == "test-value"

    def test_duplicate_key_fails(self, temp_vault):
        """Test that adding duplicate key fails."""
        password = "test-password"
        temp_vault.connect(password)

        temp_vault.add_secret("duplicate-key", "value1")

        with pytest.raises(DuplicateKeyError):
            temp_vault.add_secret("duplicate-key", "value2")

    def test_update_secret(self, temp_vault):
        """Test updating existing secret."""
        password = "test-password"
        temp_vault.connect(password)

        # Add and update secret
        temp_vault.add_secret("update-key", "original-value")
        temp_vault.update_secret("update-key", "updated-value")

        # Verify update
        value = temp_vault.get_secret("update-key")
        assert value == "updated-value"

    def test_update_nonexistent_key_fails(self, temp_vault):
        """Test that updating non-existent key fails."""
        password = "test-password"
        temp_vault.connect(password)

        with pytest.raises(KeyNotFoundError):
            temp_vault.update_secret("nonexistent-key", "value")

    def test_delete_secret(self, temp_vault):
        """Test deleting secrets."""
        password = "test-password"
        temp_vault.connect(password)

        # Add and delete secret
        temp_vault.add_secret("delete-key", "delete-value")
        temp_vault.delete_secret("delete-key")

        # Verify deletion
        value = temp_vault.get_secret("delete-key")
        assert value is None

    def test_delete_nonexistent_key_fails(self, temp_vault):
        """Test that deleting non-existent key fails."""
        password = "test-password"
        temp_vault.connect(password)

        with pytest.raises(KeyNotFoundError):
            temp_vault.delete_secret("nonexistent-key")

    def test_list_keys(self, temp_vault):
        """Test listing all keys."""
        password = "test-password"
        temp_vault.connect(password)

        # Empty vault
        keys = temp_vault.list_all_keys()
        assert keys == []

        # Add some secrets
        test_keys = ["key1", "key2", "key3"]
        for key in test_keys:
            temp_vault.add_secret(key, f"value-{key}")

        # List should return sorted keys
        keys = temp_vault.list_all_keys()
        assert sorted(keys) == sorted(test_keys)

    def test_search_keys(self, temp_vault):
        """Test searching keys with patterns."""
        password = "test-password"
        temp_vault.connect(password)

        # Add test data
        test_data = [
            "email-password",
            "email-backup",
            "api-key",
            "database-password",
            "test-email",
        ]

        for key in test_data:
            temp_vault.add_secret(key, f"value-{key}")

        # Search for email-related keys
        matches = temp_vault.search_keys("email")
        match_keys = [match[0] for match in matches]

        expected_email_keys = ["email-password", "email-backup", "test-email"]
        assert all(key in match_keys for key in expected_email_keys)

    def test_vault_info(self, temp_vault):
        """Test vault information retrieval."""
        info = temp_vault.get_vault_info()

        assert "file_path" in info
        assert "exists" in info

        # After connecting, should have more info
        password = "test-password"
        temp_vault.connect(password)

        info = temp_vault.get_vault_info()
        assert "secret_count" in info
        assert info["secret_count"] == 0

        # Add a secret and check count
        temp_vault.add_secret("test", "value")
        info = temp_vault.get_vault_info()
        assert info["secret_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__])
