package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var keyringCmd = &cobra.Command{
	Use:   "keyring",
	Short: "Manage keyring integration",
	Long:  `Manage system keyring integration for storing vault passwords securely.`,
}

var keyringStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show keyring status",
	Long:  `Display the current status of keyring integration.`,
	Run: func(cmd *cobra.Command, args []string) {
		km := sessionMgr.GetKeyringManager()

		fmt.Println("Keyring Status:")
		fmt.Printf("  Service: %s\n", km.GetServiceName())
		fmt.Printf("  Username: %s\n", km.GetUsername())
		fmt.Printf("  Enabled: %t\n", km.IsEnabled())
		fmt.Printf("  Has Stored Password: %t\n", km.HasPassword())
	},
}

var keyringSetCmd = &cobra.Command{
	Use:   "set",
	Short: "Save vault password to keyring",
	Long:  `Save the vault password to the system keyring for automatic authentication.`,
	Run: func(cmd *cobra.Command, args []string) {
		km := sessionMgr.GetKeyringManager()

		if !km.IsEnabled() {
			fmt.Println("Keyring is disabled")
			return
		}

		if km.HasPassword() {
			if !force {
				fmt.Print("Password already stored. Overwrite? (y/N): ")
				var response string
				fmt.Scanln(&response)
				if response != "y" && response != "Y" {
					fmt.Println("Cancelled")
					return
				}
			}
		}

		password, err := promptPassword("Enter vault password to store: ")
		if err != nil {
			handleError(err, "Failed to read password")
			return
		}

		// Verify the password works by attempting to connect
		if err := vaultDB.Connect(password); err != nil {
			handleError(err, "Invalid password")
			return
		}
		vaultDB.Close()

		if err := km.SavePassword(password); err != nil {
			handleError(err, "Failed to save password to keyring")
			return
		}

		fmt.Println("Password saved to keyring successfully")
	},
}

var keyringClearCmd = &cobra.Command{
	Use:   "clear",
	Short: "Remove vault password from keyring",
	Long:  `Remove the stored vault password from the system keyring.`,
	Run: func(cmd *cobra.Command, args []string) {
		km := sessionMgr.GetKeyringManager()

		if !km.HasPassword() {
			fmt.Println("No password stored in keyring")
			return
		}

		if !force {
			fmt.Print("Remove password from keyring? (y/N): ")
			var response string
			fmt.Scanln(&response)
			if response != "y" && response != "Y" {
				fmt.Println("Cancelled")
				return
			}
		}

		if err := km.DeletePassword(); err != nil {
			handleError(err, "Failed to remove password from keyring")
			return
		}

		fmt.Println("Password removed from keyring successfully")
	},
}

var keyringEnableCmd = &cobra.Command{
	Use:   "enable",
	Short: "Enable keyring integration",
	Long:  `Enable keyring integration for automatic authentication.`,
	Run: func(cmd *cobra.Command, args []string) {
		km := sessionMgr.GetKeyringManager()
		km.Enable()
		fmt.Println("Keyring integration enabled")
	},
}

var keyringDisableCmd = &cobra.Command{
	Use:   "disable",
	Short: "Disable keyring integration",
	Long:  `Disable keyring integration. This does not remove stored passwords.`,
	Run: func(cmd *cobra.Command, args []string) {
		km := sessionMgr.GetKeyringManager()
		km.Disable()
		fmt.Println("Keyring integration disabled")
		fmt.Println("Note: Stored password was not removed. Use 'lockr keyring clear' to remove it.")
	},
}

func init() {
	keyringCmd.AddCommand(keyringStatusCmd)
	keyringCmd.AddCommand(keyringSetCmd)
	keyringCmd.AddCommand(keyringClearCmd)
	keyringCmd.AddCommand(keyringEnableCmd)
	keyringCmd.AddCommand(keyringDisableCmd)
}
