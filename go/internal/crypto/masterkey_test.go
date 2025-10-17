package crypto

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestGenerateMasterKey(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)
	assert.Equal(t, KeySize, len(key))

	// Generate another key and ensure they're different
	key2, err := GenerateMasterKey()
	require.NoError(t, err)
	assert.NotEqual(t, key, key2)
}

func TestEncryptDecryptPassword(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	password := "my-super-secret-password-123!"

	// Encrypt
	encrypted, err := key.EncryptPassword(password)
	require.NoError(t, err)
	assert.NotEmpty(t, encrypted)
	assert.NotEqual(t, password, encrypted)

	// Decrypt
	decrypted, err := key.DecryptPassword(encrypted)
	require.NoError(t, err)
	assert.Equal(t, password, decrypted)
}

func TestEncryptDecryptMultiplePasswords(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	passwords := []string{
		"short",
		"longer-password-with-special-chars-!@#$%^&*()",
		"unicode-密码-пароль-🔐",
		strings.Repeat("a", 1000), // long password
	}

	for _, password := range passwords {
		encrypted, err := key.EncryptPassword(password)
		require.NoError(t, err)

		decrypted, err := key.DecryptPassword(encrypted)
		require.NoError(t, err)
		assert.Equal(t, password, decrypted, "Failed for password: %s", password)
	}
}

func TestEncryptionDeterministic(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	password := "test-password"

	// Encrypt twice
	encrypted1, err := key.EncryptPassword(password)
	require.NoError(t, err)

	encrypted2, err := key.EncryptPassword(password)
	require.NoError(t, err)

	// Should be different due to random nonce
	assert.NotEqual(t, encrypted1, encrypted2)

	// But both should decrypt to the same password
	decrypted1, err := key.DecryptPassword(encrypted1)
	require.NoError(t, err)
	assert.Equal(t, password, decrypted1)

	decrypted2, err := key.DecryptPassword(encrypted2)
	require.NoError(t, err)
	assert.Equal(t, password, decrypted2)
}

func TestDecryptWithWrongKey(t *testing.T) {
	key1, err := GenerateMasterKey()
	require.NoError(t, err)

	key2, err := GenerateMasterKey()
	require.NoError(t, err)

	password := "secret"

	// Encrypt with key1
	encrypted, err := key1.EncryptPassword(password)
	require.NoError(t, err)

	// Try to decrypt with key2 - should fail
	_, err = key2.DecryptPassword(encrypted)
	assert.Error(t, err)
}

func TestDecryptInvalidData(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	testCases := []struct {
		name      string
		encrypted string
	}{
		{"empty", ""},
		{"invalid base64", "not-base64!!!"},
		{"too short", "YWJj"}, // "abc" in base64
		{"random data", "cmFuZG9tIGRhdGEgdGhhdCBpc250IGVuY3J5cHRlZA=="}, // valid base64 but not encrypted
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := key.DecryptPassword(tc.encrypted)
			assert.Error(t, err, "Should fail for: %s", tc.name)
		})
	}
}

func TestMasterKeyEncodeDecode(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	// Encode
	encoded := key.Encode()
	assert.NotEmpty(t, encoded)

	// Decode
	decoded, err := DecodeMasterKey(encoded)
	require.NoError(t, err)
	assert.Equal(t, key, decoded)
}

func TestDecodeMasterKeyInvalid(t *testing.T) {
	testCases := []struct {
		name    string
		encoded string
	}{
		{"empty", ""},
		{"invalid base64", "not-base64!!!"},
		{"wrong size", "YWJjZGVm"}, // "abcdef" in base64 (wrong size)
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := DecodeMasterKey(tc.encoded)
			assert.Error(t, err)
		})
	}
}

func TestMasterKeyZeroize(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	// Verify key is not all zeros initially
	allZeros := true
	for _, b := range key {
		if b != 0 {
			allZeros = false
			break
		}
	}
	assert.False(t, allZeros, "Key should not be all zeros initially")

	// Zeroize
	key.Zeroize()

	// Verify key is now all zeros
	for i, b := range key {
		assert.Equal(t, byte(0), b, "Byte at index %d should be zero", i)
	}
}

func TestMasterKeyString(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	str := key.String()
	assert.Contains(t, str, "MasterKey")
	assert.Contains(t, str, "32 bytes")
	// Should not contain the actual key
	assert.NotContains(t, str, key.Encode())
}

func TestInvalidMasterKeySize(t *testing.T) {
	invalidKey := MasterKey([]byte{1, 2, 3}) // too short

	_, err := invalidKey.EncryptPassword("test")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid master key size")

	_, err = invalidKey.DecryptPassword("test")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid master key size")
}

func TestEncryptionIntegrity(t *testing.T) {
	key, err := GenerateMasterKey()
	require.NoError(t, err)

	password := "test-password"

	encrypted, err := key.EncryptPassword(password)
	require.NoError(t, err)

	// Tamper with the encrypted data
	tampered := encrypted[:len(encrypted)-4] + "XXXX"

	// Decryption should fail
	_, err = key.DecryptPassword(tampered)
	assert.Error(t, err, "Decryption should fail for tampered data")
}

func BenchmarkGenerateMasterKey(b *testing.B) {
	for i := 0; i < b.N; i++ {
		GenerateMasterKey()
	}
}

func BenchmarkEncryptPassword(b *testing.B) {
	key, _ := GenerateMasterKey()
	password := "test-password-123"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		key.EncryptPassword(password)
	}
}

func BenchmarkDecryptPassword(b *testing.B) {
	key, _ := GenerateMasterKey()
	password := "test-password-123"
	encrypted, _ := key.EncryptPassword(password)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		key.DecryptPassword(encrypted)
	}
}
