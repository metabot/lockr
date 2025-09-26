"""
Unit tests for sandbox vault functionality.
"""

import tempfile
import os
from unittest.mock import Mock, patch
import pytest

from lockr.database.manager import VaultDatabase
from lockr.search.fuzzy import fuzzy_search, MatchResult
from lockr.keychain import KeychainManager


class TestSandboxFunctionality:
    """Test sandbox vault functionality."""

    @pytest.fixture
    def sandbox_vault(self):
        """Create a sandbox vault similar to create_sandbox.py."""
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        vault = VaultDatabase(vault_path)
        password = "sandbox123"
        vault.connect(password)

        # Add comprehensive test data similar to sandbox
        test_data = {
            # Development accounts
            "github-personal": "ghp_personal_token_123456789abcdef",
            "github-work": "ghp_work_token_987654321fedcba",
            "gitlab-api": "glpat-xxxxxxxxxxxxxxxxxxxx",
            "bitbucket-password": "bitbucket_secure_pass_2024",

            # Email accounts
            "gmail-main": "my_secure_gmail_password",
            "work-email": "corporate_email_password",
            "backup-email": "backup_account_password",

            # Cloud services
            "aws-access-key": "AKIAIOSFODNN7EXAMPLE",
            "aws-secret-key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "azure-subscription": "azure_sub_12345678-1234-1234-1234-123456789abc",
            "gcp-service-account": "gcp-service-account-key.json content",

            # Databases
            "postgres-prod": "pg_production_password_secure",
            "postgres-dev": "pg_development_password",
            "mysql-main": "mysql_root_password_123",
            "redis-cache": "redis_password_cache_2024",

            # API Keys
            "stripe-api": "sk_live_xxxxxxxxxxxxxxxxxxxx",
            "openai-api": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "slack-bot": "xoxb-slack-bot-token-here",
            "discord-bot": "discord_bot_token_123456789",

            # Infrastructure
            "ssh-server": "ssh_private_key_content_here",
            "vpn-password": "vpn_connection_password",
            "docker-registry": "docker_registry_password",
            "kubernetes-token": "k8s_service_token_12345",

            # Social and personal
            "twitter-api": "twitter_api_key_v2",
            "linkedin-password": "linkedin_account_password",
            "facebook-app": "facebook_app_secret_key",
            "instagram-business": "ig_business_account_token"
        }

        for key, value in test_data.items():
            vault.add_secret(key, value)

        yield vault, password, list(test_data.keys())

        # Cleanup
        vault.close()
        if os.path.exists(vault_path):
            os.unlink(vault_path)

    def test_database_connection(self, sandbox_vault):
        """Test database connection with sandbox password."""
        vault, password, keys = sandbox_vault

        # Connection should be successful
        assert vault.connection is not None

        # Should be able to reconnect
        vault.close()
        assert vault.connect(password)

    def test_key_listing(self, sandbox_vault):
        """Test listing all keys in sandbox vault."""
        vault, password, expected_keys = sandbox_vault

        keys = vault.list_all_keys()
        assert len(keys) == len(expected_keys)

        # All expected keys should be present
        for expected_key in expected_keys:
            assert expected_key in keys

    def test_fuzzy_search_github(self, sandbox_vault):
        """Test fuzzy search for github-related entries."""
        vault, password, keys = sandbox_vault

        search_results = fuzzy_search("github", keys, limit=5)

        # Should find github-related keys
        assert len(search_results) >= 2

        github_matches = [r.text for r in search_results if "github" in r.text.lower()]
        assert "github-personal" in github_matches
        assert "github-work" in github_matches

        # Check scores are reasonable
        for result in search_results:
            assert result.score >= 0  # Scores can be > 1 for exact matches
            if "github" in result.text.lower():
                assert result.score > 0.5  # Should have high relevance

    def test_fuzzy_search_various_patterns(self, sandbox_vault):
        """Test fuzzy search with various search patterns."""
        vault, password, keys = sandbox_vault

        test_patterns = [
            ("email", ["gmail-main", "work-email", "backup-email"]),
            ("api", ["gitlab-api", "stripe-api", "openai-api", "twitter-api"]),
            ("aws", ["aws-access-key", "aws-secret-key"]),
            ("postgres", ["postgres-prod", "postgres-dev"]),
        ]

        for pattern, expected_matches in test_patterns:
            results = fuzzy_search(pattern, keys, limit=10)
            result_texts = [r.text for r in results]

            # Should find at least some expected matches
            found_matches = [match for match in expected_matches if match in result_texts]
            assert len(found_matches) > 0, f"Pattern '{pattern}' should match some keys"

    def test_keychain_manager_initialization(self):
        """Test keychain manager initialization and platform detection."""
        km = KeychainManager()

        # Should initialize without error
        assert isinstance(km, KeychainManager)

        # Should have platform info
        platform_info = km.get_platform_info()
        assert isinstance(platform_info, str)
        assert len(platform_info) > 0

    def test_keychain_support_check(self):
        """Test keychain support detection."""
        km = KeychainManager()

        # Should return boolean
        is_supported = km.is_supported()
        assert isinstance(is_supported, bool)

    def test_keychain_key_derivation(self, sandbox_vault):
        """Test keychain key derivation and verification."""
        vault, password, keys = sandbox_vault
        vault_path = str(vault.db_path)

        km = KeychainManager()

        # Test key derivation
        derived_key = km._derive_keychain_key(password, vault_path)
        assert isinstance(derived_key, str)
        assert len(derived_key) > 0

        # Test verification with correct password
        is_valid = km._verify_derived_key(password, vault_path, derived_key)
        assert is_valid is True

        # Test verification with wrong password
        wrong_password = "wrong_password"
        is_valid = km._verify_derived_key(wrong_password, vault_path, derived_key)
        assert is_valid is False

    def test_keychain_key_derivation_consistency(self, sandbox_vault):
        """Test that key derivation is consistent."""
        vault, password, keys = sandbox_vault
        vault_path = str(vault.db_path)

        km = KeychainManager()

        # Generate same key multiple times
        key1 = km._derive_keychain_key(password, vault_path)
        key2 = km._derive_keychain_key(password, vault_path)
        key3 = km._derive_keychain_key(password, vault_path)

        # Should be identical
        assert key1 == key2 == key3

    def test_keychain_key_derivation_unique_per_vault(self, sandbox_vault):
        """Test that key derivation is unique per vault path."""
        vault, password, keys = sandbox_vault
        vault_path = str(vault.db_path)

        km = KeychainManager()

        # Generate keys for different vault paths
        key1 = km._derive_keychain_key(password, vault_path)
        key2 = km._derive_keychain_key(password, "/different/path/vault.lockr")

        # Should be different
        assert key1 != key2

    @patch('lockr.keychain.KEYRING_AVAILABLE', False)
    def test_keychain_manager_with_no_keyring(self):
        """Test keychain manager when keyring is not available."""
        km = KeychainManager(enabled=True)

        # Should handle gracefully
        assert km.enabled is False

    def test_secret_retrieval_sample(self, sandbox_vault):
        """Test retrieving secrets from sandbox vault."""
        vault, password, keys = sandbox_vault

        # Test retrieving a known secret
        sample_key = keys[0]
        secret_value = vault.get_secret(sample_key)

        assert secret_value is not None
        assert isinstance(secret_value, str)
        assert len(secret_value) > 0

    def test_secret_retrieval_various_keys(self, sandbox_vault):
        """Test retrieving various types of secrets."""
        vault, password, keys = sandbox_vault

        test_keys = [
            "github-personal",
            "aws-access-key",
            "postgres-prod",
            "stripe-api"
        ]

        for key in test_keys:
            if key in keys:
                secret_value = vault.get_secret(key)
                assert secret_value is not None
                assert len(secret_value) > 0

    def test_case_insensitive_secret_retrieval(self, sandbox_vault):
        """Test case-insensitive secret retrieval."""
        vault, password, keys = sandbox_vault

        # Pick a known key
        original_key = "github-personal"
        if original_key in keys:
            # Test different case variations
            test_cases = [
                original_key,
                original_key.upper(),
                original_key.capitalize(),
                "GITHUB-PERSONAL",
                "Github-Personal"
            ]

            expected_value = vault.get_secret(original_key)

            for key_variant in test_cases:
                retrieved_value = vault.get_secret(key_variant)
                assert retrieved_value == expected_value

    def test_vault_comprehensive_functionality(self, sandbox_vault):
        """Test comprehensive vault functionality integration."""
        vault, password, keys = sandbox_vault

        # 1. Verify vault info
        info = vault.get_vault_info()
        assert info["secret_count"] == len(keys)
        assert info["exists"] is True

        # 2. Test search functionality
        search_results = vault.search_keys("github")
        github_keys = [result[0] for result in search_results]
        assert len(github_keys) >= 2

        # 3. Test key listing is sorted
        all_keys = vault.list_all_keys()
        assert all_keys == sorted(all_keys)

        # 4. Test that all keys have non-empty values
        for key in keys[:5]:  # Test first 5 keys to keep test fast
            value = vault.get_secret(key)
            assert value is not None
            assert len(value) > 0


class TestSandboxIntegration:
    """Test sandbox integration scenarios."""

    def test_sandbox_workflow_simulation(self):
        """Test complete sandbox workflow similar to original test_sandbox.py."""
        # Create temporary vault
        with tempfile.NamedTemporaryFile(suffix=".lockr", delete=False) as f:
            vault_path = f.name

        password = "sandbox123"

        try:
            # Step 1: Database connection
            db = VaultDatabase(vault_path)
            connection_success = db.connect(password)
            assert connection_success is True

            # Step 2: Add some test data
            test_keys = ["github-test", "api-key-test", "password-test"]
            for key in test_keys:
                db.add_secret(key, f"value-for-{key}")

            # Step 3: Key listing
            keys = db.list_all_keys()
            assert len(keys) == len(test_keys)

            # Step 4: Fuzzy search
            search_results = fuzzy_search("github", keys, limit=3)
            assert len(search_results) >= 1

            # Step 5: Keychain integration test
            km = KeychainManager()
            platform_info = km.get_platform_info()
            assert isinstance(platform_info, str)

            # Step 6: Secret retrieval
            sample_key = keys[0]
            secret_value = db.get_secret(sample_key)
            assert secret_value is not None

        finally:
            # Cleanup
            db.close()
            if os.path.exists(vault_path):
                os.unlink(vault_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])