package keyring

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewManager(t *testing.T) {
	m := NewManager()
	assert.NotNil(t, m)
	assert.Equal(t, ServiceName, m.GetServiceName())
	assert.Equal(t, DefaultUsername, m.GetUsername())
	assert.True(t, m.IsEnabled())
}

func TestManagerEnableDisable(t *testing.T) {
	m := NewManager()

	// Test disable
	m.Disable()
	assert.False(t, m.IsEnabled())

	// Test enable
	m.Enable()
	assert.True(t, m.IsEnabled())
}

func TestSaveAndGetPassword(t *testing.T) {
	m := NewManager()
	// Use a unique service name for testing to avoid conflicts
	m.SetServiceName("lockr-test-" + t.Name())

	// Clean up after test
	defer m.DeletePassword()

	testPassword := "my-super-secret-password-123!"

	// Save password
	err := m.SavePassword(testPassword)
	require.NoError(t, err)

	// Verify it was saved
	assert.True(t, m.HasPassword())

	// Get password
	password, err := m.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, testPassword, password)
}

func TestSavePasswordGeneratesMasterKey(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	password := "test-password"

	// Save password - should generate a master key
	err := m.SavePassword(password)
	require.NoError(t, err)

	// Verify master key was cached
	assert.NotNil(t, m.GetMasterKey())
}

func TestSavePasswordReusesMasterKey(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	password1 := "first-password"
	password2 := "second-password"

	// Save first password
	err := m.SavePassword(password1)
	require.NoError(t, err)

	// Get the master key
	masterKey1 := m.GetMasterKey()
	require.NotNil(t, masterKey1)

	// Update to second password
	err = m.UpdatePassword(password2)
	require.NoError(t, err)

	// Master key should be the same
	masterKey2 := m.GetMasterKey()
	assert.Equal(t, masterKey1, masterKey2)

	// But password should be different
	retrievedPassword, err := m.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, password2, retrievedPassword)
}

func TestSavePasswordWhenDisabled(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())
	m.Disable()

	defer m.DeletePassword()

	// Should not error, just silently skip
	err := m.SavePassword("test")
	assert.NoError(t, err)

	// Re-enable and check password wasn't saved
	m.Enable()
	assert.False(t, m.HasPassword())
}

func TestGetPasswordWhenDisabled(t *testing.T) {
	m := NewManager()
	m.Disable()

	password, err := m.GetPassword()
	assert.Equal(t, "", password)
	assert.Equal(t, ErrKeyringDisabled, err)
}

func TestGetPasswordNotFound(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-nonexistent")

	// Clean up any existing password
	m.DeletePassword()

	password, err := m.GetPassword()
	assert.Equal(t, "", password)
	assert.Equal(t, ErrPasswordNotFound, err)
}

func TestDeletePassword(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	// Save a password first
	err := m.SavePassword("test")
	require.NoError(t, err)
	assert.True(t, m.HasPassword())
	assert.NotNil(t, m.GetMasterKey())

	// Delete it
	err = m.DeletePassword()
	require.NoError(t, err)
	assert.False(t, m.HasPassword())
	assert.Nil(t, m.GetMasterKey()) // Master key should be cleared

	// Deleting again should not error
	err = m.DeletePassword()
	assert.NoError(t, err)
}

func TestDeletePasswordWhenDisabled(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	// Save a password first
	m.SavePassword("test")
	defer m.DeletePassword()

	// Disable and try to delete
	m.Disable()
	err := m.DeletePassword()
	assert.NoError(t, err)

	// Re-enable and verify password is still there
	m.Enable()
	assert.True(t, m.HasPassword())
}

func TestUpdatePassword(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	// Save initial password
	err := m.SavePassword("old-password")
	require.NoError(t, err)

	// Update password
	err = m.UpdatePassword("new-password")
	require.NoError(t, err)

	// Verify new password
	password, err := m.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, "new-password", password)
}

func TestHasPassword(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	// Initially should not have password
	assert.False(t, m.HasPassword())

	// Save password
	m.SavePassword("test")
	assert.True(t, m.HasPassword())

	// Delete password
	m.DeletePassword()
	assert.False(t, m.HasPassword())
}

func TestCustomServiceAndUsername(t *testing.T) {
	m := NewManager()
	customService := "lockr-custom-test"
	customUsername := "custom-user"

	m.SetServiceName(customService)
	m.SetUsername(customUsername)

	defer m.DeletePassword()

	assert.Equal(t, customService, m.GetServiceName())
	assert.Equal(t, customUsername, m.GetUsername())

	// Test save/get with custom values
	err := m.SavePassword("test")
	require.NoError(t, err)

	password, err := m.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, "test", password)
}

func TestIsSupported(t *testing.T) {
	// This test may fail on systems without keyring support
	// Just verify it returns a boolean
	supported := IsSupported()
	t.Logf("Keyring supported: %v", supported)
	assert.IsType(t, true, supported)
}

func TestKeyringErrorsExist(t *testing.T) {
	assert.NotNil(t, ErrKeyringDisabled)
	assert.NotNil(t, ErrPasswordNotFound)
	assert.NotNil(t, ErrKeyringNotSupported)
}

func TestClearCache(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	// Save password
	err := m.SavePassword("test")
	require.NoError(t, err)

	// Verify master key is cached
	assert.NotNil(t, m.GetMasterKey())

	// Clear cache
	m.ClearCache()

	// Master key should be nil
	assert.Nil(t, m.GetMasterKey())

	// But password should still be retrievable
	password, err := m.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, "test", password)
}

func TestEncryptionIsolation(t *testing.T) {
	// Test that different managers have different master keys
	m1 := NewManager()
	m1.SetServiceName("lockr-test-" + t.Name() + "-1")

	m2 := NewManager()
	m2.SetServiceName("lockr-test-" + t.Name() + "-2")

	defer m1.DeletePassword()
	defer m2.DeletePassword()

	password := "same-password"

	// Save same password in both
	err := m1.SavePassword(password)
	require.NoError(t, err)

	err = m2.SavePassword(password)
	require.NoError(t, err)

	// Both should return the same password
	p1, err := m1.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, password, p1)

	p2, err := m2.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, password, p2)

	// But master keys should be different
	assert.NotEqual(t, m1.GetMasterKey(), m2.GetMasterKey())
}

func TestMasterKeyPersistence(t *testing.T) {
	serviceName := "lockr-test-" + t.Name()

	// First manager - save password
	m1 := NewManager()
	m1.SetServiceName(serviceName)

	err := m1.SavePassword("test-password")
	require.NoError(t, err)

	// Create a second manager with the same service name
	m2 := NewManager()
	m2.SetServiceName(serviceName)

	defer m2.DeletePassword()

	// Second manager should be able to retrieve the password
	password, err := m2.GetPassword()
	require.NoError(t, err)
	assert.Equal(t, "test-password", password)
}

func TestMultiplePasswords(t *testing.T) {
	m := NewManager()
	m.SetServiceName("lockr-test-" + t.Name())

	defer m.DeletePassword()

	passwords := []string{
		"short",
		"longer-password-with-special-chars-!@#$%^&*()",
		"unicode-密码-пароль-🔐",
	}

	for _, password := range passwords {
		// Save password
		err := m.SavePassword(password)
		require.NoError(t, err)

		// Retrieve and verify
		retrieved, err := m.GetPassword()
		require.NoError(t, err)
		assert.Equal(t, password, retrieved, "Failed for password: %s", password)
	}
}
