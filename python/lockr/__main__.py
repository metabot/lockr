"""
CLI interface for Lockr personal vault.
"""

import sys
import getpass
import threading
import time
import click
from typing import Optional

from .database.manager import VaultDatabase
from .keychain import get_keychain_manager
from .session import get_session_manager
from .exceptions import (
    AuthenticationError,
    DuplicateKeyError,
    KeyNotFoundError,
    DatabaseError,
)
from .utils.validation import validate_key, get_validation_error_message
from .utils.password_generator import generate_password


class VaultContext:
    """Context object for sharing vault state across commands."""

    def __init__(self, vault_file: str, use_keychain: bool = True, use_sessions: bool = True):
        self.vault_file = vault_file
        self.db: Optional[VaultDatabase] = None
        self.authenticated = False
        self.keychain = get_keychain_manager(enabled=use_keychain)
        self.session = get_session_manager(enabled=use_sessions)

    def get_password_interactive(self, prompt: str = "Enter master password: ") -> str:
        """Securely get password from user."""
        return getpass.getpass(prompt)

    def authenticate(self) -> bool:
        """Authenticate user and connect to vault with session and keychain support."""
        if self.authenticated and self.db:
            return True

        password = None

        # First, try to use active session
        if self.session.is_supported():
            session_password = self.session.get_session_password(self.vault_file)
            if session_password:
                click.echo("🔄 Using active session...")
                password = session_password

        # If no active session, try keychain verification
        if not password and self.keychain.is_supported() and self.keychain.has_stored_password(self.vault_file):
            click.echo("🔐 Using stored keychain credentials...")

            # Get password from user and verify against keychain
            password = self.get_password_interactive("Enter master password: ")

            if self.keychain.verify_password(self.vault_file, password):
                click.echo("✅ Keychain verification successful")
            else:
                click.echo("❌ Keychain verification failed, removing stored key...")
                self.keychain.delete_password(self.vault_file)
                password = None

        # Fall back to interactive input if no session, keychain, or verification failed
        if not password:
            password = self.get_password_interactive("Enter master password: ")

        # Attempt to connect to database
        self.db = VaultDatabase(self.vault_file)
        try:
            self.db.connect(password)
            self.authenticated = True

            # Create new session for successful authentication
            if self.session.is_supported():
                session_created = self.session.create_session(self.vault_file, password)
                if session_created:
                    click.echo("✅ Session created (30 minutes)")

            # Offer to save in keychain if not already there
            self._maybe_save_to_keychain(password)
            return True

        except AuthenticationError as e:
            click.echo(f"Error: {e}", err=True)
            return False

    def ensure_authenticated(self) -> VaultDatabase:
        """Ensure user is authenticated, authenticate if not."""
        if not self.authenticate():
            sys.exit(1)
        assert self.db is not None, "Database should be set after successful authentication"
        return self.db

    def _maybe_save_to_keychain(self, password: str) -> None:
        """Offer to save password to keychain if not already saved."""
        if not self.keychain.is_supported():
            return

        # Check if already saved by verifying the password
        if self.keychain.has_stored_password(self.vault_file) and self.keychain.verify_password(self.vault_file, password):
            return  # Already saved and matches

        # Ask user to save
        platform_info = self.keychain.get_platform_info()
        if click.confirm(f"Save password to {platform_info}?", default=True):
            if self.keychain.store_password(self.vault_file, password):
                click.echo("✅ Password saved to keychain.")
            else:
                click.echo("❌ Failed to save password to keychain.", err=True)

    def clear_keychain(self) -> bool:
        """Remove stored password from keychain."""
        if self.keychain.is_supported():
            return self.keychain.delete_password(self.vault_file)
        return False

    def clear_session(self) -> bool:
        """Clear active session."""
        if self.session.is_supported():
            return self.session.clear_session(self.vault_file)
        return False

    def get_session_info(self) -> dict:
        """Get information about current session."""
        if self.session.is_supported():
            session_info = self.session.get_session_info(self.vault_file)
            if session_info:
                return session_info
        return {}


@click.group()
@click.option(
    "--vault-file",
    "-f",
    default="vault.lockr",
    help="Path to vault file (default: vault.lockr)",
)
@click.option(
    "--no-keychain",
    is_flag=True,
    help="Disable keychain integration",
)
@click.option(
    "--no-sessions",
    is_flag=True,
    help="Disable session management",
)
@click.pass_context
def cli(ctx: click.Context, vault_file: str, no_keychain: bool, no_sessions: bool) -> None:
    """Lockr - Personal vault for secure storage of secrets."""
    ctx.ensure_object(dict)
    ctx.obj = VaultContext(vault_file, use_keychain=not no_keychain, use_sessions=not no_sessions)


@cli.command()
@click.argument("key")
@click.argument("value", required=False)
@click.option("--stdin", is_flag=True, help="Read value from stdin")
@click.option("--generate", "-g", is_flag=True, help="Generate a secure password")
@click.option("--length", default=16, type=click.IntRange(4, 128), help="Password length (4-128, default: 16)")
@click.option("--no-lowercase", is_flag=True, help="Exclude lowercase letters")
@click.option("--no-uppercase", is_flag=True, help="Exclude uppercase letters")
@click.option("--no-digits", is_flag=True, help="Exclude digits")
@click.option("--punctuation", is_flag=True, help="Include punctuation characters")
@click.option("--allow-ambiguous", is_flag=True, help="Allow ambiguous characters (0, O, 1, l, I)")
@click.pass_obj
def add(vault_ctx: VaultContext, key: str, value: Optional[str], stdin: bool,
        generate: bool, length: int, no_lowercase: bool, no_uppercase: bool,
        no_digits: bool, punctuation: bool, allow_ambiguous: bool) -> None:
    """Add a new secret or update an existing one in the vault."""
    # Validate key format
    if not validate_key(key):
        error_msg = get_validation_error_message(key)
        click.echo(f"Error: {error_msg}", err=True)
        sys.exit(1)

    # Validate conflicting options
    if generate and stdin:
        click.echo("Error: Cannot use --generate with --stdin", err=True)
        sys.exit(1)

    if generate and value:
        click.echo("Error: Cannot use --generate with a provided value", err=True)
        sys.exit(1)

    # Authenticate first to check if key exists
    db = vault_ctx.ensure_authenticated()

    # Check if key already exists
    existing_value = db.get_secret(key)
    is_update = existing_value is not None

    # Get value from various sources
    if generate:
        # Generate secure password
        try:
            value = generate_password(
                length=length,
                use_lowercase=not no_lowercase,
                use_uppercase=not no_uppercase,
                use_digits=not no_digits,
                use_punctuation=punctuation,
                exclude_ambiguous=not allow_ambiguous
            )

            # Show password generation info
            charset_info = []
            if not no_lowercase:
                charset_info.append("lowercase")
            if not no_uppercase:
                charset_info.append("uppercase")
            if not no_digits:
                charset_info.append("digits")
            if punctuation:
                charset_info.append("punctuation")

            charset_desc = ", ".join(charset_info)
            if not allow_ambiguous:
                charset_desc += " (excluding ambiguous chars)"

            click.echo(f"🔐 Generated {length}-character password using: {charset_desc}")

        except ValueError as e:
            click.echo(f"Error generating password: {e}", err=True)
            sys.exit(1)

    elif stdin:
        value = sys.stdin.read().strip()
    elif not value:
        prompt = f"Enter {'new ' if is_update else ''}value for '{key}': "
        value = getpass.getpass(prompt)

    if not value:
        click.echo("Error: Value cannot be empty", err=True)
        sys.exit(1)

    # Add or update secret
    try:
        if is_update:
            db.update_secret(key, value)
            click.echo(f"Secret '{key}' updated successfully.")
        else:
            db.add_secret(key, value)
            click.echo(f"Secret '{key}' added successfully.")
    except (DuplicateKeyError, KeyNotFoundError) as e:
        # This shouldn't happen due to our pre-check, but handle gracefully
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except DatabaseError as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)

    # Copy generated passwords to clipboard automatically
    if generate:
        try:
            import pyperclip
            pyperclip.copy(value)
            click.echo("🔐 Generated password copied to clipboard.")

            # Auto-clear clipboard after 60 seconds
            def clear_clipboard() -> None:
                time.sleep(60)
                try:
                    pyperclip.copy("")
                    # Don't print anything as user might be doing other things
                except Exception:
                    pass

            clear_thread = threading.Thread(target=clear_clipboard, daemon=True)
            clear_thread.start()

        except ImportError:
            click.echo("pyperclip not installed. Install with: pip install pyperclip", err=True)
            click.echo(f"Generated password: {value}")
        except Exception as e:
            click.echo(f"Could not copy to clipboard: {e}", err=True)
            click.echo(f"Generated password: {value}")


@cli.command()
@click.argument("key", required=False)
@click.option(
    "--copy", "-c", is_flag=True, help="Copy to clipboard (default behavior in interactive mode)"
)
@click.option(
    "--no-interactive", is_flag=True, help="Disable interactive search (require exact key)"
)
@click.pass_obj
def get(vault_ctx: VaultContext, key: Optional[str], copy: bool, no_interactive: bool) -> None:
    """Retrieve a secret from the vault."""
    # Authenticate and get secret
    db = vault_ctx.ensure_authenticated()

    try:
        # If no key provided or interactive mode enabled, use interactive search
        if key is None or not no_interactive:
            selected_key = None

            if key is None:
                # No key provided - start interactive search
                all_keys = db.list_all_keys()
                if not all_keys:
                    click.echo("No secrets found in vault.", err=True)
                    sys.exit(1)

                from .search.realtime import realtime_search

                def on_select(selected: str) -> None:
                    nonlocal selected_key
                    selected_key = selected

                print()  # Add blank line before interface
                realtime_search(all_keys, on_select)
                print()  # Add blank line after interface

                if not selected_key:
                    click.echo("No selection made.")
                    sys.exit(0)

                key = selected_key
            else:
                # Key provided but interactive mode - try exact match first, then search
                value = db.get_secret(key)
                if value is None:
                    # No exact match, try fuzzy search
                    search_results = db.search_keys(key)
                    if search_results:
                        # Use interactive search with filtered results
                        candidate_keys = [result[0] for result in search_results[:20]]  # Top 20 matches

                        from .search.realtime import realtime_search

                        def on_select(selected: str) -> None:
                            nonlocal selected_key
                            selected_key = selected

                        click.echo(f"No exact match for '{key}'. Showing fuzzy matches:")
                        print()  # Add blank line before interface
                        realtime_search(candidate_keys, on_select)
                        print()  # Add blank line after interface

                        if not selected_key:
                            click.echo("No selection made.")
                            sys.exit(0)

                        key = selected_key

        # Get the secret value
        value = db.get_secret(key)
        if value is None:
            click.echo(f"Secret '{key}' not found.", err=True)
            click.echo("Use 'lockr list' to see available secrets.")
            sys.exit(1)

        # Default behavior: copy to clipboard and exit (like interactive mode)
        if not no_interactive or copy:
            try:
                import pyperclip
                pyperclip.copy(value)
                click.echo(f"✅ Secret '{key}' copied to clipboard.")
                # Auto-clear clipboard after 60 seconds
                def clear_clipboard() -> None:
                    time.sleep(60)
                    try:
                        pyperclip.copy("")
                        # Don't print anything as user might be doing other things
                    except Exception:
                        pass

                clear_thread = threading.Thread(target=clear_clipboard, daemon=True)
                clear_thread.start()

            except ImportError:
                click.echo(
                    "pyperclip not installed. Install with: pip install pyperclip"
                )
                click.echo(f"{key}: {value}")
        else:
            click.echo(f"{key}: {value}")

    except DatabaseError as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("pattern", required=False)
@click.pass_obj
def list(vault_ctx: VaultContext, pattern: Optional[str]) -> None:
    """List all keys in the vault, optionally filtered by pattern."""
    # Authenticate and list keys
    db = vault_ctx.ensure_authenticated()

    try:
        if pattern:
            # Search with pattern
            matches = db.search_keys(pattern)
            keys = [match[0] for match in matches]
            if not keys:
                click.echo(f"No secrets found matching '{pattern}'.")
                return
            click.echo(f"Found {len(keys)} secrets matching '{pattern}':")
        else:
            # List all keys
            keys = db.list_all_keys()
            if not keys:
                click.echo("Vault is empty.")
                return
            click.echo(f"Found {len(keys)} secrets:")

        for key in keys:
            click.echo(f"  {key}")

    except DatabaseError as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)



@cli.command()
@click.argument("key")
@click.option("--confirm", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_obj
def delete(vault_ctx: VaultContext, key: str, confirm: bool) -> None:
    """Delete a secret from the vault."""
    if not confirm:
        if not click.confirm(f"Are you sure you want to delete '{key}'?"):
            click.echo("Cancelled.")
            return

    # Authenticate and delete secret
    db = vault_ctx.ensure_authenticated()

    try:
        db.delete_secret(key)
        click.echo(f"Secret '{key}' deleted successfully.")
    except KeyNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except DatabaseError as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_obj
def info(vault_ctx: VaultContext) -> None:
    """Show vault information."""
    # Create database instance without authenticating
    db = VaultDatabase(vault_ctx.vault_file)
    info = db.get_vault_info()

    click.echo("Vault Information:")
    click.echo(f"  File: {info['file_path']}")

    if not info["exists"]:
        click.echo("  Status: Vault file does not exist")
        click.echo("  Use 'lockr add' to create your first secret")
        return

    click.echo(f"  Size: {info['size_bytes']} bytes")
    click.echo(f"  Modified: {info['modified']}")

    # Try to get additional info if we can authenticate
    if vault_ctx.authenticate():
        if "secret_count" in info:
            click.echo(f"  Secrets: {info['secret_count']}")
        if "failed_attempts" in info:
            click.echo(f"  Failed login attempts: {info['failed_attempts']}")


@cli.command()
@click.argument("action", type=click.Choice(["status", "clear", "test"]))
@click.pass_obj
def keychain(vault_ctx: VaultContext, action: str) -> None:
    """Manage keychain integration."""
    if action == "status":
        if vault_ctx.keychain.is_supported():
            platform_info = vault_ctx.keychain.get_platform_info()
            click.echo(f"✅ Keychain integration: {platform_info}")

            # Check if derived key is stored
            stored = vault_ctx.keychain.has_stored_password(vault_ctx.vault_file)
            status = "stored" if stored else "not stored"
            click.echo(f"   Derived key for '{vault_ctx.vault_file}': {status}")
        else:
            click.echo("❌ Keychain integration: Not supported or disabled")

    elif action == "clear":
        if vault_ctx.clear_keychain():
            click.echo(f"✅ Removed password for '{vault_ctx.vault_file}' from keychain")
        else:
            click.echo("❌ Failed to remove password from keychain", err=True)

    elif action == "test":
        if vault_ctx.keychain.test_keychain_access():
            click.echo("✅ Keychain access test passed")
        else:
            click.echo("❌ Keychain access test failed", err=True)


@cli.command()
@click.argument("action", type=click.Choice(["status", "clear"]))
@click.pass_obj
def session(vault_ctx: VaultContext, action: str) -> None:
    """Manage session authentication."""
    if action == "status":
        if vault_ctx.session.is_supported():
            click.echo("✅ Session management: Enabled")

            # Check if there's an active session
            session_info = vault_ctx.get_session_info()
            if session_info:
                age_minutes = session_info['age_seconds'] // 60
                remaining_minutes = session_info['remaining_seconds'] // 60
                click.echo(f"   Active session for '{vault_ctx.vault_file}':")
                click.echo(f"   Age: {age_minutes} minutes")
                click.echo(f"   Remaining: {remaining_minutes} minutes")
            else:
                click.echo(f"   No active session for '{vault_ctx.vault_file}'")
        else:
            click.echo("❌ Session management: Not supported or disabled")

    elif action == "clear":
        if vault_ctx.clear_session():
            click.echo(f"✅ Cleared session for '{vault_ctx.vault_file}'")
        else:
            click.echo("❌ Failed to clear session", err=True)


def main() -> None:
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
