package clipboard

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"time"
)

const (
	// DefaultClearDelay is the default time to wait before clearing clipboard
	DefaultClearDelay = 60 * time.Second

	// MaxClipboardSize is the maximum size of data we'll copy to clipboard (for safety)
	MaxClipboardSize = 1024 * 1024 // 1MB
)

// Manager handles clipboard operations with auto-clear functionality
type Manager struct {
	clearDelay time.Duration
	clearTimer *time.Timer
	lastCopy   string
}

// NewManager creates a new clipboard manager with default settings
func NewManager() *Manager {
	return &Manager{
		clearDelay: DefaultClearDelay,
	}
}

// SetClearDelay configures how long to wait before auto-clearing clipboard
func (m *Manager) SetClearDelay(delay time.Duration) {
	m.clearDelay = delay
}

// Copy copies the given text to the system clipboard with auto-clear
func (m *Manager) Copy(text string) error {
	if len(text) > MaxClipboardSize {
		return fmt.Errorf("clipboard content too large: %d bytes (max %d)", len(text), MaxClipboardSize)
	}

	// Cancel any existing clear timer
	if m.clearTimer != nil {
		m.clearTimer.Stop()
	}

	// Copy to system clipboard
	if err := m.copyToSystem(text); err != nil {
		return fmt.Errorf("failed to copy to clipboard: %w", err)
	}

	// Store the text we copied for verification during clear
	m.lastCopy = text

	// Set up auto-clear timer if delay is positive
	if m.clearDelay > 0 {
		m.clearTimer = time.AfterFunc(m.clearDelay, func() {
			if err := m.clearIfUnchanged(); err != nil {
				// Log error but don't fail - this is a background operation
				fmt.Fprintf(os.Stderr, "Warning: failed to auto-clear clipboard: %v\n", err)
			}
		})
	}

	return nil
}

// CopyWithCustomDelay copies text and sets a custom clear delay for this operation
func (m *Manager) CopyWithCustomDelay(text string, delay time.Duration) error {
	oldDelay := m.clearDelay
	m.SetClearDelay(delay)
	err := m.Copy(text)
	m.SetClearDelay(oldDelay)
	return err
}

// Clear immediately clears the clipboard
func (m *Manager) Clear() error {
	// Cancel any pending auto-clear
	if m.clearTimer != nil {
		m.clearTimer.Stop()
		m.clearTimer = nil
	}

	// Clear the system clipboard
	if err := m.clearSystem(); err != nil {
		return fmt.Errorf("failed to clear clipboard: %w", err)
	}

	m.lastCopy = ""
	return nil
}

// GetContent retrieves the current clipboard content
func (m *Manager) GetContent() (string, error) {
	content, err := m.getFromSystem()
	if err != nil {
		return "", fmt.Errorf("failed to get clipboard content: %w", err)
	}
	return content, nil
}

// clearIfUnchanged clears the clipboard only if it still contains our last copied text
func (m *Manager) clearIfUnchanged() error {
	if m.lastCopy == "" {
		return nil // Nothing to clear
	}

	// Check current clipboard content
	current, err := m.GetContent()
	if err != nil {
		// If we can't read clipboard, err on the side of caution and don't clear
		return fmt.Errorf("cannot verify clipboard content: %w", err)
	}

	// Only clear if the clipboard still contains what we put there
	if current == m.lastCopy {
		return m.Clear()
	}

	// Clipboard content has changed - user has copied something else
	m.lastCopy = ""
	return nil
}

// copyToSystem copies text to the system clipboard (platform-specific)
func (m *Manager) copyToSystem(text string) error {
	switch runtime.GOOS {
	case "darwin":
		return m.copyDarwin(text)
	case "linux":
		return m.copyLinux(text)
	case "windows":
		return m.copyWindows(text)
	default:
		return fmt.Errorf("unsupported platform: %s", runtime.GOOS)
	}
}

// getFromSystem gets text from the system clipboard (platform-specific)
func (m *Manager) getFromSystem() (string, error) {
	switch runtime.GOOS {
	case "darwin":
		return m.getDarwin()
	case "linux":
		return m.getLinux()
	case "windows":
		return m.getWindows()
	default:
		return "", fmt.Errorf("unsupported platform: %s", runtime.GOOS)
	}
}

// clearSystem clears the system clipboard (platform-specific)
func (m *Manager) clearSystem() error {
	switch runtime.GOOS {
	case "darwin":
		return m.clearDarwin()
	case "linux":
		return m.clearLinux()
	case "windows":
		return m.clearWindows()
	default:
		return fmt.Errorf("unsupported platform: %s", runtime.GOOS)
	}
}

// macOS implementations using pbcopy/pbpaste
func (m *Manager) copyDarwin(text string) error {
	cmd := exec.Command("pbcopy")
	cmd.Stdin = nil

	// Use a pipe to send the text
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		stdin.Close()
		return err
	}

	_, err = stdin.Write([]byte(text))
	stdin.Close()

	if err != nil {
		cmd.Wait()
		return err
	}

	return cmd.Wait()
}

func (m *Manager) getDarwin() (string, error) {
	cmd := exec.Command("pbpaste")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

func (m *Manager) clearDarwin() error {
	return m.copyDarwin("")
}

// Linux implementations using xclip
func (m *Manager) copyLinux(text string) error {
	// Try xclip first
	cmd := exec.Command("xclip", "-selection", "clipboard")
	cmd.Stdin = nil

	stdin, err := cmd.StdinPipe()
	if err != nil {
		// Fallback to xsel
		return m.copyLinuxXsel(text)
	}

	if err := cmd.Start(); err != nil {
		stdin.Close()
		return m.copyLinuxXsel(text)
	}

	_, err = stdin.Write([]byte(text))
	stdin.Close()

	if err != nil {
		cmd.Wait()
		return m.copyLinuxXsel(text)
	}

	return cmd.Wait()
}

func (m *Manager) copyLinuxXsel(text string) error {
	cmd := exec.Command("xsel", "--clipboard", "--input")
	cmd.Stdin = nil

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		stdin.Close()
		return err
	}

	_, err = stdin.Write([]byte(text))
	stdin.Close()

	if err != nil {
		cmd.Wait()
		return err
	}

	return cmd.Wait()
}

func (m *Manager) getLinux() (string, error) {
	// Try xclip first
	cmd := exec.Command("xclip", "-selection", "clipboard", "-output")
	output, err := cmd.Output()
	if err == nil {
		return string(output), nil
	}

	// Fallback to xsel
	cmd = exec.Command("xsel", "--clipboard", "--output")
	output, err = cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

func (m *Manager) clearLinux() error {
	return m.copyLinux("")
}

// Windows implementations using PowerShell
func (m *Manager) copyWindows(text string) error {
	cmd := exec.Command("powershell", "-command", "Set-Clipboard", "-Value", text)
	return cmd.Run()
}

func (m *Manager) getWindows() (string, error) {
	cmd := exec.Command("powershell", "-command", "Get-Clipboard")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

func (m *Manager) clearWindows() error {
	return m.copyWindows("")
}

// IsSupported returns true if clipboard operations are supported on this platform
func IsSupported() bool {
	switch runtime.GOOS {
	case "darwin":
		return isCommandAvailable("pbcopy") && isCommandAvailable("pbpaste")
	case "linux":
		return isCommandAvailable("xclip") || isCommandAvailable("xsel")
	case "windows":
		return isCommandAvailable("powershell")
	default:
		return false
	}
}

// isCommandAvailable checks if a command is available in PATH
func isCommandAvailable(command string) bool {
	_, err := exec.LookPath(command)
	return err == nil
}

// CopySecretWithNotification copies a secret to clipboard and shows user feedback
func (m *Manager) CopySecretWithNotification(secret string) error {
	if err := m.Copy(secret); err != nil {
		return err
	}

	// Show user notification
	fmt.Printf("Secret copied to clipboard (will auto-clear in %v)\n", m.clearDelay)
	return nil
}

// GetStatus returns information about the clipboard manager state
func (m *Manager) GetStatus() map[string]interface{} {
	status := map[string]interface{}{
		"supported":    IsSupported(),
		"clear_delay":  m.clearDelay.String(),
		"auto_clear":   m.clearDelay > 0,
		"timer_active": m.clearTimer != nil,
	}

	// Add platform-specific information
	switch runtime.GOOS {
	case "darwin":
		status["platform"] = "macOS"
		status["commands"] = []string{"pbcopy", "pbpaste"}
	case "linux":
		status["platform"] = "Linux"
		commands := []string{}
		if isCommandAvailable("xclip") {
			commands = append(commands, "xclip")
		}
		if isCommandAvailable("xsel") {
			commands = append(commands, "xsel")
		}
		status["commands"] = commands
	case "windows":
		status["platform"] = "Windows"
		status["commands"] = []string{"powershell"}
	}

	return status
}
