#!/usr/bin/env python3
"""
Test script for the interactive get command.
"""

import sys
from pathlib import Path

# Add the lockr package to the path
sys.path.insert(0, str(Path(__file__).parent))

from lockr.search.realtime import realtime_search


def test_realtime_search():
    """Test the real-time search interface."""
    print("Testing real-time search interface...")

    # Sample keys for testing
    test_keys = [
        "github_api_key_dev",
        "github_secret_prod",
        "github_token_staging",
        "aws_access_key_dev",
        "aws_secret_key_prod",
        "stripe_api_key",
        "stripe_webhook_secret",
        "postgres_password_dev",
        "redis_auth_token",
        "docker_registry_token"
    ]

    selected_key = None

    def on_select(key: str):
        nonlocal selected_key
        selected_key = key
        print(f"\n✅ You selected: {key}")

    print(f"Launching real-time search with {len(test_keys)} test items...")
    print("Instructions:")
    print("  - Type characters to search (e.g., 'github', 'api', 'prod')")
    print("  - Watch top 3 recommendations update in real-time with match counts")
    print("  - Use Tab/↓ to move to next result, Shift+Tab/↑ to move to previous")
    print("  - Press Enter to select highlighted result (❯)")
    print("  - Press Esc to cancel")
    print()

    try:
        realtime_search(test_keys, on_select)

        if selected_key:
            print(f"Selected key: {selected_key}")
            print("In the real app, this would:")
            print("  1. Copy the secret value to clipboard")
            print("  2. Auto-clear clipboard after 60 seconds")
            print("  3. Exit the program")
        else:
            print("No selection made - user cancelled")

        return True

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the test."""
    print("🚀 Testing interactive get command interface...\n")

    if test_realtime_search():
        print("\n🎉 Interactive get command test completed!")
        return 0
    else:
        print("\n❌ Test failed!")
        return 1


if __name__ == "__main__":
    exit(main())