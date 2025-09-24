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
from .exceptions import (
    AuthenticationError,
    DuplicateKeyError,
    KeyNotFoundError,
    DatabaseError,
)
from .utils.validation import validate_key, get_validation_error_message


class VaultContext:
    """Context object for sharing vault state across commands."""

    def __init__(self, vault_file: str):
        self.vault_file = vault_file
        self.db: Optional[VaultDatabase] = None
        self.authenticated = False

    def get_password(self, prompt: str = "Enter master password: ") -> str:
        """Securely get password from user."""
        return getpass.getpass(prompt)

    def authenticate(self) -> bool:
        """Authenticate user and connect to vault."""
        if self.authenticated and self.db:
            return True

        password = self.get_password()
        self.db = VaultDatabase(self.vault_file)

        try:
            self.db.connect(password)
            self.authenticated = True
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


@click.group()
@click.option(
    "--vault-file",
    "-f",
    default="vault.lockr",
    help="Path to vault file (default: vault.lockr)",
)
@click.pass_context
def cli(ctx: click.Context, vault_file: str) -> None:
    """Lockr - Personal vault for secure storage of secrets."""
    ctx.ensure_object(dict)
    ctx.obj = VaultContext(vault_file)


@cli.command()
@click.argument("key")
@click.argument("value", required=False)
@click.option("--stdin", is_flag=True, help="Read value from stdin")
@click.pass_obj
def add(vault_ctx: VaultContext, key: str, value: Optional[str], stdin: bool) -> None:
    """Add a new secret to the vault."""
    # Validate key format
    if not validate_key(key):
        error_msg = get_validation_error_message(key)
        click.echo(f"Error: {error_msg}", err=True)
        sys.exit(1)

    # Get value from stdin or prompt
    if stdin:
        value = sys.stdin.read().strip()
    elif not value:
        value = getpass.getpass(f"Enter value for '{key}': ")

    if not value:
        click.echo("Error: Value cannot be empty", err=True)
        sys.exit(1)

    # Authenticate and add secret
    db = vault_ctx.ensure_authenticated()

    try:
        db.add_secret(key, value)
        click.echo(f"Secret '{key}' added successfully.")
    except DuplicateKeyError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(f"Use 'lockr update {key}' to modify existing secret.")
        sys.exit(1)
    except DatabaseError as e:
        click.echo(f"Database error: {e}", err=True)
        sys.exit(1)


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
@click.argument("value", required=False)
@click.option("--stdin", is_flag=True, help="Read value from stdin")
@click.pass_obj
def update(vault_ctx: VaultContext, key: str, value: Optional[str], stdin: bool) -> None:
    """Update an existing secret in the vault."""
    # Get value from stdin or prompt
    if stdin:
        value = sys.stdin.read().strip()
    elif not value:
        value = getpass.getpass(f"Enter new value for '{key}': ")

    if not value:
        click.echo("Error: Value cannot be empty", err=True)
        sys.exit(1)

    # Authenticate and update secret
    db = vault_ctx.ensure_authenticated()

    try:
        db.update_secret(key, value)
        click.echo(f"Secret '{key}' updated successfully.")
    except KeyNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(f"Use 'lockr add {key}' to create a new secret.")
        sys.exit(1)
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


def main() -> None:
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
