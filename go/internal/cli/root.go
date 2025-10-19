package cli

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"golang.org/x/term"

	"github.com/lockr/go/internal/clipboard"
	"github.com/lockr/go/internal/database"
	"github.com/lockr/go/internal/session"
)

var (
	// Global flags
	vaultPath  string
	configPath string
	verbose    bool
	force      bool

	// Global instances
	vaultDB      *database.VaultDatabase
	sessionMgr   *session.Manager
	clipboardMgr *clipboard.Manager
)

// rootCmd represents the base command when called without any subcommands
var rootCmd = &cobra.Command{
	Use:   "lockr",
	Short: "A personal vault CLI for secure storage and retrieval of secrets",
	Long: `Lockr is a personal vault CLI application for secure storage and retrieval
of secrets (passwords, tokens, etc.) with interactive fuzzy search capabilities.

Features:
- SQLCipher encrypted storage
- Interactive fuzzy search
- Session-based authentication with timeout
- Automatic clipboard management
- Cross-platform support

Examples:
  lockr get                    # Interactive search and retrieve
  lockr set mykey              # Store/update with secure password prompt
  lockr set -g mykey           # Auto-generate a random secret
  lockr set -g -l 32 mykey     # Generate 32-character secret
  lockr list                   # List all keys
  lockr list api               # Search for keys matching "api"
  lockr delete -f mykey        # Force delete without prompt
  lockr status                 # Show session status`,
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		// Initialize global components
		initializeGlobals()
	},
	PersistentPostRun: func(cmd *cobra.Command, args []string) {
		// Cleanup
		if sessionMgr != nil {
			sessionMgr.Logout()
		}
	},
	CompletionOptions: cobra.CompletionOptions{
		DisableDefaultCmd: true,
	},
}

// SetVersion sets the version information for the CLI
func SetVersion(version, commit, date string) {
	versionInfo.version = version
	versionInfo.commit = commit
	versionInfo.date = date
}

// Execute adds all child commands to the root command and sets flags appropriately.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func init() {
	// Global flags
	rootCmd.PersistentFlags().StringVarP(&vaultPath, "vault", "v", getDefaultVaultPath(), "Path to vault database file")
	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", getDefaultConfigPath(), "Path to configuration file")
	rootCmd.PersistentFlags().BoolVarP(&force, "force", "f", false, "Force operation without confirmation")
	rootCmd.PersistentFlags().BoolVar(&verbose, "verbose", false, "Enable verbose output")

	// Define command groups
	rootCmd.AddGroup(&cobra.Group{ID: "management", Title: "Management Commands:"})
	rootCmd.AddGroup(&cobra.Group{ID: "secret", Title: "Secret Operations:"})

	// Secret operations
	getCmd.GroupID = "secret"
	setCmd.GroupID = "secret"
	deleteCmd.GroupID = "secret"

	// Management commands
	initCmd.GroupID = "management"
	listCmd.GroupID = "management"
	statusCmd.GroupID = "management"
	versionCmd.GroupID = "management"
	keyringCmd.GroupID = "management"

	// Add subcommands
	rootCmd.AddCommand(getCmd)
	rootCmd.AddCommand(setCmd)
	rootCmd.AddCommand(deleteCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(versionCmd)
	rootCmd.AddCommand(initCmd)
	rootCmd.AddCommand(keyringCmd)
}

// initializeGlobals initializes the global components
func initializeGlobals() {
	// Initialize database
	vaultDB = database.NewVaultDatabase(vaultPath)

	// Initialize session manager
	sessionMgr = session.NewManager(vaultDB)

	// Initialize clipboard manager
	if clipboard.IsSupported() {
		clipboardMgr = clipboard.NewManager()
	}

	if verbose {
		fmt.Printf("Vault path: %s\n", vaultPath)
		fmt.Printf("Config path: %s\n", configPath)
		fmt.Printf("Clipboard enabled: %t\n", clipboardMgr != nil)
	}
}

// getDefaultVaultPath returns the default path for the vault database
func getDefaultVaultPath() string {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "vault.lockr"
	}
	return filepath.Join(homeDir, ".lockr", "vault.lockr")
}

// getDefaultConfigPath returns the default path for the configuration file
func getDefaultConfigPath() string {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "config.yml"
	}
	return filepath.Join(homeDir, ".lockr", "config.yml")
}

// ensureAuthenticated ensures the user is authenticated, prompting if necessary
func ensureAuthenticated() error {
	if sessionMgr.IsAuthenticated() {
		// Refresh session on each operation
		return sessionMgr.RefreshSession()
	}

	// Try keyring authentication first
	err := sessionMgr.TryAuthenticateWithKeyring()
	if err == nil {
		printVerbose("Authenticated using keyring")
		return nil
	}

	// If keyring auth failed (not available or wrong password), prompt for password
	printVerbose("Keyring authentication failed: %v", err)
	password, err := promptPassword("Enter vault password: ")
	if err != nil {
		return fmt.Errorf("failed to read password: %w", err)
	}

	if err := sessionMgr.Authenticate(password); err != nil {
		return fmt.Errorf("authentication failed: %w", err)
	}

	return nil
}

// promptPassword prompts the user for a password with hidden input
func promptPassword(prompt string) (string, error) {
	fmt.Print(prompt)

	// Read password without echoing to terminal
	passwordBytes, err := term.ReadPassword(int(os.Stdin.Fd()))
	fmt.Println() // Print newline after password input

	if err != nil {
		return "", err
	}

	return string(passwordBytes), nil
}

// handleError handles errors with appropriate output and exit codes
func handleError(err error, message string) {
	if err == nil {
		return
	}

	if message != "" {
		fmt.Fprintf(os.Stderr, "%s: %v\n", message, err)
	} else {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
	}

	// Specific handling for common errors
	switch err {
	case database.ErrAuthenticationFailed:
		os.Exit(2)
	case database.ErrKeyNotFound:
		os.Exit(3)
	case database.ErrDuplicateKey:
		os.Exit(4)
	case database.ErrSessionExpired:
		os.Exit(5)
	default:
		os.Exit(1)
	}
}

// printVerbose prints verbose output if verbose mode is enabled
func printVerbose(format string, args ...interface{}) {
	if verbose {
		fmt.Printf("[DEBUG] "+format+"\n", args...)
	}
}

// ensureVaultDirectory ensures the vault directory exists
func ensureVaultDirectory() error {
	dir := filepath.Dir(vaultPath)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return fmt.Errorf("failed to create vault directory: %w", err)
	}
	return nil
}
