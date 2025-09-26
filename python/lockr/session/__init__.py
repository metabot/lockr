"""
Session management for Lockr.

Provides session-based authentication using keyring for secure storage.
"""

from .manager import SessionManager, get_session_manager

__all__ = ['SessionManager', 'get_session_manager']