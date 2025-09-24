"""
Input validation utilities for Lockr.
"""

import re
from typing import Optional

# Key validation pattern: alphanumeric + common punctuation
KEY_PATTERN = re.compile(r"^[a-zA-Z0-9._\-@#$%^&*()+=\[\]{}|;:,<>?/~]{1,256}$")


def validate_key(key: str) -> bool:
    """
    Validate key format according to Lockr specifications.

    Args:
        key: The key to validate

    Returns:
        True if key is valid, False otherwise
    """
    if not isinstance(key, str):
        return False

    return bool(KEY_PATTERN.match(key))


def sanitize_key(key: str) -> Optional[str]:
    """
    Sanitize and normalize a key.

    Args:
        key: The key to sanitize

    Returns:
        Sanitized key or None if invalid
    """
    if not isinstance(key, str):
        return None

    # Strip whitespace
    key = key.strip()

    # Check if valid after sanitization
    if validate_key(key):
        return key

    return None


def get_validation_error_message(key: str) -> str:
    """
    Get a descriptive error message for an invalid key.

    Args:
        key: The invalid key

    Returns:
        Error message describing why the key is invalid
    """
    if not isinstance(key, str):
        return "Key must be a string"

    if len(key) == 0:
        return "Key cannot be empty"

    if len(key) > 256:
        return "Key cannot be longer than 256 characters"

    # Check for invalid characters
    valid_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-@#$%^&*()+=[]{}|;:,<>?/~"
    )
    invalid_chars = set(key) - valid_chars

    if invalid_chars:
        return f"Key contains invalid characters: {', '.join(sorted(invalid_chars))}"

    return "Key format is invalid"
