package database

import (
	"errors"
	"fmt"
)

var (
	// ErrAuthenticationFailed indicates incorrect password or authentication failure
	ErrAuthenticationFailed = errors.New("authentication failed: incorrect password")

	// ErrDatabaseLocked indicates the database is locked or encrypted
	ErrDatabaseLocked = errors.New("database is locked or encrypted")

	// ErrKeyNotFound indicates the requested key does not exist
	ErrKeyNotFound = errors.New("key not found")

	// ErrDuplicateKey indicates the key already exists
	ErrDuplicateKey = errors.New("key already exists")

	// ErrInvalidKey indicates the key format is invalid
	ErrInvalidKey = errors.New("invalid key format")

	// ErrDatabaseNotConnected indicates no active database connection
	ErrDatabaseNotConnected = errors.New("database not connected")

	// ErrSessionExpired indicates the session has expired
	ErrSessionExpired = errors.New("session has expired")

	// ErrInvalidSession indicates the session is invalid
	ErrInvalidSession = errors.New("invalid session")
)

// DatabaseError wraps database operation errors with additional context
type DatabaseError struct {
	Operation string
	Err       error
}

func (e *DatabaseError) Error() string {
	return fmt.Sprintf("database operation '%s' failed: %v", e.Operation, e.Err)
}

func (e *DatabaseError) Unwrap() error {
	return e.Err
}

// NewDatabaseError creates a new DatabaseError
func NewDatabaseError(operation string, err error) *DatabaseError {
	return &DatabaseError{
		Operation: operation,
		Err:       err,
	}
}
