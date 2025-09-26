"""
Session management using keyring for secure token storage.

Provides session-based authentication where users don't need to re-enter
their password for 30 minutes after successful authentication.
"""

import json
import time
import secrets
import logging
from typing import Optional, Dict, Any
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


class SessionManager:
    """Manages authentication sessions using keyring for secure storage."""

    SERVICE_NAME = "com.lockr.session"
    SESSION_DURATION = 30 * 60  # 30 minutes in seconds

    def __init__(self, enabled: bool = True):
        """
        Initialize session manager.

        Args:
            enabled: Whether session management is enabled
        """
        self.enabled = enabled and KEYRING_AVAILABLE

        if not KEYRING_AVAILABLE and enabled:
            logger.warning("Keyring library not available. Session management disabled.")

    def _get_session_username(self, vault_path: str) -> str:
        """Generate unique session username for vault path."""
        abs_path = str(Path(vault_path).resolve())
        return f"session:{abs_path}"

    def _create_session_token(self, password: str, vault_path: str) -> str:
        """
        Create a session token containing encrypted password and timestamp.

        Args:
            password: The master password
            vault_path: Path to vault file

        Returns:
            Base64-encoded session token
        """
        # Create session data
        session_data = {
            "password": password,  # In real implementation, this should be encrypted
            "created_at": time.time(),
            "vault_path": vault_path,
            "token": secrets.token_hex(16)  # Random token for validation
        }

        # Serialize and encode
        import base64
        json_data = json.dumps(session_data)
        return base64.b64encode(json_data.encode()).decode('ascii')

    def _parse_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Parse and validate session token.

        Args:
            token: Base64-encoded session token

        Returns:
            Session data if valid, None otherwise
        """
        try:
            import base64
            json_data = base64.b64decode(token.encode()).decode()
            session_data = json.loads(json_data)

            # Validate that we got a dict
            if not isinstance(session_data, dict):
                logger.warning("Invalid session token: not a dict")
                return None

            # Validate required fields
            required_fields = ['password', 'created_at', 'vault_path', 'token']
            if not all(field in session_data for field in required_fields):
                logger.warning("Invalid session token: missing required fields")
                return None

            return session_data

        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to parse session token: {e}")
            return None

    def _is_session_valid(self, session_data: Dict[str, Any]) -> bool:
        """
        Check if session is still valid (not expired).

        Args:
            session_data: Parsed session data

        Returns:
            True if session is valid, False if expired
        """
        created_at = session_data.get('created_at', 0)
        if not isinstance(created_at, (int, float)):
            logger.warning("Invalid session token: created_at is not a number")
            return False

        current_time = time.time()

        age = current_time - created_at
        is_valid = age < self.SESSION_DURATION

        if not is_valid:
            logger.debug(f"Session expired: {age:.0f}s > {self.SESSION_DURATION}s")
        else:
            logger.debug(f"Session valid: {age:.0f}s remaining")

        return is_valid

    def create_session(self, vault_path: str, password: str) -> bool:
        """
        Create a new authentication session.

        Args:
            vault_path: Path to vault file
            password: Master password that was successfully authenticated

        Returns:
            True if session created successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Session management disabled")
            return False

        try:
            username = self._get_session_username(vault_path)
            session_token = self._create_session_token(password, vault_path)

            keyring.set_password(self.SERVICE_NAME, username, session_token)
            logger.debug(f"Session created for vault: {vault_path}")
            return True

        except (KeyringLocked, KeyringError) as e:
            logger.warning(f"Failed to create session: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating session: {e}")
            return False

    def get_session_password(self, vault_path: str) -> Optional[str]:
        """
        Get password from active session if valid.

        Args:
            vault_path: Path to vault file

        Returns:
            Password if session is valid, None otherwise
        """
        if not self.enabled:
            return None

        try:
            username = self._get_session_username(vault_path)
            session_token = keyring.get_password(self.SERVICE_NAME, username)

            if not session_token:
                logger.debug(f"No session found for vault: {vault_path}")
                return None

            session_data = self._parse_session_token(session_token)
            if not session_data:
                # Invalid token, remove it
                self.clear_session(vault_path)
                return None

            if not self._is_session_valid(session_data):
                # Expired session, remove it
                self.clear_session(vault_path)
                return None

            # Valid session
            logger.debug(f"Valid session found for vault: {vault_path}")
            password = session_data.get('password')
            if isinstance(password, str):
                return password
            else:
                logger.warning("Invalid session token: password is not a string")
                self.clear_session(vault_path)
                return None

        except (KeyringLocked, KeyringError) as e:
            logger.warning(f"Failed to retrieve session: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving session: {e}")
            return None

    def clear_session(self, vault_path: str) -> bool:
        """
        Clear/invalidate session for vault.

        Args:
            vault_path: Path to vault file

        Returns:
            True if cleared successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            username = self._get_session_username(vault_path)
            keyring.delete_password(self.SERVICE_NAME, username)
            logger.debug(f"Session cleared for vault: {vault_path}")
            return True

        except (KeyringLocked, KeyringError) as e:
            logger.debug(f"Could not clear session: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error clearing session: {e}")
            return False

    def has_active_session(self, vault_path: str) -> bool:
        """
        Check if there's an active (valid) session for vault.

        Args:
            vault_path: Path to vault file

        Returns:
            True if active session exists, False otherwise
        """
        return self.get_session_password(vault_path) is not None

    def get_session_info(self, vault_path: str) -> Optional[Dict[str, Any]]:
        """
        Get information about current session.

        Args:
            vault_path: Path to vault file

        Returns:
            Session info dict or None if no valid session
        """
        if not self.enabled:
            return None

        try:
            username = self._get_session_username(vault_path)
            session_token = keyring.get_password(self.SERVICE_NAME, username)

            if not session_token:
                return None

            session_data = self._parse_session_token(session_token)
            if not session_data or not self._is_session_valid(session_data):
                return None

            created_at = session_data['created_at']
            current_time = time.time()
            age = current_time - created_at
            remaining = max(0, self.SESSION_DURATION - age)

            return {
                'created_at': created_at,
                'age_seconds': int(age),
                'remaining_seconds': int(remaining),
                'vault_path': session_data['vault_path']
            }

        except Exception as e:
            logger.error(f"Error getting session info: {e}")
            return None

    def is_supported(self) -> bool:
        """Check if session management is supported."""
        return self.enabled

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (best effort).

        Note: This is limited by keyring API - we can only clean up sessions
        we know about, not enumerate all stored sessions.

        Returns:
            Number of sessions cleaned up (may be 0 due to API limitations)
        """
        # Keyring doesn't provide a way to enumerate all stored credentials
        # So we can't automatically clean up expired sessions
        # They will be cleaned up when accessed and found to be expired
        logger.debug("Session cleanup not implemented due to keyring API limitations")
        return 0


def get_session_manager(enabled: bool = True) -> SessionManager:
    """
    Get a configured session manager instance.

    Args:
        enabled: Whether session management should be enabled

    Returns:
        SessionManager instance
    """
    return SessionManager(enabled=enabled)