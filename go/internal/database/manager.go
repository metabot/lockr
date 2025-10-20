package database

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "github.com/mutecomm/go-sqlcipher/v4" // SQLCipher driver
)

const (
	// SessionTimeout defines the session timeout duration (15 minutes)
	SessionTimeout = 15 * time.Minute

	// MaxKeyLength defines the maximum allowed key length
	MaxKeyLength = 256

	// SchemaVersion defines the current database schema version
	SchemaVersion = 1
)

// VaultDatabase manages the encrypted SQLCipher database
type VaultDatabase struct {
	dbPath     string
	connection *sql.DB
	isOpen     bool
}

// NewVaultDatabase creates a new VaultDatabase instance
func NewVaultDatabase(dbPath string) *VaultDatabase {
	return &VaultDatabase{
		dbPath: dbPath,
		isOpen: false,
	}
}

// Connect establishes a connection to the encrypted database with the given password
func (vd *VaultDatabase) Connect(password string) error {
	if vd.isOpen {
		return nil // Already connected
	}

	// Build connection string with SQLCipher parameters
	connStr := fmt.Sprintf("%s?_pragma_key=%s&_pragma_cipher_page_size=4096&_pragma_cipher_hmac_algorithm=HMAC_SHA512&_pragma_cipher_kdf_algorithm=PBKDF2_HMAC_SHA512&_pragma_cipher_kdf_iter=256000",
		vd.dbPath, password)

	db, err := sql.Open("sqlite3", connStr)
	if err != nil {
		return NewDatabaseError("connect", err)
	}

	// Test the connection with a simple query to verify password
	if err := vd.testConnection(db); err != nil {
		db.Close()
		return err
	}

	vd.connection = db
	vd.isOpen = true

	// Initialize schema if needed
	return vd.initializeSchema()
}

// testConnection verifies the database connection and password
func (vd *VaultDatabase) testConnection(db *sql.DB) error {
	var result int
	err := db.QueryRow("SELECT 1").Scan(&result)
	if err != nil {
		if strings.Contains(err.Error(), "file is not a database") ||
			strings.Contains(err.Error(), "file is encrypted") {
			return ErrAuthenticationFailed
		}
		return NewDatabaseError("test_connection", err)
	}
	return nil
}

// initializeSchema creates the database schema if it doesn't exist
func (vd *VaultDatabase) initializeSchema() error {
	// Read schema from the shared schema file
	schemaPath := filepath.Join(filepath.Dir(vd.dbPath), "..", "..", "schema", "vault.sql")
	schemaBytes, err := os.ReadFile(schemaPath)
	if err != nil {
		// Fallback to embedded schema
		return vd.createSchemaFromEmbedded()
	}

	schema := string(schemaBytes)
	_, err = vd.connection.Exec(schema)
	if err != nil {
		return NewDatabaseError("initialize_schema", err)
	}

	return nil
}

// createSchemaFromEmbedded creates the schema using embedded SQL statements
func (vd *VaultDatabase) createSchemaFromEmbedded() error {
	schema := `
		-- Secrets table: Core key-value storage
		CREATE TABLE IF NOT EXISTS secrets (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			key TEXT UNIQUE NOT NULL COLLATE NOCASE,
			value TEXT NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			access_count INTEGER DEFAULT 0,
			tags TEXT,
			notes TEXT
		);

		-- Authentication attempts log
		CREATE TABLE IF NOT EXISTS auth_attempts (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			username TEXT NOT NULL,
			success BOOLEAN DEFAULT FALSE,
			ip_address TEXT,
			session_id TEXT
		);

		-- Session management
		CREATE TABLE IF NOT EXISTS sessions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			session_id TEXT UNIQUE NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			expires_at TIMESTAMP NOT NULL,
			last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		-- Performance indexes
		CREATE INDEX IF NOT EXISTS idx_secrets_key ON secrets(key COLLATE NOCASE);
		CREATE INDEX IF NOT EXISTS idx_secrets_created ON secrets(created_at);
		CREATE INDEX IF NOT EXISTS idx_secrets_accessed ON secrets(last_accessed);
		CREATE INDEX IF NOT EXISTS idx_auth_timestamp ON auth_attempts(timestamp);
		CREATE INDEX IF NOT EXISTS idx_auth_username ON auth_attempts(username);
		CREATE INDEX IF NOT EXISTS idx_sessions_id ON sessions(session_id);
		CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

		-- Version information for future migrations
		CREATE TABLE IF NOT EXISTS schema_version (
			version INTEGER PRIMARY KEY,
			applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		-- Insert initial schema version
		INSERT OR IGNORE INTO schema_version (version) VALUES (1);
	`

	_, err := vd.connection.Exec(schema)
	if err != nil {
		return NewDatabaseError("create_embedded_schema", err)
	}

	return nil
}

// Rekey changes the encryption password for the vault database
// This operation re-encrypts the entire database with a new password
func (vd *VaultDatabase) Rekey(oldPassword, newPassword string) error {
	// First, verify the old password by connecting
	if vd.isOpen {
		// Close existing connection
		if err := vd.Close(); err != nil {
			return err
		}
	}

	// Connect with old password
	if err := vd.Connect(oldPassword); err != nil {
		return fmt.Errorf("failed to verify old password: %w", err)
	}

	// Execute PRAGMA rekey to change the password
	// SQLCipher will re-encrypt the entire database with the new password
	_, err := vd.connection.Exec(fmt.Sprintf("PRAGMA rekey = '%s'", newPassword))
	if err != nil {
		vd.Close()
		return NewDatabaseError("rekey", err)
	}

	// Close and reconnect with new password to verify
	if err := vd.Close(); err != nil {
		return err
	}

	// Reconnect with new password to verify it worked
	if err := vd.Connect(newPassword); err != nil {
		return fmt.Errorf("failed to verify new password after rekey: %w", err)
	}

	return nil
}

// Close closes the database connection
func (vd *VaultDatabase) Close() error {
	if !vd.isOpen || vd.connection == nil {
		return nil
	}

	err := vd.connection.Close()
	vd.connection = nil
	vd.isOpen = false

	if err != nil {
		return NewDatabaseError("close", err)
	}

	return nil
}

// IsConnected returns true if the database connection is active
func (vd *VaultDatabase) IsConnected() bool {
	return vd.isOpen && vd.connection != nil
}

// ensureConnected checks if the database is connected and returns an error if not
func (vd *VaultDatabase) ensureConnected() error {
	if !vd.IsConnected() {
		return ErrDatabaseNotConnected
	}
	return nil
}

// CreateSecret adds a new secret to the vault
func (vd *VaultDatabase) CreateSecret(key, value string) error {
	if err := vd.ensureConnected(); err != nil {
		return err
	}

	if err := validateKey(key); err != nil {
		return err
	}

	query := `
		INSERT INTO secrets (key, value, created_at, last_accessed, access_count)
		VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
	`

	_, err := vd.connection.Exec(query, key, value)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE constraint failed") {
			return ErrDuplicateKey
		}
		return NewDatabaseError("create_secret", err)
	}

	return nil
}

// GetSecret retrieves a secret by key and updates access tracking
func (vd *VaultDatabase) GetSecret(key string) (*Secret, error) {
	if err := vd.ensureConnected(); err != nil {
		return nil, err
	}

	// First, get the secret
	query := `
		SELECT id, key, value, created_at, last_accessed, access_count, tags, notes
		FROM secrets
		WHERE key = ? COLLATE NOCASE
	`

	var secret Secret
	err := vd.connection.QueryRow(query, key).Scan(
		&secret.ID,
		&secret.Key,
		&secret.Value,
		&secret.CreatedAt,
		&secret.LastAccessed,
		&secret.AccessCount,
		&secret.Tags,
		&secret.Notes,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, ErrKeyNotFound
		}
		return nil, NewDatabaseError("get_secret", err)
	}

	// Update access tracking
	updateQuery := `
		UPDATE secrets
		SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
		WHERE key = ? COLLATE NOCASE
	`

	_, err = vd.connection.Exec(updateQuery, key)
	if err != nil {
		// Non-fatal error - return the secret but log the tracking failure
		return &secret, NewDatabaseError("update_access_tracking", err)
	}

	// Increment the access count in the returned secret to match database state
	secret.AccessCount++

	return &secret, nil
}

// UpdateSecret updates an existing secret's value
func (vd *VaultDatabase) UpdateSecret(key, value string) error {
	if err := vd.ensureConnected(); err != nil {
		return err
	}

	query := `
		UPDATE secrets
		SET value = ?, last_accessed = CURRENT_TIMESTAMP
		WHERE key = ? COLLATE NOCASE
	`

	result, err := vd.connection.Exec(query, value, key)
	if err != nil {
		return NewDatabaseError("update_secret", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return NewDatabaseError("update_secret_check", err)
	}

	if rowsAffected == 0 {
		return ErrKeyNotFound
	}

	return nil
}

// DeleteSecret removes a secret from the vault
func (vd *VaultDatabase) DeleteSecret(key string) error {
	if err := vd.ensureConnected(); err != nil {
		return err
	}

	query := `DELETE FROM secrets WHERE key = ? COLLATE NOCASE`

	result, err := vd.connection.Exec(query, key)
	if err != nil {
		return NewDatabaseError("delete_secret", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return NewDatabaseError("delete_secret_check", err)
	}

	if rowsAffected == 0 {
		return ErrKeyNotFound
	}

	return nil
}

// ListSecrets returns all secrets for search and display (without values for security)
func (vd *VaultDatabase) ListSecrets() ([]SearchResult, error) {
	if err := vd.ensureConnected(); err != nil {
		return nil, err
	}

	query := `
		SELECT key, created_at, last_accessed, access_count, tags
		FROM secrets
		ORDER BY last_accessed DESC, key ASC
	`

	rows, err := vd.connection.Query(query)
	if err != nil {
		return nil, NewDatabaseError("list_secrets", err)
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var result SearchResult
		err := rows.Scan(
			&result.Key,
			&result.CreatedAt,
			&result.LastAccessed,
			&result.AccessCount,
			&result.Tags,
		)
		if err != nil {
			return nil, NewDatabaseError("scan_secret_list", err)
		}
		results = append(results, result)
	}

	if err = rows.Err(); err != nil {
		return nil, NewDatabaseError("list_secrets_iteration", err)
	}

	return results, nil
}

// SearchSecrets performs fuzzy search on secret keys
func (vd *VaultDatabase) SearchSecrets(pattern string) ([]SearchResult, error) {
	if err := vd.ensureConnected(); err != nil {
		return nil, err
	}

	// Use LIKE for basic pattern matching (fuzzy search logic will be in search package)
	query := `
		SELECT key, created_at, last_accessed, access_count, tags
		FROM secrets
		WHERE key LIKE ? COLLATE NOCASE
		ORDER BY
			CASE
				WHEN key = ? COLLATE NOCASE THEN 1
				WHEN key LIKE ? || '%' COLLATE NOCASE THEN 2
				ELSE 3
			END,
			last_accessed DESC,
			key ASC
		LIMIT 100
	`

	likePattern := "%" + pattern + "%"
	prefixPattern := pattern

	rows, err := vd.connection.Query(query, likePattern, pattern, prefixPattern)
	if err != nil {
		return nil, NewDatabaseError("search_secrets", err)
	}
	defer rows.Close()

	var results []SearchResult
	for rows.Next() {
		var result SearchResult
		err := rows.Scan(
			&result.Key,
			&result.CreatedAt,
			&result.LastAccessed,
			&result.AccessCount,
			&result.Tags,
		)
		if err != nil {
			return nil, NewDatabaseError("scan_search_results", err)
		}
		results = append(results, result)
	}

	if err = rows.Err(); err != nil {
		return nil, NewDatabaseError("search_secrets_iteration", err)
	}

	return results, nil
}

// LogAuthAttempt records an authentication attempt
func (vd *VaultDatabase) LogAuthAttempt(username string, success bool, ipAddress *string, sessionID *string) error {
	if err := vd.ensureConnected(); err != nil {
		return err
	}

	query := `
		INSERT INTO auth_attempts (timestamp, username, success, ip_address, session_id)
		VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?)
	`

	_, err := vd.connection.Exec(query, username, success, ipAddress, sessionID)
	if err != nil {
		return NewDatabaseError("log_auth_attempt", err)
	}

	return nil
}

// validateKey validates a secret key according to the application rules
func validateKey(key string) error {
	if len(key) == 0 {
		return ErrInvalidKey
	}

	if len(key) > MaxKeyLength {
		return ErrInvalidKey
	}

	// Check for valid characters (alphanumeric + common punctuation)
	for _, r := range key {
		if !isValidKeyChar(r) {
			return ErrInvalidKey
		}
	}

	return nil
}

// isValidKeyChar checks if a character is valid for use in a key
func isValidKeyChar(r rune) bool {
	// Allow alphanumeric characters
	if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
		return true
	}

	// Allow common punctuation
	validPunct := ".-_:/@#$%^&*+=[]{}|\\;\"'<>?~`"
	for _, valid := range validPunct {
		if r == valid {
			return true
		}
	}

	return false
}
