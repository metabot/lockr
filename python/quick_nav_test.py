#!/usr/bin/env python3
"""
Quick test for the enhanced navigation features.
"""

import sys
from pathlib import Path

# Add the lockr package to the path
sys.path.insert(0, str(Path(__file__).parent))

from lockr.search.realtime import realtime_search


def main():
    """Quick navigation test."""
    test_keys = [
        "github_api_key",
        "github_secret",
        "github_token",
        "aws_access_key",
        "stripe_api_key"
    ]

    selected_key = None

    def on_select(key: str):
        nonlocal selected_key
        selected_key = key

    print("🚀 Enhanced Navigation Test")
    print(f"Testing with {len(test_keys)} items")
    print("\nFeatures to test:")
    print("✓ Match count display (e.g., '3 matches (showing top 3)')")
    print("✓ Selection highlighting with ❯ indicator")
    print("✓ Tab/↓ to move down, Shift+Tab/↑ to move up")
    print("✓ Selection position [1/3], [2/3], etc.")
    print("\nTry searching 'github' and use Tab to navigate between results")
    print()

    try:
        realtime_search(test_keys, on_select)
        if selected_key:
            print(f"\n✅ Selected: {selected_key}")
        else:
            print("\n❌ No selection made")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())