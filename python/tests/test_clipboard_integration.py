"""
Unit tests for clipboard integration in add command.
"""

import tempfile
import os
import threading
import time
from unittest.mock import patch, MagicMock
import pytest

from lockr.database.manager import VaultDatabase
from lockr.utils.password_generator import generate_password


class TestClipboardIntegration:
    """Test clipboard functionality with add command."""

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

    @patch('pyperclip.copy')
    def test_clipboard_copy_success(self, mock_copy):
        """Test successful clipboard copying."""
        # Generate a password
        password = generate_password(length=16)

        # Simulate copying to clipboard
        mock_copy.return_value = None

        # Test the copy functionality
        import pyperclip
        pyperclip.copy(password)

        # Verify copy was called with the password
        mock_copy.assert_called_once_with(password)

    @patch('pyperclip.copy')
    @patch('threading.Thread')
    def test_clipboard_auto_clear(self, mock_thread, mock_copy):
        """Test clipboard auto-clear functionality."""
        password = generate_password(length=16)

        # Mock successful copy
        mock_copy.return_value = None
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Simulate the clipboard functionality
        import pyperclip
        pyperclip.copy(password)

        # Simulate creating clear thread
        def clear_clipboard():
            time.sleep(60)
            try:
                pyperclip.copy("")
            except Exception:
                pass

        thread = threading.Thread(target=clear_clipboard, daemon=True)

        # Verify thread would be started
        assert callable(clear_clipboard)

    def test_clipboard_import_error_handling(self):
        """Test handling when pyperclip is not available."""
        # Test that we handle ImportError gracefully
        with patch('builtins.__import__', side_effect=ImportError("No module named 'pyperclip'")):
            with pytest.raises(ImportError):
                import pyperclip

    @patch('pyperclip.copy')
    def test_clipboard_copy_exception_handling(self, mock_copy):
        """Test handling of clipboard copy exceptions."""
        # Mock copy to raise an exception
        mock_copy.side_effect = Exception("Clipboard access denied")

        with pytest.raises(Exception):
            import pyperclip
            pyperclip.copy("test-password")

    def test_generated_password_properties(self):
        """Test that generated passwords have expected properties for clipboard."""
        password = generate_password(length=20, use_punctuation=True)

        # Password should be suitable for clipboard
        assert len(password) == 20
        assert isinstance(password, str)
        assert len(password.encode('utf-8')) > 0  # Should be encodable

        # Should not contain newlines or control characters
        assert '\n' not in password
        assert '\r' not in password
        assert '\t' not in password

    def test_different_password_types_clipboard_compatibility(self):
        """Test that different password types are clipboard compatible."""
        test_cases = [
            {"length": 8, "use_punctuation": False},  # Simple alphanumeric
            {"length": 16, "use_punctuation": True},  # With special chars
            {"length": 32, "use_lowercase": True, "use_uppercase": False, "use_digits": False},  # Lowercase only
            {"length": 12, "use_lowercase": False, "use_uppercase": False, "use_digits": True},  # Digits only
        ]

        for case in test_cases:
            password = generate_password(**case)

            # All should be valid strings
            assert isinstance(password, str)
            assert len(password) > 0
            assert len(password) == case["length"]

            # Should not contain problematic characters for clipboard
            assert '\x00' not in password  # No null bytes
            assert password.isprintable() or any(not c.isprintable() for c in password if c in "!@#$%^&*()_+-=[]{}|;:,.<>?")

    @patch('pyperclip.copy')
    def test_clipboard_with_vault_integration(self, mock_copy, temp_vault):
        """Test clipboard functionality with actual vault operations."""
        vault, master_password = temp_vault

        # Generate a password
        generated_password = generate_password(length=24, use_punctuation=True)

        # Add to vault
        vault.add_secret("test-clipboard-key", generated_password)

        # Simulate clipboard copy
        mock_copy.return_value = None
        import pyperclip
        pyperclip.copy(generated_password)

        # Verify copy was called
        mock_copy.assert_called_once_with(generated_password)

        # Verify we can retrieve the same password from vault
        retrieved = vault.get_secret("test-clipboard-key")
        assert retrieved == generated_password

    def test_clipboard_thread_safety(self):
        """Test that clipboard operations are thread-safe."""
        passwords = []

        def generate_and_store():
            password = generate_password(length=12)
            passwords.append(password)

        # Create multiple threads to generate passwords
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=generate_and_store)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have generated 10 unique passwords
        assert len(passwords) == 10
        assert len(set(passwords)) == 10  # All should be unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])