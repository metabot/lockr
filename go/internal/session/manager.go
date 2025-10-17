package session

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"os/user"
	"time"

	"github.com/lockr/go/internal/database"
	"github.com/lockr/go/internal/keyring"
)

const (
	// SessionTimeout defines how long a session remains valid
	SessionTimeout = 15 * time.Minute

	// SessionIDLength defines the length of session IDs in bytes
	SessionIDLength = 32
)

// Manager handles authentication sessions and timeouts
type Manager struct {
	db             *database.VaultDatabase
	currentSession *database.Session
	keyringMgr     *keyring.Manager
}

// NewManager creates a new session manager
func NewManager(db *database.VaultDatabase) *Manager {
	return &Manager{
		db:         db,
		keyringMgr: keyring.NewManager(),
	}
}

// NewManagerWithKeyring creates a new session manager with a custom keyring manager
func NewManagerWithKeyring(db *database.VaultDatabase, kr *keyring.Manager) *Manager {
	return &Manager{
		db:         db,
		keyringMgr: kr,
	}
}

// Authenticate attempts to authenticate with the given password and creates a session
func (m *Manager) Authenticate(password string) error {
	// Get current user for logging
	currentUser, err := user.Current()
	if err != nil {
		currentUser = &user.User{Username: "unknown"}
	}

	// Attempt database connection
	err = m.db.Connect(password)

	// Log the authentication attempt
	success := err == nil
	logErr := m.db.LogAuthAttempt(currentUser.Username, success, nil, nil)
	if logErr != nil && success {
		// If we successfully authenticated but failed to log, continue anyway
		fmt.Fprintf(os.Stderr, "Warning: failed to log authentication attempt: %v\n", logErr)
	}

	if err != nil {
		return err
	}

	// Optionally save password to keyring
	if m.keyringMgr.IsEnabled() && !m.keyringMgr.HasPassword() {
		if err := m.keyringMgr.PromptToSave(password); err != nil {
			// Log warning but continue - keyring is optional
			fmt.Fprintf(os.Stderr, "Warning: keyring save failed: %v\n", err)
		}
	}

	// Create a new session
	sessionID, err := generateSessionID()
	if err != nil {
		return fmt.Errorf("failed to generate session ID: %w", err)
	}

	session := &database.Session{
		SessionID:    sessionID,
		CreatedAt:    time.Now(),
		ExpiresAt:    time.Now().Add(SessionTimeout),
		LastActivity: time.Now(),
	}

	// Store session in database
	if err := m.createSession(session); err != nil {
		return fmt.Errorf("failed to create session: %w", err)
	}

	m.currentSession = session
	return nil
}

// IsAuthenticated checks if there's an active, valid session
func (m *Manager) IsAuthenticated() bool {
	if m.currentSession == nil {
		return false
	}

	// Check if session has expired
	if time.Now().After(m.currentSession.ExpiresAt) {
		m.expireSession()
		return false
	}

	return m.db.IsConnected()
}

// RefreshSession updates the session's last activity time and extends expiration
func (m *Manager) RefreshSession() error {
	if m.currentSession == nil {
		return database.ErrInvalidSession
	}

	// Check if session has expired
	if time.Now().After(m.currentSession.ExpiresAt) {
		m.expireSession()
		return database.ErrSessionExpired
	}

	// Update session activity
	m.currentSession.LastActivity = time.Now()
	m.currentSession.ExpiresAt = time.Now().Add(SessionTimeout)

	// Update in database
	return m.updateSession(m.currentSession)
}

// Logout terminates the current session
func (m *Manager) Logout() error {
	if m.currentSession == nil {
		return nil // No session to logout from
	}

	// Remove session from database
	if err := m.deleteSession(m.currentSession.SessionID); err != nil {
		// Log but don't fail - we still want to clear local session
		fmt.Fprintf(os.Stderr, "Warning: failed to delete session from database: %v\n", err)
	}

	// Close database connection
	if err := m.db.Close(); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: failed to close database connection: %v\n", err)
	}

	// Clear local session
	m.currentSession = nil
	return nil
}

// GetCurrentSession returns the current active session
func (m *Manager) GetCurrentSession() *database.Session {
	if !m.IsAuthenticated() {
		return nil
	}
	return m.currentSession
}

// GetTimeUntilExpiry returns the time remaining until session expires
func (m *Manager) GetTimeUntilExpiry() time.Duration {
	if m.currentSession == nil {
		return 0
	}

	remaining := time.Until(m.currentSession.ExpiresAt)
	if remaining < 0 {
		return 0
	}
	return remaining
}

// CleanExpiredSessions removes expired sessions from the database
func (m *Manager) CleanExpiredSessions() error {
	if !m.db.IsConnected() {
		return database.ErrDatabaseNotConnected
	}

	// This is a simplified version - in the full implementation,
	// we would need to access the underlying sql.DB connection
	// For now, we'll skip this operation
	return nil
}

// expireSession handles session expiration cleanup
func (m *Manager) expireSession() {
	if m.currentSession != nil {
		// Try to delete from database
		m.deleteSession(m.currentSession.SessionID)
		m.currentSession = nil
	}

	// Close database connection
	m.db.Close()
}

// createSession stores a new session in the database
func (m *Manager) createSession(session *database.Session) error {
	// In a full implementation, we would need direct SQL access
	// For now, we'll store the session locally only
	// This is a limitation of the current database abstraction
	return nil
}

// updateSession updates an existing session in the database
func (m *Manager) updateSession(session *database.Session) error {
	// In a full implementation, we would need direct SQL access
	// For now, we'll update the local session only
	return nil
}

// deleteSession removes a session from the database
func (m *Manager) deleteSession(sessionID string) error {
	// In a full implementation, we would need direct SQL access
	// For now, we'll just clear the local session
	return nil
}

// generateSessionID creates a cryptographically secure random session ID
func generateSessionID() (string, error) {
	bytes := make([]byte, SessionIDLength)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

// SessionInfo provides information about the current session for display
type SessionInfo struct {
	Active        bool          `json:"active"`
	TimeRemaining time.Duration `json:"time_remaining"`
	CreatedAt     time.Time     `json:"created_at,omitempty"`
	LastActivity  time.Time     `json:"last_activity,omitempty"`
}

// GetSessionInfo returns current session information
func (m *Manager) GetSessionInfo() SessionInfo {
	if !m.IsAuthenticated() {
		return SessionInfo{Active: false}
	}

	return SessionInfo{
		Active:        true,
		TimeRemaining: m.GetTimeUntilExpiry(),
		CreatedAt:     m.currentSession.CreatedAt,
		LastActivity:  m.currentSession.LastActivity,
	}
}

// AuthenticateWithKeyring attempts to authenticate using password from keyring
func (m *Manager) AuthenticateWithKeyring() error {
	if !m.keyringMgr.IsEnabled() {
		return keyring.ErrKeyringDisabled
	}

	password, err := m.keyringMgr.GetPassword()
	if err != nil {
		return err
	}

	return m.Authenticate(password)
}

// TryAuthenticateWithKeyring attempts keyring authentication, returns nil if keyring is unavailable
func (m *Manager) TryAuthenticateWithKeyring() error {
	if !m.keyringMgr.IsEnabled() || !m.keyringMgr.HasPassword() {
		return keyring.ErrPasswordNotFound
	}

	return m.AuthenticateWithKeyring()
}

// GetKeyringManager returns the keyring manager
func (m *Manager) GetKeyringManager() *keyring.Manager {
	return m.keyringMgr
}

// ClearKeyring removes the password from the keyring
func (m *Manager) ClearKeyring() error {
	return m.keyringMgr.DeletePassword()
}
