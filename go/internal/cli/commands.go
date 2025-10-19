package cli

import (
	"crypto/rand"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/lockr/go/internal/clipboard"
	"github.com/lockr/go/internal/database"
	"github.com/lockr/go/internal/search"
)

// getCmd represents the get command for retrieving secrets
var getCmd = &cobra.Command{
	Use:   "get [key]",
	Short: "Retrieve a secret by key",
	Long: `Retrieve a secret from the vault by its key. If no key is provided,
opens an interactive fuzzy search interface.

Examples:
  lockr get mykey          # Get secret for 'mykey'
  lockr get                # Interactive search
  lockr get --no-copy     # Get secret without copying to clipboard`,
	Args: cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if err := ensureAuthenticated(); err != nil {
			handleError(err, "Authentication failed")
			return
		}

		var key string
		var err error

		if len(args) == 0 {
			// Interactive mode
			key, err = interactiveGet()
			if err != nil {
				handleError(err, "Interactive search failed")
				return
			}
			if key == "" {
				fmt.Println("No selection made")
				return
			}
		} else {
			key = args[0]
		}

		// Retrieve the secret
		secret, err := vaultDB.GetSecret(key)
		if err != nil {
			handleError(err, fmt.Sprintf("Failed to get secret '%s'", key))
			return
		}

		// Handle clipboard operations
		noCopy, _ := cmd.Flags().GetBool("no-copy")
		if !noCopy && clipboardMgr != nil {
			if err := clipboardMgr.CopySecretWithNotification(secret.Value); err != nil {
				fmt.Fprintf(os.Stderr, "Warning: failed to copy to clipboard: %v\n", err)
				fmt.Printf("Secret: %s\n", secret.Value)
			}
		} else {
			fmt.Printf("Secret: %s\n", secret.Value)
		}

		printVerbose("Retrieved secret for key '%s' (accessed %d times)", key, secret.AccessCount)
	},
}

// setCmd represents the set command for storing/updating secrets
var setCmd = &cobra.Command{
	Use:   "set <key>",
	Short: "Store or update a secret",
	Long: `Store a new secret in the vault or update an existing one.
Secret value is always read securely from stdin (hidden input).

Examples:
  lockr set mykey                   # Prompt for secret value (hidden input)
  lockr set -g mykey                # Auto-generate a random secret
  lockr set -g -l 32 mykey          # Generate 32-character secret
  lockr set -f -g mykey             # Force update with generated secret`,
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if err := ensureAuthenticated(); err != nil {
			handleError(err, "Authentication failed")
			return
		}

		key := args[0]
		var value string

		generate, _ := cmd.Flags().GetBool("generate")

		if generate {
			// Auto-generate a random secret
			length, _ := cmd.Flags().GetInt("length")
			var err error
			value, err = generateSecret(length)
			if err != nil {
				handleError(err, "Failed to generate secret")
				return
			}
			// Copy to clipboard without displaying
			if clipboardMgr != nil {
				if err := clipboardMgr.CopySecretWithNotification(value); err != nil {
					handleError(err, "Failed to copy generated secret to clipboard")
					return
				}
			} else {
				handleError(fmt.Errorf("clipboard not available"), "Cannot generate secret without clipboard support")
				return
			}
		} else {
			// Read value securely with hidden input
			var err error
			value, err = promptPassword("Enter secret value: ")
			if err != nil {
				handleError(err, "Failed to read secret value")
				return
			}
			if value == "" {
				handleError(fmt.Errorf("secret value cannot be empty"), "")
				return
			}
		}

		// Try to create the secret first
		err := vaultDB.CreateSecret(key, value)
		if err == database.ErrDuplicateKey {
			// Key exists, ask for update confirmation
			if !force {
				fmt.Printf("Secret '%s' already exists. Update it? (y/N): ", key)
				var response string
				fmt.Scanln(&response)
				if strings.ToLower(response) != "y" && strings.ToLower(response) != "yes" {
					fmt.Println("Cancelled")
					return
				}
			}

			// Update existing secret
			if err := vaultDB.UpdateSecret(key, value); err != nil {
				handleError(err, fmt.Sprintf("Failed to update secret '%s'", key))
				return
			}
			fmt.Printf("Secret '%s' updated successfully\n", key)
			printVerbose("Updated secret with key '%s'", key)
		} else if err != nil {
			handleError(err, fmt.Sprintf("Failed to store secret '%s'", key))
			return
		} else {
			fmt.Printf("Secret '%s' stored successfully\n", key)
			printVerbose("Stored new secret with key '%s'", key)
		}
	},
}

// deleteCmd represents the delete command for removing secrets
var deleteCmd = &cobra.Command{
	Use:   "delete <key>",
	Short: "Delete a secret from the vault",
	Long: `Permanently delete a secret from the vault by its key.

Examples:
  lockr delete mykey
  lockr delete -f mykey    # Force delete without confirmation`,
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if err := ensureAuthenticated(); err != nil {
			handleError(err, "Authentication failed")
			return
		}

		key := args[0]

		// Confirmation check
		if !force {
			fmt.Printf("Are you sure you want to delete secret '%s'? (y/N): ", key)
			var response string
			fmt.Scanln(&response)
			if strings.ToLower(response) != "y" && strings.ToLower(response) != "yes" {
				fmt.Println("Cancelled")
				return
			}
		}

		// Delete the secret
		if err := vaultDB.DeleteSecret(key); err != nil {
			handleError(err, fmt.Sprintf("Failed to delete secret '%s'", key))
			return
		}

		fmt.Printf("Secret '%s' deleted successfully\n", key)
		printVerbose("Deleted secret with key '%s'", key)
	},
}

// listCmd represents the list/search command for showing secrets
var listCmd = &cobra.Command{
	Use:   "list [pattern]",
	Short: "List or search secret keys",
	Long: `List all secret keys in the vault or search with a pattern using fuzzy matching.

Examples:
  lockr list                     # List all secrets
  lockr list api                 # Search for keys matching "api"
  lockr list --format table      # List in table format
  lockr list --limit 10 user     # Search and limit to 10 results`,
	Args: cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if err := ensureAuthenticated(); err != nil {
			handleError(err, "Authentication failed")
			return
		}

		// Get all secrets
		secrets, err := vaultDB.ListSecrets()
		if err != nil {
			handleError(err, "Failed to list secrets")
			return
		}

		if len(secrets) == 0 {
			fmt.Println("No secrets stored in vault")
			return
		}

		// If pattern provided, perform search
		if len(args) > 0 {
			pattern := args[0]
			limit, _ := cmd.Flags().GetInt("limit")
			if limit == 0 {
				limit = 100 // Default limit for search
			}

			// Perform fuzzy search
			engine := search.NewEngine()
			matches := engine.SearchInteractive(pattern, secrets, limit)

			if len(matches) == 0 {
				fmt.Printf("No matches found for pattern '%s'\n", pattern)
				return
			}

			fmt.Printf("Found %d matches for pattern '%s':\n\n", len(matches), pattern)
			for i, match := range matches {
				fmt.Printf("%d. %s (score: %.1f, accessed: %d times)\n",
					i+1, match.Result.Key, match.Score, match.Result.AccessCount)
			}
			return
		}

		// List all secrets
		format, _ := cmd.Flags().GetString("format")
		switch format {
		case "table":
			printSecretsTable(secrets)
		case "json":
			printSecretsJSON(secrets)
		default:
			printSecretsList(secrets)
		}

		fmt.Printf("\nTotal: %d secrets\n", len(secrets))
	},
}

// statusCmd represents the status command for showing session info
var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show vault and session status",
	Long: `Display information about the vault database, current session,
and system capabilities.`,
	Run: func(cmd *cobra.Command, args []string) {
		// Check if vault file exists
		fmt.Printf("Vault Status:\n")
		fmt.Printf("  Path: %s\n", vaultPath)

		if _, err := os.Stat(vaultPath); os.IsNotExist(err) {
			fmt.Printf("  Status: Not initialized\n")
		} else {
			fmt.Printf("  Status: Available\n")

			// If authenticated, show more details
			if sessionMgr.IsAuthenticated() {
				sessionInfo := sessionMgr.GetSessionInfo()
				fmt.Printf("  Connected: Yes\n")
				fmt.Printf("  Session expires in: %v\n", sessionInfo.TimeRemaining)

				// Show secret count
				if secrets, err := vaultDB.ListSecrets(); err == nil {
					fmt.Printf("  Secrets count: %d\n", len(secrets))
				}
			} else {
				fmt.Printf("  Connected: No\n")
			}
		}

		// Clipboard status
		fmt.Printf("\nClipboard Status:\n")
		if clipboardMgr != nil {
			status := clipboardMgr.GetStatus()
			fmt.Printf("  Supported: %v\n", status["supported"])
			fmt.Printf("  Platform: %v\n", status["platform"])
			fmt.Printf("  Auto-clear: %v\n", status["auto_clear"])
			fmt.Printf("  Clear delay: %v\n", status["clear_delay"])
		} else {
			fmt.Printf("  Supported: %v\n", clipboard.IsSupported())
			fmt.Printf("  Enabled: No (--no-clipboard flag used)\n")
		}

		// System info
		fmt.Printf("\nSystem Info:\n")
		fmt.Printf("  Verbose mode: %v\n", verbose)
		fmt.Printf("  Config path: %s\n", configPath)
	},
}

// versionCmd represents the version command
var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Show version information",
	Long:  `Display version information for the Lockr CLI.`,
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("lockr version %s\n", getVersion())
		if getCommit() != "unknown" {
			fmt.Printf("commit: %s\n", getCommit())
		}
		if getBuildTime() != "unknown" {
			fmt.Printf("built: %s\n", getBuildTime())
		}
	},
}

// initCmd represents the init command for creating a new vault
var initCmd = &cobra.Command{
	Use:   "init",
	Short: "Initialize a new vault",
	Long: `Create a new encrypted vault database with the specified password.

Examples:
  lockr init                # Initialize with password prompt
  lockr init --force        # Overwrite existing vault`,
	Run: func(cmd *cobra.Command, args []string) {
		// Check if vault already exists
		if _, err := os.Stat(vaultPath); err == nil {
			force, _ := cmd.Flags().GetBool("force")
			if !force {
				fmt.Printf("Vault already exists at %s\nUse --force to overwrite\n", vaultPath)
				return
			}
		}

		// Ensure vault directory exists
		if err := ensureVaultDirectory(); err != nil {
			handleError(err, "Failed to create vault directory")
			return
		}

		// Prompt for password
		password, err := promptPassword("Enter new vault password: ")
		if err != nil {
			handleError(err, "Failed to read password")
			return
		}

		// Create and initialize the vault
		if err := vaultDB.Connect(password); err != nil {
			handleError(err, "Failed to initialize vault")
			return
		}

		fmt.Printf("Vault initialized successfully at %s\n", vaultPath)
		printVerbose("Created new vault database")
	},
}

// Command flag initialization
func init() {
	// get command flags
	getCmd.Flags().Bool("no-copy", false, "Don't copy secret to clipboard")

	// set command flags
	setCmd.Flags().BoolP("generate", "g", false, "Auto-generate a random secret")
	setCmd.Flags().IntP("length", "l", 24, "Length of generated secret")

	// list command flags (merged with search)
	listCmd.Flags().String("format", "list", "Output format: list, table, json")
	listCmd.Flags().String("sort", "accessed", "Sort by: key, created, accessed")
	listCmd.Flags().Int("limit", 20, "Maximum number of search results to show")
}

// interactiveGet runs the interactive search interface
func interactiveGet() (string, error) {
	// Get all secrets for search
	secrets, err := vaultDB.ListSecrets()
	if err != nil {
		return "", fmt.Errorf("failed to retrieve secrets: %w", err)
	}

	if len(secrets) == 0 {
		fmt.Println("No secrets stored in vault")
		return "", nil
	}

	// Run interactive search
	return search.RunInteractiveSearch(secrets)
}

// printSecretsList prints secrets in a simple list format
func printSecretsList(secrets []database.SearchResult) {
	for _, secret := range secrets {
		fmt.Printf("%-30s (accessed %d times, created %s)\n",
			secret.Key,
			secret.AccessCount,
			secret.CreatedAt.Format("2006-01-02"))
	}
}

// printSecretsTable prints secrets in a table format
func printSecretsTable(secrets []database.SearchResult) {
	fmt.Printf("%-30s %-12s %-12s %-8s\n", "KEY", "CREATED", "ACCESSED", "COUNT")
	fmt.Printf("%-30s %-12s %-12s %-8s\n", strings.Repeat("-", 30), strings.Repeat("-", 12), strings.Repeat("-", 12), strings.Repeat("-", 8))

	for _, secret := range secrets {
		fmt.Printf("%-30s %-12s %-12s %-8d\n",
			truncateString(secret.Key, 30),
			secret.CreatedAt.Format("2006-01-02"),
			secret.LastAccessed.Format("2006-01-02"),
			secret.AccessCount)
	}
}

// printSecretsJSON prints secrets in JSON format
func printSecretsJSON(secrets []database.SearchResult) {
	fmt.Println("[")
	for i, secret := range secrets {
		fmt.Printf("  {\n")
		fmt.Printf("    \"key\": \"%s\",\n", secret.Key)
		fmt.Printf("    \"created_at\": \"%s\",\n", secret.CreatedAt.Format(time.RFC3339))
		fmt.Printf("    \"last_accessed\": \"%s\",\n", secret.LastAccessed.Format(time.RFC3339))
		fmt.Printf("    \"access_count\": %d\n", secret.AccessCount)
		if i == len(secrets)-1 {
			fmt.Printf("  }\n")
		} else {
			fmt.Printf("  },\n")
		}
	}
	fmt.Println("]")
}

// truncateString truncates a string to the specified length
func truncateString(s string, length int) string {
	if len(s) <= length {
		return s
	}
	return s[:length-3] + "..."
}

// Version information functions (these would be set by build flags)
var (
	versionInfo = struct {
		version string
		commit  string
		date    string
	}{
		version: "dev",
		commit:  "unknown",
		date:    "unknown",
	}
)

func getVersion() string {
	return versionInfo.version
}

func getBuildTime() string {
	return versionInfo.date
}

func getCommit() string {
	return versionInfo.commit
}

// generateSecret generates a cryptographically secure random secret
func generateSecret(length int) (string, error) {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>?"

	if length < 8 {
		return "", fmt.Errorf("secret length must be at least 8 characters")
	}
	if length > 256 {
		return "", fmt.Errorf("secret length must not exceed 256 characters")
	}

	secret := make([]byte, length)
	charsetLen := len(charset)

	for i := range secret {
		// Generate a random byte
		randomBytes := make([]byte, 1)
		if _, err := rand.Read(randomBytes); err != nil {
			return "", fmt.Errorf("failed to generate random bytes: %w", err)
		}

		// Map the random byte to a character in the charset
		secret[i] = charset[int(randomBytes[0])%charsetLen]
	}

	return string(secret), nil
}
