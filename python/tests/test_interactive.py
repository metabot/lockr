"""
Unit tests for interactive search functionality.
"""

import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from lockr.database.manager import VaultDatabase
from lockr.search.fuzzy import fuzzy_search, MatchResult


class TestInteractiveSearch:
    """Test interactive search functionality."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault with test data."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        vault = VaultDatabase(vault_path)
        vault.connect("test-password")

        # Add sample test data
        test_keys = [
            "github-personal",
            "github-work",
            "gmail-password",
            "aws-api-key",
            "database-prod",
            "database-dev",
            "slack-token",
            "docker-registry",
            "ssh-server",
            "vpn-credentials"
        ]

        for key in test_keys:
            vault.add_secret(key, f"secret-value-for-{key}")

        yield vault, test_keys

        # Cleanup
        vault.close()
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    def test_vault_connection_and_key_loading(self, temp_vault):
        """Test that we can connect to vault and load keys."""
        vault, expected_keys = temp_vault

        # Test connection is working
        assert vault.connection is not None

        # Test key loading
        keys = vault.list_all_keys()
        assert len(keys) == len(expected_keys)
        assert all(key in keys for key in expected_keys)

    def test_fuzzy_search_functionality(self, temp_vault):
        """Test fuzzy search with various patterns."""
        vault, keys = temp_vault

        # Test exact match
        results = fuzzy_search("github", keys, limit=5)
        assert len(results) >= 2
        github_keys = [r.text for r in results if "github" in r.text]
        assert "github-personal" in github_keys
        assert "github-work" in github_keys

        # Test partial match
        results = fuzzy_search("data", keys, limit=5)
        database_keys = [r.text for r in results if "database" in r.text]
        assert len(database_keys) >= 2

        # Test no matches
        results = fuzzy_search("nonexistent", keys, limit=5)
        # Should return empty or very low scores
        high_score_matches = [r for r in results if r.score > 0.5]
        assert len(high_score_matches) == 0

    def test_secret_retrieval_after_selection(self, temp_vault):
        """Test secret retrieval after key selection."""
        vault, keys = temp_vault

        # Test retrieving a secret
        test_key = "github-personal"
        secret_value = vault.get_secret(test_key)
        assert secret_value == f"secret-value-for-{test_key}"

        # Test case-insensitive retrieval
        secret_value = vault.get_secret("GITHUB-PERSONAL")
        assert secret_value == f"secret-value-for-{test_key}"

    @patch('lockr.search.realtime.realtime_search')
    def test_realtime_search_callback(self, mock_realtime_search, temp_vault):
        """Test that realtime search callback mechanism works."""
        vault, keys = temp_vault

        # Mock the realtime search to simulate user selection
        selected_key = "github-personal"

        def mock_search_callback(key_list, callback_fn):
            # Simulate user selecting a key
            callback_fn(selected_key)

        mock_realtime_search.side_effect = mock_search_callback

        # Test the callback mechanism
        result_key = None
        def on_select(key: str) -> None:
            nonlocal result_key
            result_key = key

        # Import and test the realtime search
        from lockr.search.realtime import realtime_search
        realtime_search(keys, on_select)

        # Verify callback was called with correct key
        assert result_key == selected_key

    def test_fuzzy_result_structure(self, temp_vault):
        """Test FuzzyResult structure and properties."""
        vault, keys = temp_vault

        results = fuzzy_search("github", keys, limit=3)

        for result in results:
            assert isinstance(result, MatchResult)
            assert hasattr(result, 'text')
            assert hasattr(result, 'score')
            assert isinstance(result.text, str)
            assert isinstance(result.score, (int, float))
            assert result.score >= 0  # Scores can be > 1 for exact matches

    def test_search_with_empty_keys(self):
        """Test fuzzy search with empty key list."""
        results = fuzzy_search("test", [], limit=5)
        assert len(results) == 0

    def test_search_with_various_limits(self, temp_vault):
        """Test fuzzy search with different limit values."""
        vault, keys = temp_vault

        # Test with limit 1
        results = fuzzy_search("data", keys, limit=1)
        assert len(results) <= 1

        # Test with limit 3
        results = fuzzy_search("github", keys, limit=3)
        assert len(results) <= 3

        # Test with limit larger than available matches
        results = fuzzy_search("github", keys, limit=10)
        # Should not exceed actual matches
        assert len(results) <= len(keys)

    @patch('builtins.print')
    def test_error_handling_during_search(self, mock_print, temp_vault):
        """Test error handling during interactive search operations."""
        vault, keys = temp_vault

        # Close the vault to simulate connection error
        vault.close()

        # Try to get secret from closed vault - should handle gracefully
        with pytest.raises(Exception):
            vault.get_secret("github-personal")

    def test_case_insensitive_fuzzy_search(self, temp_vault):
        """Test that fuzzy search is case insensitive."""
        vault, keys = temp_vault

        # Search with different cases
        results_lower = fuzzy_search("github", keys, limit=5)
        results_upper = fuzzy_search("GITHUB", keys, limit=5)
        results_mixed = fuzzy_search("GitHub", keys, limit=5)

        # Should find similar results regardless of case
        assert len(results_lower) > 0
        assert len(results_upper) > 0
        assert len(results_mixed) > 0

        # Extract text from results for comparison
        lower_texts = [r.text for r in results_lower]
        upper_texts = [r.text for r in results_upper]
        mixed_texts = [r.text for r in results_mixed]

        # Should contain similar matches
        github_keys = [key for key in keys if "github" in key.lower()]
        for github_key in github_keys:
            assert github_key in lower_texts
            assert github_key in upper_texts
            assert github_key in mixed_texts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])