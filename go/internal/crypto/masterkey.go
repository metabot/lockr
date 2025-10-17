package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"io"

	"golang.org/x/crypto/pbkdf2"
)

const (
	// KeySize is the size of the master key in bytes (32 bytes = 256 bits)
	KeySize = 32

	// SaltSize is the size of the salt in bytes
	SaltSize = 16

	// NonceSize is the size of the nonce for AES-GCM
	NonceSize = 12

	// PBKDF2Iterations is the number of iterations for PBKDF2
	PBKDF2Iterations = 100000
)

// MasterKey represents an encryption key
type MasterKey []byte

// GenerateMasterKey generates a cryptographically secure random master key
func GenerateMasterKey() (MasterKey, error) {
	key := make([]byte, KeySize)
	if _, err := rand.Read(key); err != nil {
		return nil, fmt.Errorf("failed to generate master key: %w", err)
	}
	return MasterKey(key), nil
}

// EncryptPassword encrypts a vault password using the master key
// Returns: base64(salt + nonce + ciphertext)
func (mk MasterKey) EncryptPassword(password string) (string, error) {
	if len(mk) != KeySize {
		return "", fmt.Errorf("invalid master key size: expected %d, got %d", KeySize, len(mk))
	}

	// Generate random salt
	salt := make([]byte, SaltSize)
	if _, err := rand.Read(salt); err != nil {
		return "", fmt.Errorf("failed to generate salt: %w", err)
	}

	// Derive encryption key from master key and salt using PBKDF2
	derivedKey := pbkdf2.Key(mk, salt, PBKDF2Iterations, KeySize, sha256.New)

	// Create AES cipher
	block, err := aes.NewCipher(derivedKey)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	// Create GCM mode
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	// Generate random nonce
	nonce := make([]byte, NonceSize)
	if _, err := rand.Read(nonce); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	// Encrypt the password
	ciphertext := gcm.Seal(nil, nonce, []byte(password), nil)

	// Combine salt + nonce + ciphertext
	combined := make([]byte, 0, SaltSize+NonceSize+len(ciphertext))
	combined = append(combined, salt...)
	combined = append(combined, nonce...)
	combined = append(combined, ciphertext...)

	// Encode to base64 for storage
	return base64.StdEncoding.EncodeToString(combined), nil
}

// DecryptPassword decrypts an encrypted vault password using the master key
func (mk MasterKey) DecryptPassword(encryptedPassword string) (string, error) {
	if len(mk) != KeySize {
		return "", fmt.Errorf("invalid master key size: expected %d, got %d", KeySize, len(mk))
	}

	// Decode from base64
	combined, err := base64.StdEncoding.DecodeString(encryptedPassword)
	if err != nil {
		return "", fmt.Errorf("failed to decode encrypted password: %w", err)
	}

	// Check minimum length
	minLength := SaltSize + NonceSize + 1 // at least 1 byte of ciphertext
	if len(combined) < minLength {
		return "", fmt.Errorf("encrypted password too short: expected at least %d bytes, got %d", minLength, len(combined))
	}

	// Extract salt, nonce, and ciphertext
	salt := combined[:SaltSize]
	nonce := combined[SaltSize : SaltSize+NonceSize]
	ciphertext := combined[SaltSize+NonceSize:]

	// Derive encryption key from master key and salt using PBKDF2
	derivedKey := pbkdf2.Key(mk, salt, PBKDF2Iterations, KeySize, sha256.New)

	// Create AES cipher
	block, err := aes.NewCipher(derivedKey)
	if err != nil {
		return "", fmt.Errorf("failed to create cipher: %w", err)
	}

	// Create GCM mode
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("failed to create GCM: %w", err)
	}

	// Decrypt the password
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt password: %w", err)
	}

	return string(plaintext), nil
}

// String returns a safe string representation (not the actual key)
func (mk MasterKey) String() string {
	return fmt.Sprintf("MasterKey[%d bytes]", len(mk))
}

// Encode encodes the master key to base64 for storage
func (mk MasterKey) Encode() string {
	return base64.StdEncoding.EncodeToString(mk)
}

// DecodeMasterKey decodes a base64-encoded master key
func DecodeMasterKey(encoded string) (MasterKey, error) {
	key, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, fmt.Errorf("failed to decode master key: %w", err)
	}
	if len(key) != KeySize {
		return nil, fmt.Errorf("invalid master key size: expected %d, got %d", KeySize, len(key))
	}
	return MasterKey(key), nil
}

// Zeroize securely clears the master key from memory
func (mk MasterKey) Zeroize() {
	for i := range mk {
		mk[i] = 0
	}
}

// GenerateRandomNonce generates a random nonce for testing
func GenerateRandomNonce() ([]byte, error) {
	nonce := make([]byte, NonceSize)
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("failed to generate nonce: %w", err)
	}
	return nonce, nil
}
