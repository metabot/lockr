# Next Steps for Homebrew Tap Release

## Summary

I've successfully set up Lockr for Homebrew distribution! Here's what has been completed:

### ✅ Completed Setup

1. **GoReleaser Configuration** (`.goreleaser.yml`)
   - Builds for macOS Intel and Apple Silicon
   - Automatically generates Homebrew formula
   - Includes version information in binaries
   - Creates release archives with checksums

2. **GitHub Actions Workflow** (`.github/workflows/release.yml`)
   - Triggers on git tags (e.g., `v0.1.0`)
   - Builds binaries automatically
   - Creates GitHub releases
   - Updates Homebrew tap repository

3. **Version Information**
   - Updated `go/cmd/lockr/main.go` to accept build-time version info
   - Updated `go/internal/cli/*.go` to display version correctly
   - `lockr version` now shows: version, commit, and build date

4. **Supporting Files**
   - Created `LICENSE` (MIT)
   - Updated `.gitignore` to exclude build artifacts
   - Created `README.md` with comprehensive documentation
   - Created `HOMEBREW_SETUP.md` with step-by-step instructions

5. **Local Testing**
   - Successfully built macOS binaries
   - Tested binary execution
   - Verified version information
   - Generated Homebrew formula

## 🚀 To Complete the Setup (3 Quick Steps)

### 1. Create `homebrew-tap` Repository

Go to GitHub and create a new public repository:
- URL: https://github.com/organizations/metabot/repositories/new
- Name: **`homebrew-tap`**
- Visibility: **Public**
- Leave it empty (no README)

### 2. Add GitHub Token Secret

1. Create Personal Access Token:
   - Go to: https://github.com/settings/tokens/new
   - Name: "GoReleaser Homebrew Tap"
   - Scopes: Check `repo` and `write:packages`
   - Click "Generate token" and copy it

2. Add to lockr repository:
   - Go to: https://github.com/metabot/lockr/settings/secrets/actions
   - Click "New repository secret"
   - Name: `HOMEBREW_TAP_GITHUB_TOKEN`
   - Value: [paste token]

### 3. Create First Release

```bash
cd /Users/jun/Workspaces/lockr

# Commit all changes
git add .
git commit -m "Add Homebrew tap distribution setup"
git push origin main

# Create and push release tag
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0
```

That's it! GitHub Actions will automatically:
- Build the binaries
- Create a GitHub release
- Update your Homebrew tap

## 📦 After Release, Users Can Install With:

```bash
brew tap metabot/tap
brew install lockr
```

## 📚 Documentation

- **[HOMEBREW_SETUP.md](HOMEBREW_SETUP.md)** - Detailed step-by-step guide
- **[docs/HOMEBREW_DISTRIBUTION.md](docs/HOMEBREW_DISTRIBUTION.md)** - Complete distribution guide
- **[README.md](README.md)** - Project documentation

## 🔍 What Was Built

Test the built binaries:
```bash
./dist/lockr_darwin_arm64_v8.0/lockr version
# Output: lockr version 0.0.1-next
#         commit: 8c0ec9e4a2e725c5ae754cd0994f59d28bfcf488
#         built: 2025-10-18T00:31:23Z
```

View generated Homebrew formula:
```bash
cat dist/homebrew/Formula/lockr.rb
```

## 🎯 Current Build Support

✅ macOS Intel (x86_64)
✅ macOS Apple Silicon (arm64)
⏳ Linux (future - requires Docker)
⏳ Windows (future - requires SQLCipher setup)

## 📞 Need Help?

Check the documentation files created:
- `HOMEBREW_SETUP.md` - Step-by-step instructions
- `docs/HOMEBREW_DISTRIBUTION.md` - Complete guide with troubleshooting

---

**Ready to release!** Just complete the 3 steps above and you'll have a working Homebrew tap.
