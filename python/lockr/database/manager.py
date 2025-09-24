"""
Database manager for Lockr vault using SQLCipher.
"""

import getpass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import sqlcipher3 as sqlcipher

from ..exceptions import (
    AuthenticationError,
    DuplicateKeyError,
    KeyNotFoundError,
    DatabaseError,
)
from ..utils.validation import validate_key


class VaultDatabase:
    """Database manager for encrypted vault storage."""

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to the SQLCipher database file
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlcipher.Connection] = None

    def connect(self, password: str) -> bool:
        """
        Connect to encrypted database with password.

        Args:
            password: Master password for vault

        Returns:
            True if connection successful, False otherwise

        Raises:
            AuthenticationError: If password is incorrect
            DatabaseError: If database operation fails
        """
        try:
            # Connect to SQLCipher database
            self.connection = sqlcipher.connect(str(self.db_path))

            # Set encryption key
            self.connection.execute(f"PRAGMA key = '{password}'")

            # Test connection by querying schema
            cursor = self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
            )
            cursor.fetchone()

            # Initialize tables if this is a new vault
            self._initialize_tables()

            # Log successful authentication
            self._log_auth_attempt(success=True)

            return True

        except sqlcipher.DatabaseError as e:
            # Log failed authentication attempt
            if self.connection:
                try:
                    self._log_auth_attempt(success=False)
                except:
                    pass  # Don't fail if logging fails
                self.connection.close()
                self.connection = None

            raise AuthenticationError("Invalid password or corrupted vault file") from e

    def _initialize_tables(self) -> None:
        """Create tables if they don't exist."""
        if not self.connection:
            raise DatabaseError("Not connected to database")

        # Read schema from shared schema file
        schema_path = (
            Path(__file__).parent.parent.parent.parent / "schema" / "vault.sql"
        )

        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()

            # Execute schema creation
            self.connection.executescript(schema_sql)
            self.connection.commit()

        except FileNotFoundError:
            # Fallback to embedded schema
            self._create_tables_fallback()

    def _create_tables_fallback(self) -> None:
        """Fallback table creation if schema file not found."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL COLLATE NOCASE,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS auth_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            username TEXT NOT NULL,
            success BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_secrets_key ON secrets(key COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_auth_timestamp ON auth_attempts(timestamp);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
        """

        self.connection.executescript(schema_sql)
        self.connection.commit()

    def add_secret(self, key: str, value: str) -> None:
        """
        Add a new secret to the vault.

        Args:
            key: Secret key
            value: Secret value

        Raises:
            DuplicateKeyError: If key already exists
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        if not validate_key(key):
            raise ValueError(f"Invalid key format: {key}")

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO secrets (key, value, created_at, last_accessed)
                VALUES (?, ?, datetime('now'), datetime('now'))
                """,
                (key, value),
            )
            self.connection.commit()

        except sqlcipher.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise DuplicateKeyError(f"Key '{key}' already exists")
            raise DatabaseError(f"Database error: {e}") from e

    def get_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a secret by exact key match.

        Args:
            key: Secret key

        Returns:
            Secret value or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        try:
            cursor = self.connection.execute(
                "SELECT value FROM secrets WHERE key = ? COLLATE NOCASE", (key,)
            )
            result = cursor.fetchone()

            if result:
                # Update last accessed time
                self._update_last_accessed(key)
                return result[0]

            return None

        except sqlcipher.Error as e:
            raise DatabaseError(f"Database error: {e}") from e

    def update_secret(self, key: str, value: str) -> None:
        """
        Update an existing secret.

        Args:
            key: Secret key
            value: New secret value

        Raises:
            KeyNotFoundError: If key doesn't exist
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        try:
            cursor = self.connection.execute(
                """
                UPDATE secrets
                SET value = ?, last_accessed = datetime('now')
                WHERE key = ? COLLATE NOCASE
                """,
                (value, key),
            )

            if cursor.rowcount == 0:
                raise KeyNotFoundError(f"Key '{key}' does not exist")

            self.connection.commit()

        except sqlcipher.Error as e:
            raise DatabaseError(f"Database error: {e}") from e

    def delete_secret(self, key: str) -> None:
        """
        Delete a secret from the vault.

        Args:
            key: Secret key

        Raises:
            KeyNotFoundError: If key doesn't exist
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        try:
            cursor = self.connection.execute(
                "DELETE FROM secrets WHERE key = ? COLLATE NOCASE", (key,)
            )

            if cursor.rowcount == 0:
                raise KeyNotFoundError(f"Key '{key}' does not exist")

            self.connection.commit()

        except sqlcipher.Error as e:
            raise DatabaseError(f"Database error: {e}") from e

    def list_all_keys(self) -> List[str]:
        """
        List all keys in the vault.

        Returns:
            List of all secret keys sorted alphabetically

        Raises:
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        try:
            cursor = self.connection.execute(
                "SELECT key FROM secrets ORDER BY key COLLATE NOCASE"
            )
            return [row[0] for row in cursor.fetchall()]

        except sqlcipher.Error as e:
            raise DatabaseError(f"Database error: {e}") from e

    def search_keys(self, pattern: str) -> List[Tuple[str, float]]:
        """
        Search keys with fuzzy matching.

        Args:
            pattern: Search pattern

        Returns:
            List of (key, score) tuples sorted by relevance

        Raises:
            DatabaseError: If database operation fails
        """
        if not self.connection:
            raise DatabaseError("Not connected to database")

        try:
            # Get all keys first
            cursor = self.connection.execute("SELECT key FROM secrets ORDER BY key COLLATE NOCASE")
            all_keys = [row[0] for row in cursor.fetchall()]

            # Import fuzzy search here to avoid circular imports
            from ..search.fuzzy import fuzzy_search

            # Perform fuzzy search
            results = fuzzy_search(pattern, all_keys, limit=100, case_sensitive=False)

            # Convert to expected format (key, score)
            return [(result.text, result.score) for result in results]

        except sqlcipher.Error as e:
            raise DatabaseError(f"Database error: {e}") from e

    def get_vault_info(self) -> Dict[str, Any]:
        """
        Get vault file information.

        Returns:
            Dictionary with vault statistics and metadata
        """
        info = {
            "file_path": str(self.db_path.absolute()),
            "exists": self.db_path.exists(),
        }

        if self.db_path.exists():
            stat = self.db_path.stat()
            info.update(
                {
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        if self.connection:
            try:
                cursor = self.connection.execute("SELECT COUNT(*) FROM secrets")
                info["secret_count"] = cursor.fetchone()[0]

                cursor = self.connection.execute(
                    "SELECT COUNT(*) FROM auth_attempts WHERE success = 0"
                )
                info["failed_attempts"] = cursor.fetchone()[0]

            except sqlcipher.Error:
                pass  # Don't fail if we can't get stats

        return info

    def _update_last_accessed(self, key: str) -> None:
        """Update last accessed timestamp for a key."""
        try:
            self.connection.execute(
                """
                UPDATE secrets
                SET last_accessed = datetime('now'),
                    access_count = access_count + 1
                WHERE key = ? COLLATE NOCASE
                """,
                (key,),
            )
            self.connection.commit()
        except sqlcipher.Error:
            pass  # Don't fail if we can't update stats

    def _log_auth_attempt(self, success: bool) -> None:
        """Log authentication attempt."""
        try:
            username = getpass.getuser()
            self.connection.execute(
                """
                INSERT INTO auth_attempts (username, success, timestamp)
                VALUES (?, ?, datetime('now'))
                """,
                (username, success),
            )
            self.connection.commit()
        except (sqlcipher.Error, OSError):
            pass  # Don't fail if we can't log

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
