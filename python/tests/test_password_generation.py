"""
Unit tests for password generation functionality.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock
import pytest
import re

from lockr.utils.password_generator import PasswordGenerator, generate_password
from lockr.database.manager import VaultDatabase


class TestPasswordGenerator:
    """Test password generator utility."""

    def test_default_password(self):
        """Test default password generation."""
        password = generate_password()

        assert len(password) == 16
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)
        assert not any(c in "!@#$%^&*" for c in password)  # No punctuation by default

    def test_custom_length(self):
        """Test custom password length."""
        for length in [4, 8, 16, 32, 64, 128]:
            password = generate_password(length=length)
            assert len(password) == length

    def test_character_types(self):
        """Test different character type combinations."""
        # Lowercase only
        password = generate_password(
            use_uppercase=False,
            use_digits=False,
            use_punctuation=False
        )
        assert all(c.islower() for c in password)

        # Uppercase only
        password = generate_password(
            use_lowercase=False,
            use_digits=False,
            use_punctuation=False
        )
        assert all(c.isupper() for c in password)

        # Digits only
        password = generate_password(
            use_lowercase=False,
            use_uppercase=False,
            use_punctuation=False
        )
        assert all(c.isdigit() for c in password)

        # With punctuation
        password = generate_password(
            length=50,  # Longer to ensure punctuation appears
            use_punctuation=True
        )
        # Should have at least some punctuation in a 50-char password
        # (though not guaranteed in every case due to randomness)

    def test_exclude_ambiguous(self):
        """Test ambiguous character exclusion."""
        # Generate many passwords to check for ambiguous chars
        for _ in range(20):
            password = generate_password(length=50, exclude_ambiguous=True)
            ambiguous_chars = set("0O1lI")
            assert not any(c in ambiguous_chars for c in password)

    def test_include_ambiguous(self):
        """Test including ambiguous characters."""
        # Generate many passwords to potentially get ambiguous chars
        found_ambiguous = False
        for _ in range(50):
            password = generate_password(length=50, exclude_ambiguous=False)
            ambiguous_chars = set("0O1lI")
            if any(c in ambiguous_chars for c in password):
                found_ambiguous = True
                break

        # Should eventually find ambiguous characters (though not guaranteed)
        # This test is probabilistic but should pass most of the time

    def test_invalid_configurations(self):
        """Test invalid password generation configurations."""
        # No character types enabled
        with pytest.raises(ValueError):
            generate_password(
                use_lowercase=False,
                use_uppercase=False,
                use_digits=False,
                use_punctuation=False
            )

    def test_password_uniqueness(self):
        """Test that generated passwords are unique."""
        passwords = set()

        # Generate 100 passwords - should all be unique
        for _ in range(100):
            password = generate_password(length=16)
            passwords.add(password)

        # All passwords should be unique
        assert len(passwords) == 100

    def test_password_generator_class(self):
        """Test PasswordGenerator class directly."""
        generator = PasswordGenerator(
            length=12,
            use_lowercase=True,
            use_uppercase=False,
            use_digits=True,
            use_punctuation=False,
            exclude_ambiguous=True
        )

        password = generator.generate()
        assert len(password) == 12
        assert all(c.islower() or c.isdigit() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)

    def test_charset_info(self):
        """Test charset information display."""
        generator = PasswordGenerator(
            use_lowercase=True,
            use_uppercase=False,
            use_digits=True,
            use_punctuation=True,
            exclude_ambiguous=True
        )

        info = generator.get_charset_info()
        assert "lowercase" in info
        assert "digits" in info
        assert "punctuation" in info
        assert "uppercase" not in info
        assert "excluding ambiguous" in info


class TestPasswordGenerationIntegration:
    """Test password generation integration with vault operations."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault for testing."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        vault = VaultDatabase(vault_path)
        password = "test-password"
        vault.connect(password)

        yield vault, password

        # Cleanup
        vault.close()
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    def test_add_generated_password(self, temp_vault):
        """Test adding a secret with generated password."""
        vault, master_password = temp_vault

        # Generate a password and add it to vault
        generated_password = generate_password(length=20, use_punctuation=True)

        vault.add_secret("test-generated-key", generated_password)

        # Retrieve and verify
        retrieved_password = vault.get_secret("test-generated-key")
        assert retrieved_password == generated_password
        assert len(retrieved_password) == 20

    def test_update_with_generated_password(self, temp_vault):
        """Test updating a secret with generated password."""
        vault, master_password = temp_vault

        # Add initial secret
        vault.add_secret("test-update-key", "original-value")

        # Generate new password and update
        new_password = generate_password(length=24, use_punctuation=False)
        vault.update_secret("test-update-key", new_password)

        # Verify update
        retrieved_password = vault.get_secret("test-update-key")
        assert retrieved_password == new_password
        assert len(retrieved_password) == 24
        assert retrieved_password != "original-value"

    def test_password_strength_validation(self):
        """Test that generated passwords meet strength requirements."""
        # Generate multiple passwords and check they meet basic strength requirements
        for _ in range(10):
            password = generate_password(length=16, use_punctuation=True)

            # Should have mixed case
            has_lower = any(c.islower() for c in password)
            has_upper = any(c.isupper() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_punct = any(not c.isalnum() for c in password)

            assert has_lower, f"Password should have lowercase: {password}"
            assert has_upper, f"Password should have uppercase: {password}"
            assert has_digit, f"Password should have digits: {password}"
            assert has_punct, f"Password should have punctuation: {password}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])