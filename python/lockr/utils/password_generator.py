"""
Secure password generation utilities.
"""

import secrets
import string
from typing import Set


class PasswordGenerator:
    """Generate secure passwords with customizable character sets."""

    # Character sets
    LOWERCASE = set(string.ascii_lowercase)
    UPPERCASE = set(string.ascii_uppercase)
    DIGITS = set(string.digits)
    PUNCTUATION = set(string.punctuation)

    # Common confusing characters to optionally exclude
    AMBIGUOUS_CHARS = set("0O1lI")

    def __init__(self,
                 length: int = 16,
                 use_lowercase: bool = True,
                 use_uppercase: bool = True,
                 use_digits: bool = True,
                 use_punctuation: bool = False,
                 exclude_ambiguous: bool = True):
        """
        Initialize password generator with options.

        Args:
            length: Password length (minimum 4, maximum 128)
            use_lowercase: Include lowercase letters
            use_uppercase: Include uppercase letters
            use_digits: Include digits
            use_punctuation: Include punctuation characters
            exclude_ambiguous: Exclude visually ambiguous characters (0, O, 1, l, I)
        """
        self.length = max(4, min(length, 128))
        self.use_lowercase = use_lowercase
        self.use_uppercase = use_uppercase
        self.use_digits = use_digits
        self.use_punctuation = use_punctuation
        self.exclude_ambiguous = exclude_ambiguous

        # Build character set
        self.charset = self._build_charset()

        if not self.charset:
            raise ValueError("At least one character type must be enabled")

    def _build_charset(self) -> str:
        """Build the character set based on options."""
        chars: Set[str] = set()

        if self.use_lowercase:
            chars.update(self.LOWERCASE)

        if self.use_uppercase:
            chars.update(self.UPPERCASE)

        if self.use_digits:
            chars.update(self.DIGITS)

        if self.use_punctuation:
            chars.update(self.PUNCTUATION)

        # Remove ambiguous characters if requested
        if self.exclude_ambiguous:
            chars -= self.AMBIGUOUS_CHARS

        return ''.join(sorted(chars))

    def generate(self) -> str:
        """
        Generate a secure password.

        Returns:
            Generated password string
        """
        if not self.charset:
            raise ValueError("No characters available for password generation")

        # Generate password using cryptographically secure random
        password = ''.join(secrets.choice(self.charset) for _ in range(self.length))

        # Ensure password meets minimum requirements
        if not self._meets_requirements(password):
            # Regenerate if requirements not met (rare case)
            return self.generate()

        return password

    def _meets_requirements(self, password: str) -> bool:
        """
        Check if password meets the specified character type requirements.

        Args:
            password: Password to check

        Returns:
            True if password meets all enabled requirements
        """
        password_chars = set(password)

        if self.use_lowercase and not (password_chars & self.LOWERCASE):
            return False

        if self.use_uppercase and not (password_chars & self.UPPERCASE):
            return False

        if self.use_digits and not (password_chars & self.DIGITS):
            return False

        if self.use_punctuation and not (password_chars & self.PUNCTUATION):
            return False

        return True

    def get_charset_info(self) -> str:
        """
        Get human-readable description of character set.

        Returns:
            Description of enabled character types
        """
        parts = []

        if self.use_lowercase:
            parts.append("lowercase")
        if self.use_uppercase:
            parts.append("uppercase")
        if self.use_digits:
            parts.append("digits")
        if self.use_punctuation:
            parts.append("punctuation")

        info = ", ".join(parts)

        if self.exclude_ambiguous:
            info += " (excluding ambiguous chars)"

        return info


def generate_password(length: int = 16,
                     use_lowercase: bool = True,
                     use_uppercase: bool = True,
                     use_digits: bool = True,
                     use_punctuation: bool = False,
                     exclude_ambiguous: bool = True) -> str:
    """
    Convenience function to generate a password.

    Args:
        length: Password length (4-128)
        use_lowercase: Include lowercase letters
        use_uppercase: Include uppercase letters
        use_digits: Include digits
        use_punctuation: Include punctuation characters
        exclude_ambiguous: Exclude visually ambiguous characters

    Returns:
        Generated password string
    """
    generator = PasswordGenerator(
        length=length,
        use_lowercase=use_lowercase,
        use_uppercase=use_uppercase,
        use_digits=use_digits,
        use_punctuation=use_punctuation,
        exclude_ambiguous=exclude_ambiguous
    )

    return generator.generate()