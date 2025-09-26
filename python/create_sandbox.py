#!/usr/bin/env python3
"""
Script to create a sandbox vault with test data for development and testing.
"""

import os
import sys
import random
import string
from pathlib import Path

# Add the lockr package to the path
sys.path.insert(0, str(Path(__file__).parent))

from lockr.database.manager import VaultDatabase
from lockr.exceptions import DuplicateKeyError


def generate_random_string(length: int) -> str:
    """Generate a random string of given length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_test_secrets(count: int) -> list[tuple[str, str]]:
    """Generate test secrets with realistic-looking keys and values."""
    categories = [
        "api_key",
        "password",
        "token",
        "secret",
        "credential",
        "auth",
        "database",
        "service",
        "config",
        "env",
        "dev",
        "prod",
        "staging",
    ]

    services = [
        "github",
        "gitlab",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "redis",
        "postgres",
        "mysql",
        "mongodb",
        "elasticsearch",
        "stripe",
        "sendgrid",
        "slack",
        "discord",
        "twitter",
        "facebook",
        "google",
        "microsoft",
        "apple",
        "dropbox",
        "notion",
        "figma",
        "vercel",
    ]

    environments = ["dev", "staging", "prod", "test", "local"]

    secrets = []

    for i in range(count):
        # Generate realistic key names
        category = random.choice(categories)
        service = random.choice(services)
        env = random.choice(environments) if random.random() > 0.3 else ""

        if env:
            key = f"{service}_{category}_{env}_{i:03d}"
        else:
            key = f"{service}_{category}_{i:03d}"

        # Generate realistic secret values
        if "password" in category:
            value = generate_random_string(random.randint(12, 24))
        elif "api_key" in category or "token" in category:
            value = f"sk-{generate_random_string(32)}"
        elif "secret" in category:
            value = generate_random_string(random.randint(16, 32))
        else:
            value = generate_random_string(random.randint(8, 20))

        secrets.append((key, value))

    return secrets


def main():
    """Create sandbox vault with test data."""
    sandbox_path = Path("sandbox_vault.db")

    # Remove existing sandbox if it exists
    if sandbox_path.exists():
        sandbox_path.unlink()
        print(f"Removed existing sandbox vault: {sandbox_path}")

    # Create new vault
    print("Creating new sandbox vault...")
    db = VaultDatabase(str(sandbox_path))

    # Connect and create vault with master password
    master_password = "sandbox123"
    try:
        db.connect(master_password)
        print(f"✓ Connected to vault with master password: {master_password}")
    except Exception as e:
        print(f"✗ Failed to connect to vault: {e}")
        return 1

    # Generate test secrets
    print("Generating test secrets...")
    secrets = generate_test_secrets(1000)  # Generate 1000 test secrets

    # Add secrets to vault
    print("Populating vault with test data...")
    added_count = 0
    duplicate_count = 0

    for key, value in secrets:
        try:
            db.add_secret(key, value)
            added_count += 1
            if added_count % 100 == 0:
                print(f"  Added {added_count} secrets...")
        except DuplicateKeyError:
            duplicate_count += 1
        except Exception as e:
            print(f"✗ Failed to add secret '{key}': {e}")

    print(f"✓ Successfully added {added_count} secrets to sandbox vault")
    if duplicate_count > 0:
        print(f"  Skipped {duplicate_count} duplicate keys")

    print(f"\nSandbox vault created: {sandbox_path.absolute()}")
    print(f"Master password: {master_password}")
    print("\nYou can now test the CLI with:")
    print(f"  uv run python -m lockr --vault {sandbox_path} list")

    return 0


if __name__ == "__main__":
    exit(main())
