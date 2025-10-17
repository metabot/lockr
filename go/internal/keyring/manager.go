package keyring

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/lockr/go/internal/crypto"
	"github.com/zalando/go-keyring"
)

const (
	// ServiceName is the name used to identify lockr in the system keyring
	ServiceName = "lockr"

	// DefaultUsername is the default username for storing the master key
	DefaultUsername = "masterkey"
)

// KeyringData stores the master key and encrypted password
type KeyringData struct {
	MasterKey         string `json:"master_key"`           // Base64-encoded master key
	EncryptedPassword string `json:"encrypted_password"`   // Encrypted vault password
}

// Manager handles interactions with the system keyring
type Manager struct {
	serviceName string
	username    string
	enabled     bool
	masterKey   crypto.MasterKey // Cached master key
}

// NewManager creates a new keyring manager
func NewManager() *Manager {
	return &Manager{
		serviceName: ServiceName,
		username:    DefaultUsername,
		enabled:     true,
	}
}

// IsEnabled returns whether keyring integration is enabled
func (m *Manager) IsEnabled() bool {
	return m.enabled
}

// Disable disables keyring integration
func (m *Manager) Disable() {
	m.enabled = false
}

// Enable enables keyring integration
func (m *Manager) Enable() {
	m.enabled = true
}

// SavePassword stores the vault password in the system keyring using a master key
// The master key is stored in the keyring, and the password is encrypted with it
// This allows the vault file to remain portable while providing local convenience
func (m *Manager) SavePassword(password string) error {
	if !m.enabled {
		return nil // Silently skip if disabled
	}

	// Check if we already have a master key
	var masterKey crypto.MasterKey
	if m.masterKey != nil {
		masterKey = m.masterKey
	} else {
		// Check if there's an existing keyring data
		existingData, err := m.loadKeyringData()
		if err == nil && existingData != nil {
			// Reuse existing master key
			masterKey, err = crypto.DecodeMasterKey(existingData.MasterKey)
			if err != nil {
				return fmt.Errorf("failed to decode existing master key: %w", err)
			}
		} else {
			// Generate a new master key
			masterKey, err = crypto.GenerateMasterKey()
			if err != nil {
				return fmt.Errorf("failed to generate master key: %w", err)
			}
		}
	}

	// Encrypt the password with the master key
	encryptedPassword, err := masterKey.EncryptPassword(password)
	if err != nil {
		return fmt.Errorf("failed to encrypt password: %w", err)
	}

	// Store the master key and encrypted password
	data := KeyringData{
		MasterKey:         masterKey.Encode(),
		EncryptedPassword: encryptedPassword,
	}

	// Serialize to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal keyring data: %w", err)
	}

	// Store in system keyring
	err = keyring.Set(m.serviceName, m.username, string(jsonData))
	if err != nil {
		return fmt.Errorf("failed to save to keyring: %w", err)
	}

	// Cache the master key
	m.masterKey = masterKey

	return nil
}

// GetPassword retrieves and decrypts the vault password from the system keyring
func (m *Manager) GetPassword() (string, error) {
	if !m.enabled {
		return "", ErrKeyringDisabled
	}

	// Load keyring data
	data, err := m.loadKeyringData()
	if err != nil {
		return "", err
	}

	// Decode the master key
	masterKey, err := crypto.DecodeMasterKey(data.MasterKey)
	if err != nil {
		return "", fmt.Errorf("failed to decode master key: %w", err)
	}

	// Decrypt the password
	password, err := masterKey.DecryptPassword(data.EncryptedPassword)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt password: %w", err)
	}

	// Cache the master key
	m.masterKey = masterKey

	return password, nil
}

// loadKeyringData loads and parses keyring data from the system keyring
func (m *Manager) loadKeyringData() (*KeyringData, error) {
	jsonData, err := keyring.Get(m.serviceName, m.username)
	if err != nil {
		if err == keyring.ErrNotFound {
			return nil, ErrPasswordNotFound
		}
		return nil, fmt.Errorf("failed to retrieve from keyring: %w", err)
	}

	var data KeyringData
	if err := json.Unmarshal([]byte(jsonData), &data); err != nil {
		return nil, fmt.Errorf("failed to parse keyring data: %w", err)
	}

	return &data, nil
}

// DeletePassword removes the master key and encrypted password from the system keyring
func (m *Manager) DeletePassword() error {
	if !m.enabled {
		return nil // Silently skip if disabled
	}

	// Clear cached master key
	if m.masterKey != nil {
		m.masterKey.Zeroize()
		m.masterKey = nil
	}

	err := keyring.Delete(m.serviceName, m.username)
	if err != nil {
		// Ignore "not found" errors when deleting
		if err == keyring.ErrNotFound {
			return nil
		}
		return fmt.Errorf("failed to delete from keyring: %w", err)
	}

	return nil
}

// HasPassword checks if keyring data is stored
func (m *Manager) HasPassword() bool {
	if !m.enabled {
		return false
	}

	_, err := m.loadKeyringData()
	return err == nil
}

// UpdatePassword updates the stored password in the keyring
// This preserves the existing master key and only updates the encrypted password
func (m *Manager) UpdatePassword(newPassword string) error {
	if !m.enabled {
		return nil
	}

	// Save the new password (SavePassword will reuse the existing master key)
	return m.SavePassword(newPassword)
}

// GetMasterKey returns the cached master key (for advanced use cases)
func (m *Manager) GetMasterKey() crypto.MasterKey {
	return m.masterKey
}

// SetMasterKey sets the master key (for advanced use cases)
func (m *Manager) SetMasterKey(key crypto.MasterKey) {
	m.masterKey = key
}

// IsSupported checks if keyring is supported on the current system
func IsSupported() bool {
	// The zalando/go-keyring library supports macOS, Windows, and Linux
	// We can do a quick test to see if it's working
	testService := "lockr-test"
	testUser := "test"
	testData := "test"

	// Try to set and get a test value
	err := keyring.Set(testService, testUser, testData)
	if err != nil {
		return false
	}

	// Clean up the test value
	keyring.Delete(testService, testUser)

	return true
}

// PrintDebugInfo prints debug information about keyring status
func (m *Manager) PrintDebugInfo() {
	fmt.Printf("Keyring Status:\n")
	fmt.Printf("  Service: %s\n", m.serviceName)
	fmt.Printf("  Username: %s\n", m.username)
	fmt.Printf("  Enabled: %t\n", m.enabled)
	fmt.Printf("  Has Stored Data: %t\n", m.HasPassword())
	fmt.Printf("  Supported: %t\n", IsSupported())
	fmt.Printf("  Master Key Cached: %t\n", m.masterKey != nil)
}

// SetServiceName allows customizing the service name (useful for testing)
func (m *Manager) SetServiceName(name string) {
	m.serviceName = name
}

// SetUsername allows customizing the username (useful for multi-vault scenarios)
func (m *Manager) SetUsername(username string) {
	m.username = username
}

// GetServiceName returns the current service name
func (m *Manager) GetServiceName() string {
	return m.serviceName
}

// GetUsername returns the current username
func (m *Manager) GetUsername() string {
	return m.username
}

// PromptToSave prompts the user to save their password to the keyring
func (m *Manager) PromptToSave(password string) error {
	if !m.enabled {
		return nil
	}

	// Check if data is already saved
	if m.HasPassword() {
		return nil
	}

	// Prompt user
	fmt.Print("Save password to system keyring for auto-login? (y/N): ")
	var response string
	fmt.Scanln(&response)

	if response == "y" || response == "Y" {
		if err := m.SavePassword(password); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to save password to keyring: %v\n", err)
			return err
		}
		fmt.Println("Password saved to keyring (vault file remains portable)")
	}

	return nil
}

// ClearCache clears the cached master key from memory
func (m *Manager) ClearCache() {
	if m.masterKey != nil {
		m.masterKey.Zeroize()
		m.masterKey = nil
	}
}
