package keyring

import "errors"

var (
	// ErrKeyringDisabled is returned when keyring is disabled
	ErrKeyringDisabled = errors.New("keyring is disabled")

	// ErrPasswordNotFound is returned when the password is not found in the keyring
	ErrPasswordNotFound = errors.New("password not found in keyring")

	// ErrKeyringNotSupported is returned when keyring is not supported on the system
	ErrKeyringNotSupported = errors.New("keyring is not supported on this system")
)
