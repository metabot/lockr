package database

import (
	"time"
)

// Secret represents a stored secret entry
type Secret struct {
	ID           int64     `json:"id"`
	Key          string    `json:"key"`
	Value        string    `json:"value"`
	CreatedAt    time.Time `json:"created_at"`
	LastAccessed time.Time `json:"last_accessed"`
	AccessCount  int64     `json:"access_count"`
	Tags         *string   `json:"tags,omitempty"`
	Notes        *string   `json:"notes,omitempty"`
}

// AuthAttempt represents an authentication attempt log entry
type AuthAttempt struct {
	ID        int64     `json:"id"`
	Timestamp time.Time `json:"timestamp"`
	Username  string    `json:"username"`
	Success   bool      `json:"success"`
	IPAddress *string   `json:"ip_address,omitempty"`
	SessionID *string   `json:"session_id,omitempty"`
}

// Session represents an active session
type Session struct {
	ID           int64     `json:"id"`
	SessionID    string    `json:"session_id"`
	CreatedAt    time.Time `json:"created_at"`
	ExpiresAt    time.Time `json:"expires_at"`
	LastActivity time.Time `json:"last_activity"`
}

// SearchResult represents a secret entry for search operations
type SearchResult struct {
	Key          string    `json:"key"`
	CreatedAt    time.Time `json:"created_at"`
	LastAccessed time.Time `json:"last_accessed"`
	AccessCount  int64     `json:"access_count"`
	Tags         *string   `json:"tags,omitempty"`
}
