"""
Unit tests for session management functionality.
"""

import tempfile
import os
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

from lockr.session.manager import SessionManager
from lockr.database.manager import VaultDatabase


class TestSessionManager:
    """Test session manager functionality."""

    @pytest.fixture
    def session_manager(self):
        """Create a session manager for testing."""
        return SessionManager(enabled=True)

    @pytest.fixture
    def temp_vault_path(self):
        """Create a temporary vault path for testing."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        yield vault_path

        # Cleanup
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    def test_session_manager_initialization(self):
        """Test session manager initialization."""
        # Test enabled initialization
        sm = SessionManager(enabled=True)
        assert isinstance(sm, SessionManager)

        # Test disabled initialization
        sm_disabled = SessionManager(enabled=False)
        assert sm_disabled.enabled is False

    def test_session_support_check(self, session_manager):
        """Test session support detection."""
        is_supported = session_manager.is_supported()
        assert isinstance(is_supported, bool)

    def test_session_username_generation(self, session_manager, temp_vault_path):
        """Test session username generation."""
        username = session_manager._get_session_username(temp_vault_path)

        assert isinstance(username, str)
        assert username.startswith("session:")
        assert temp_vault_path in username or str(os.path.abspath(temp_vault_path)) in username

    def test_session_username_consistency(self, session_manager, temp_vault_path):
        """Test that session username generation is consistent."""
        username1 = session_manager._get_session_username(temp_vault_path)
        username2 = session_manager._get_session_username(temp_vault_path)

        assert username1 == username2

    def test_session_token_creation_and_parsing(self, session_manager, temp_vault_path):
        """Test session token creation and parsing."""
        password = "test-password"

        # Create token
        token = session_manager._create_session_token(password, temp_vault_path)
        assert isinstance(token, str)
        assert len(token) > 0

        # Parse token
        session_data = session_manager._parse_session_token(token)
        assert session_data is not None
        assert session_data["password"] == password
        assert session_data["vault_path"] == temp_vault_path
        assert "created_at" in session_data
        assert "token" in session_data

    def test_session_token_parsing_invalid(self, session_manager):
        """Test session token parsing with invalid tokens."""
        # Invalid base64
        result = session_manager._parse_session_token("invalid-token")
        assert result is None

        # Valid base64 but invalid JSON
        import base64
        invalid_json = base64.b64encode(b"not-json").decode()
        result = session_manager._parse_session_token(invalid_json)
        assert result is None

        # Valid JSON but missing fields
        import json
        incomplete_data = {"password": "test"}
        incomplete_json = json.dumps(incomplete_data)
        incomplete_token = base64.b64encode(incomplete_json.encode()).decode()
        result = session_manager._parse_session_token(incomplete_token)
        assert result is None

    def test_session_validation_timing(self, session_manager, temp_vault_path):
        """Test session validation and expiration."""
        password = "test-password"

        # Create fresh session token
        token = session_manager._create_session_token(password, temp_vault_path)
        session_data = session_manager._parse_session_token(token)

        # Should be valid immediately
        assert session_manager._is_session_valid(session_data) is True

        # Modify created_at to simulate expired session
        session_data["created_at"] = time.time() - (session_manager.SESSION_DURATION + 100)
        assert session_manager._is_session_valid(session_data) is False

    def test_session_validation_invalid_data(self, session_manager):
        """Test session validation with invalid data."""
        # Missing created_at
        invalid_data = {"password": "test", "vault_path": "/test", "token": "abc"}
        assert session_manager._is_session_valid(invalid_data) is False

        # Invalid created_at type
        invalid_data["created_at"] = "not-a-number"
        assert session_manager._is_session_valid(invalid_data) is False

    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_session_creation_success(self, mock_get, mock_set, session_manager, temp_vault_path):
        """Test successful session creation."""
        password = "test-password"

        # Mock keyring success
        mock_set.return_value = None  # set_password returns None on success

        result = session_manager.create_session(temp_vault_path, password)
        assert result is True

        # Verify keyring was called
        mock_set.assert_called_once()
        args = mock_set.call_args[0]
        assert args[0] == session_manager.SERVICE_NAME
        assert args[1].startswith("session:")

    @patch('keyring.set_password')
    def test_session_creation_keyring_error(self, mock_set, session_manager, temp_vault_path):
        """Test session creation with keyring error."""
        from keyring.errors import KeyringError

        password = "test-password"
        mock_set.side_effect = KeyringError("Keyring error")

        result = session_manager.create_session(temp_vault_path, password)
        assert result is False

    def test_session_creation_disabled(self, temp_vault_path):
        """Test session creation when disabled."""
        session_manager = SessionManager(enabled=False)
        result = session_manager.create_session(temp_vault_path, "password")
        assert result is False

    @patch('keyring.get_password')
    def test_session_password_retrieval_no_session(self, mock_get, session_manager, temp_vault_path):
        """Test password retrieval when no session exists."""
        mock_get.return_value = None

        password = session_manager.get_session_password(temp_vault_path)
        assert password is None

    @patch('keyring.get_password')
    @patch('keyring.delete_password')
    def test_session_password_retrieval_expired(self, mock_delete, mock_get, session_manager, temp_vault_path):
        """Test password retrieval with expired session."""
        # Create expired token
        password = "test-password"
        token = session_manager._create_session_token(password, temp_vault_path)
        session_data = session_manager._parse_session_token(token)
        session_data["created_at"] = time.time() - (session_manager.SESSION_DURATION + 100)

        # Re-encode the modified token
        import json, base64
        expired_token = base64.b64encode(json.dumps(session_data).encode()).decode()
        mock_get.return_value = expired_token

        result_password = session_manager.get_session_password(temp_vault_path)
        assert result_password is None

        # Should have called delete to clean up expired session
        mock_delete.assert_called_once()

    @patch('keyring.get_password')
    def test_session_password_retrieval_success(self, mock_get, session_manager, temp_vault_path):
        """Test successful password retrieval from session."""
        password = "test-password"
        token = session_manager._create_session_token(password, temp_vault_path)
        mock_get.return_value = token

        retrieved_password = session_manager.get_session_password(temp_vault_path)
        assert retrieved_password == password

    def test_session_password_retrieval_disabled(self, temp_vault_path):
        """Test password retrieval when sessions disabled."""
        session_manager = SessionManager(enabled=False)
        password = session_manager.get_session_password(temp_vault_path)
        assert password is None

    @patch('keyring.delete_password')
    def test_session_clearing(self, mock_delete, session_manager, temp_vault_path):
        """Test session clearing."""
        mock_delete.return_value = None

        result = session_manager.clear_session(temp_vault_path)
        assert result is True

        mock_delete.assert_called_once()

    @patch('keyring.delete_password')
    def test_session_clearing_keyring_error(self, mock_delete, session_manager, temp_vault_path):
        """Test session clearing with keyring error."""
        from keyring.errors import KeyringError
        mock_delete.side_effect = KeyringError("Delete failed")

        result = session_manager.clear_session(temp_vault_path)
        assert result is False

    def test_session_clearing_disabled(self, temp_vault_path):
        """Test session clearing when disabled."""
        session_manager = SessionManager(enabled=False)
        result = session_manager.clear_session(temp_vault_path)
        assert result is False

    @patch('keyring.get_password')
    def test_has_active_session(self, mock_get, session_manager, temp_vault_path):
        """Test checking for active session."""
        password = "test-password"

        # No session
        mock_get.return_value = None
        assert session_manager.has_active_session(temp_vault_path) is False

        # Valid session
        token = session_manager._create_session_token(password, temp_vault_path)
        mock_get.return_value = token
        assert session_manager.has_active_session(temp_vault_path) is True

    @patch('keyring.get_password')
    def test_session_info(self, mock_get, session_manager, temp_vault_path):
        """Test getting session information."""
        password = "test-password"

        # No session
        mock_get.return_value = None
        info = session_manager.get_session_info(temp_vault_path)
        assert info is None

        # Valid session
        token = session_manager._create_session_token(password, temp_vault_path)
        mock_get.return_value = token

        info = session_manager.get_session_info(temp_vault_path)
        assert info is not None
        assert "created_at" in info
        assert "age_seconds" in info
        assert "remaining_seconds" in info
        assert "vault_path" in info
        assert isinstance(info["age_seconds"], int)
        assert isinstance(info["remaining_seconds"], int)

    def test_session_info_disabled(self, temp_vault_path):
        """Test session info when disabled."""
        session_manager = SessionManager(enabled=False)
        info = session_manager.get_session_info(temp_vault_path)
        assert info is None

    def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired sessions."""
        # This is a no-op due to keyring API limitations
        result = session_manager.cleanup_expired_sessions()
        assert isinstance(result, int)


class TestSessionIntegration:
    """Test session integration with vault operations."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault for testing."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        vault = VaultDatabase(vault_path)
        password = "test-password-123"
        vault.connect(password)

        yield vault, password

        # Cleanup
        vault.close()
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_session_workflow_integration(self, mock_get, mock_set, temp_vault):
        """Test complete session workflow integration."""
        vault, password = temp_vault
        vault_path = str(vault.db_path)

        session_manager = SessionManager(enabled=True)

        # 1. Create session
        mock_set.return_value = None
        result = session_manager.create_session(vault_path, password)
        assert result is True

        # 2. Retrieve password from session
        token = session_manager._create_session_token(password, vault_path)
        mock_get.return_value = token

        retrieved_password = session_manager.get_session_password(vault_path)
        assert retrieved_password == password

        # 3. Verify session is active
        assert session_manager.has_active_session(vault_path) is True

        # 4. Get session info
        info = session_manager.get_session_info(vault_path)
        assert info is not None
        assert info["remaining_seconds"] > 0

    def test_session_expiry_workflow(self, temp_vault):
        """Test session expiry workflow."""
        vault, password = temp_vault
        vault_path = str(vault.db_path)

        session_manager = SessionManager(enabled=True)

        # Temporarily reduce session duration for testing
        original_duration = session_manager.SESSION_DURATION
        session_manager.SESSION_DURATION = 1  # 1 second

        try:
            with patch('keyring.set_password'), \
                 patch('keyring.get_password') as mock_get, \
                 patch('keyring.delete_password') as mock_delete:

                # Create session
                result = session_manager.create_session(vault_path, password)
                assert result is True

                # Wait for expiry
                time.sleep(1.1)

                # Set up expired token
                token = session_manager._create_session_token(password, vault_path)
                session_data = session_manager._parse_session_token(token)
                session_data["created_at"] = time.time() - 2  # 2 seconds ago

                import json, base64
                expired_token = base64.b64encode(json.dumps(session_data).encode()).decode()
                mock_get.return_value = expired_token

                # Try to get password - should be None due to expiry
                retrieved_password = session_manager.get_session_password(vault_path)
                assert retrieved_password is None

                # Should have cleaned up expired session
                mock_delete.assert_called_once()

        finally:
            # Restore original duration
            session_manager.SESSION_DURATION = original_duration

    @patch('keyring.set_password')
    @patch('keyring.get_password')
    @patch('keyring.delete_password')
    def test_session_clearing_workflow(self, mock_delete, mock_get, mock_set, temp_vault):
        """Test session clearing workflow."""
        vault, password = temp_vault
        vault_path = str(vault.db_path)

        session_manager = SessionManager(enabled=True)

        # Create session
        mock_set.return_value = None
        result = session_manager.create_session(vault_path, password)
        assert result is True

        # Verify session exists
        token = session_manager._create_session_token(password, vault_path)
        mock_get.return_value = token
        assert session_manager.has_active_session(vault_path) is True

        # Clear session
        mock_delete.return_value = None
        result = session_manager.clear_session(vault_path)
        assert result is True

        # Verify session is cleared
        mock_get.return_value = None
        assert session_manager.has_active_session(vault_path) is False


class TestSessionManagerFactory:
    """Test session manager factory function."""

    def test_get_session_manager_enabled(self):
        """Test getting session manager with enabled=True."""
        from lockr.session.manager import get_session_manager

        sm = get_session_manager(enabled=True)
        assert isinstance(sm, SessionManager)

    def test_get_session_manager_disabled(self):
        """Test getting session manager with enabled=False."""
        from lockr.session.manager import get_session_manager

        sm = get_session_manager(enabled=False)
        assert isinstance(sm, SessionManager)
        assert sm.enabled is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])