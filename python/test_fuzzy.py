#!/usr/bin/env python3
"""
Test script for fuzzy matching functionality.
"""

import sys
from pathlib import Path

# Add the lockr package to the path
sys.path.insert(0, str(Path(__file__).parent))

from lockr.database.manager import VaultDatabase
from lockr.search.fuzzy import fuzzy_search, highlight_matches
from lockr.search.interactive import interactive_search


def test_fuzzy_search():
    """Test fuzzy search functionality."""
    print("Testing fuzzy search functionality...")

    # Connect to sandbox vault
    vault_path = "sandbox_vault.db"
    if not Path(vault_path).exists():
        print("❌ Sandbox vault not found. Run create_sandbox.py first.")
        return False

    try:
        db = VaultDatabase(vault_path)
        db.connect("sandbox123")
        print("✅ Connected to sandbox vault")
    except Exception as e:
        print(f"❌ Failed to connect to vault: {e}")
        return False

    # Get all keys
    all_keys = db.list_all_keys()
    print(f"✅ Found {len(all_keys)} keys in vault")

    # Test various fuzzy search patterns
    test_patterns = [
        "github",
        "api",
        "aws_secret",
        "prod",
        "dev_key",
        "stripe_token"
    ]

    print("\n🔍 Testing fuzzy search patterns:")
    for pattern in test_patterns:
        print(f"\nPattern: '{pattern}'")

        # Test database search
        db_results = db.search_keys(pattern)
        print(f"  Database results: {len(db_results)}")

        # Show top 5 results
        for i, (key, score) in enumerate(db_results[:5]):
            print(f"    {i+1}. {key} (score: {score:.3f})")

        if len(db_results) > 5:
            print(f"    ... and {len(db_results) - 5} more")

    print("\n✅ Fuzzy search tests completed successfully!")
    return True


def test_interactive_search():
    """Test interactive search interface."""
    print("\n🖥️  Testing interactive search interface...")

    # Connect to sandbox vault
    vault_path = "sandbox_vault.db"
    if not Path(vault_path).exists():
        print("❌ Sandbox vault not found. Run create_sandbox.py first.")
        return False

    try:
        db = VaultDatabase(vault_path)
        db.connect("sandbox123")
        print("✅ Connected to sandbox vault")
    except Exception as e:
        print(f"❌ Failed to connect to vault: {e}")
        return False

    # Get all keys
    all_keys = db.list_all_keys()

    print(f"Launching interactive search with {len(all_keys)} items...")
    print("Use ↑↓ to navigate, type to search, Enter to select, Esc to cancel")

    try:
        selected = interactive_search(
            all_keys,
            title="🔍 Fuzzy Search Test - Select a key",
            max_results=10
        )

        if selected:
            print(f"\n✅ Selected: {selected}")
            # Get the actual secret value
            secret_value = db.get_secret(selected)
            print(f"Secret value: {secret_value}")
        else:
            print("\n❌ No selection made")

        return True

    except Exception as e:
        print(f"❌ Interactive search failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Starting fuzzy search tests...\n")

    success = True

    # Test basic fuzzy search
    if not test_fuzzy_search():
        success = False

    # Ask user if they want to test interactive search
    print("\n" + "="*60)
    answer = input("Test interactive search interface? (y/N): ").strip().lower()

    if answer in ('y', 'yes'):
        if not test_interactive_search():
            success = False

    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())