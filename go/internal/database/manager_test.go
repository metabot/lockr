package database

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestVaultDatabase_Basic(t *testing.T) {
	// Create temporary database for testing
	tmpDir, err := os.MkdirTemp("", "lockr_test_*")
	require.NoError(t, err)
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")
	testPassword := "test_password_123"

	// Test database creation and connection
	vd := NewVaultDatabase(dbPath)
	assert.False(t, vd.IsConnected())

	err = vd.Connect(testPassword)
	require.NoError(t, err)
	assert.True(t, vd.IsConnected())

	// Test basic secret operations
	testKey := "test_key"
	testValue := "test_secret_value"

	// Create secret
	err = vd.CreateSecret(testKey, testValue)
	require.NoError(t, err)

	// Retrieve secret
	secret, err := vd.GetSecret(testKey)
	require.NoError(t, err)
	assert.Equal(t, testKey, secret.Key)
	assert.Equal(t, testValue, secret.Value)
	assert.Equal(t, int64(1), secret.AccessCount)

	// List secrets
	secrets, err := vd.ListSecrets()
	require.NoError(t, err)
	assert.Len(t, secrets, 1)
	assert.Equal(t, testKey, secrets[0].Key)

	// Update secret
	newValue := "updated_secret_value"
	err = vd.UpdateSecret(testKey, newValue)
	require.NoError(t, err)

	// Verify update
	updatedSecret, err := vd.GetSecret(testKey)
	require.NoError(t, err)
	assert.Equal(t, newValue, updatedSecret.Value)
	assert.Equal(t, int64(2), updatedSecret.AccessCount) // Should be incremented

	// Delete secret
	err = vd.DeleteSecret(testKey)
	require.NoError(t, err)

	// Verify deletion
	_, err = vd.GetSecret(testKey)
	assert.Equal(t, ErrKeyNotFound, err)

	// Close connection
	err = vd.Close()
	require.NoError(t, err)
	assert.False(t, vd.IsConnected())
}

func TestVaultDatabase_Errors(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "lockr_test_*")
	require.NoError(t, err)
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")
	vd := NewVaultDatabase(dbPath)

	// Test operations without connection
	err = vd.CreateSecret("key", "value")
	assert.Equal(t, ErrDatabaseNotConnected, err)

	_, err = vd.GetSecret("key")
	assert.Equal(t, ErrDatabaseNotConnected, err)

	// Connect and test error conditions
	err = vd.Connect("test_password")
	require.NoError(t, err)

	// Test duplicate key
	err = vd.CreateSecret("key1", "value1")
	require.NoError(t, err)

	err = vd.CreateSecret("key1", "value2")
	assert.Equal(t, ErrDuplicateKey, err)

	// Test key not found
	_, err = vd.GetSecret("nonexistent")
	assert.Equal(t, ErrKeyNotFound, err)

	err = vd.UpdateSecret("nonexistent", "value")
	assert.Equal(t, ErrKeyNotFound, err)

	err = vd.DeleteSecret("nonexistent")
	assert.Equal(t, ErrKeyNotFound, err)

	vd.Close()
}

func TestVaultDatabase_KeyValidation(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "lockr_test_*")
	require.NoError(t, err)
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")
	vd := NewVaultDatabase(dbPath)
	err = vd.Connect("test_password")
	require.NoError(t, err)
	defer vd.Close()

	// Test invalid keys
	invalidKeys := []string{
		"",                                   // Empty key
		string(make([]byte, MaxKeyLength+1)), // Too long
	}

	for _, key := range invalidKeys {
		err := vd.CreateSecret(key, "value")
		assert.Equal(t, ErrInvalidKey, err)
	}

	// Test valid key
	validKey := "valid_key_123"
	err = vd.CreateSecret(validKey, "value")
	assert.NoError(t, err)
}

func TestVaultDatabase_Search(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "lockr_test_*")
	require.NoError(t, err)
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")
	vd := NewVaultDatabase(dbPath)
	err = vd.Connect("test_password")
	require.NoError(t, err)
	defer vd.Close()

	// Create test data
	testData := map[string]string{
		"api_key_github":    "gh_token",
		"api_key_stripe":    "sk_token",
		"database_password": "db_pass",
		"user_password":     "user_pass",
	}

	for key, value := range testData {
		err := vd.CreateSecret(key, value)
		require.NoError(t, err)
	}

	// Test search
	results, err := vd.SearchSecrets("api")
	require.NoError(t, err)
	assert.Len(t, results, 2)

	results, err = vd.SearchSecrets("password")
	require.NoError(t, err)
	assert.Len(t, results, 2)

	results, err = vd.SearchSecrets("nonexistent")
	require.NoError(t, err)
	assert.Len(t, results, 0)
}
