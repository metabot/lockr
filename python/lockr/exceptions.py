"""
Custom exceptions for Lockr.
"""


class LockrException(Exception):
    """Base exception for Lockr."""

    pass


class AuthenticationError(LockrException):
    """Authentication failed."""

    pass


class VaultNotFoundError(LockrException):
    """Vault file not found."""

    pass


class InvalidKeyError(LockrException):
    """Invalid key format."""

    pass


class SessionExpiredError(LockrException):
    """Session has expired."""

    pass


class DuplicateKeyError(LockrException):
    """Key already exists in vault."""

    pass


class KeyNotFoundError(LockrException):
    """Key does not exist in vault."""

    pass


class DatabaseError(LockrException):
    """Database operation failed."""

    pass
