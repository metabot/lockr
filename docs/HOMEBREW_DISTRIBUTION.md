# Homebrew Distribution Guide

This guide covers the steps to distribute Lockr via Homebrew (not Homebrew Cask, which is for GUI apps).

## Overview

Homebrew distribution involves:
1. Setting up automated releases with binaries
2. Creating a Homebrew formula
3. Submitting to homebrew-core (or hosting your own tap)

## Prerequisites

- GitHub repository with proper releases
- GoReleaser for automated builds
- GPG key for signing (optional but recommended)

## Step 1: Set Up GoReleaser

GoReleaser automates the build and release process for Go applications.

### 1.1 Install GoReleaser

```bash
# macOS
brew install goreleaser

# Or download from https://github.com/goreleaser/goreleaser/releases
```

### 1.2 Create `.goreleaser.yml`

Create this file in the project root:

```yaml
# .goreleaser.yml
project_name: lockr

before:
  hooks:
    - go mod tidy
    - go mod download

builds:
  - id: lockr
    main: ./go/cmd/lockr
    binary: lockr
    env:
      - CGO_ENABLED=1
    goos:
      - darwin
      - linux
      - windows
    goarch:
      - amd64
      - arm64
    # CGO cross-compilation setup
    ldflags:
      - -s -w
      - -X main.version={{.Version}}
      - -X main.commit={{.Commit}}
      - -X main.date={{.Date}}
    # Platform-specific CGO settings
    overrides:
      - goos: darwin
        goarch: amd64
        env:
          - CC=o64-clang
          - CXX=o64-clang++
      - goos: darwin
        goarch: arm64
        env:
          - CC=oa64-clang
          - CXX=oa64-clang++
      - goos: linux
        goarch: amd64
        env:
          - CC=x86_64-linux-gnu-gcc
          - CXX=x86_64-linux-gnu-g++
      - goos: linux
        goarch: arm64
        env:
          - CC=aarch64-linux-gnu-gcc
          - CXX=aarch64-linux-gnu-g++

archives:
  - id: lockr
    format: tar.gz
    name_template: >-
      {{ .ProjectName }}_
      {{- .Version }}_
      {{- title .Os }}_
      {{- if eq .Arch "amd64" }}x86_64
      {{- else if eq .Arch "386" }}i386
      {{- else }}{{ .Arch }}{{ end }}
      {{- if .Arm }}v{{ .Arm }}{{ end }}
    format_overrides:
      - goos: windows
        format: zip
    files:
      - LICENSE*
      - README*
      - CHANGELOG*

checksum:
  name_template: 'checksums.txt'

snapshot:
  name_template: "{{ incpatch .Version }}-next"

changelog:
  sort: asc
  filters:
    exclude:
      - '^docs:'
      - '^test:'
      - '^chore:'
      - Merge pull request
      - Merge branch

# Homebrew tap (for your own tap)
brews:
  - name: lockr
    repository:
      owner: metabot
      name: homebrew-tap
      token: "{{ .Env.HOMEBREW_TAP_GITHUB_TOKEN }}"
    folder: Formula
    homepage: https://github.com/metabot/lockr
    description: "Secure personal vault CLI with interactive fuzzy search"
    license: MIT
    dependencies:
      - name: sqlcipher
        type: build
    test: |
      system "#{bin}/lockr", "version"
    install: |
      bin.install "lockr"

release:
  github:
    owner: metabot
    name: lockr
  draft: false
  prerelease: auto
```

### 1.3 Test GoReleaser Locally

```bash
# Test without publishing
goreleaser release --snapshot --clean

# Check generated artifacts
ls -la dist/
```

## Step 2: Set Up GitHub Actions for Automated Releases

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write
  packages: write

jobs:
  goreleaser:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24'

      - name: Install SQLCipher dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libsqlcipher-dev gcc-aarch64-linux-gnu

      - name: Run GoReleaser
        uses: goreleaser/goreleaser-action@v5
        with:
          distribution: goreleaser
          version: latest
          args: release --clean
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          HOMEBREW_TAP_GITHUB_TOKEN: ${{ secrets.HOMEBREW_TAP_GITHUB_TOKEN }}
```

## Step 3: Create a Homebrew Tap (Recommended First Step)

Before submitting to homebrew-core (which has strict requirements), create your own tap.

### 3.1 Create Tap Repository

```bash
# Create a new GitHub repository named: homebrew-tap
# (Must be named "homebrew-<something>")

# Clone it locally
git clone https://github.com/metabot/homebrew-tap.git
cd homebrew-tap

# Create Formula directory
mkdir -p Formula
```

### 3.2 Create Formula Manually (First Version)

Create `Formula/lockr.rb`:

```ruby
class Lockr < Formula
  desc "Secure personal vault CLI with interactive fuzzy search"
  homepage "https://github.com/metabot/lockr"
  version "0.1.0"
  license "MIT"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/metabot/lockr/releases/download/v0.1.0/lockr_0.1.0_Darwin_arm64.tar.gz"
      sha256 "REPLACE_WITH_ACTUAL_SHA256"
    else
      url "https://github.com/metabot/lockr/releases/download/v0.1.0/lockr_0.1.0_Darwin_x86_64.tar.gz"
      sha256 "REPLACE_WITH_ACTUAL_SHA256"
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/metabot/lockr/releases/download/v0.1.0/lockr_0.1.0_Linux_arm64.tar.gz"
      sha256 "REPLACE_WITH_ACTUAL_SHA256"
    else
      url "https://github.com/metabot/lockr/releases/download/v0.1.0/lockr_0.1.0_Linux_x86_64.tar.gz"
      sha256 "REPLACE_WITH_ACTUAL_SHA256"
    end
  end

  depends_on "sqlcipher" => :build

  def install
    bin.install "lockr"
  end

  test do
    system "#{bin}/lockr", "version"
  end
end
```

### 3.3 Calculate SHA256 Checksums

After creating a GitHub release:

```bash
# Download your release archives
curl -L https://github.com/metabot/lockr/releases/download/v0.1.0/lockr_0.1.0_Darwin_arm64.tar.gz -o darwin_arm64.tar.gz

# Calculate SHA256
shasum -a 256 darwin_arm64.tar.gz

# Repeat for all platforms
```

### 3.4 Push Tap to GitHub

```bash
cd homebrew-tap
git add Formula/lockr.rb
git commit -m "Add lockr formula v0.1.0"
git push origin main
```

## Step 4: Create Your First Release

### 4.1 Prepare Release

```bash
cd /path/to/lockr

# Ensure everything is committed
git add .
git commit -m "Prepare v0.1.0 release"
git push

# Create and push tag
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

### 4.2 GitHub Actions Will Automatically:

1. Build binaries for all platforms
2. Create checksums
3. Create GitHub release
4. Update your homebrew-tap (if configured in .goreleaser.yml)

### 4.3 Verify Release

```bash
# Check GitHub releases page
open https://github.com/metabot/lockr/releases

# Test installation from your tap
brew tap metabot/tap
brew install lockr

# Test the binary
lockr version
```

## Step 5: Submit to Homebrew Core (Optional)

Once your tap is stable and tested, you can submit to homebrew-core for wider distribution.

### 5.1 Prerequisites for homebrew-core

- Stable project (not alpha/beta)
- Active maintenance
- Significant user base
- Follows Homebrew guidelines
- No redundancy with existing formulas

### 5.2 Submission Process

1. Fork [Homebrew/homebrew-core](https://github.com/Homebrew/homebrew-core)

2. Create formula in `Formula/l/lockr.rb`:

```bash
cd homebrew-core
brew create https://github.com/metabot/lockr/archive/v0.1.0.tar.gz
```

3. Edit the generated formula:

```ruby
class Lockr < Formula
  desc "Secure personal vault CLI with interactive fuzzy search"
  homepage "https://github.com/metabot/lockr"
  url "https://github.com/metabot/lockr/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "ACTUAL_SHA256"
  license "MIT"

  depends_on "go" => :build
  depends_on "sqlcipher"

  def install
    cd "go" do
      system "go", "build", *std_go_args(ldflags: "-s -w"), "./cmd/lockr"
    end
  end

  test do
    system "#{bin}/lockr", "version"
  end
end
```

4. Test the formula:

```bash
brew install --build-from-source lockr
brew test lockr
brew audit --strict lockr
```

5. Create pull request to homebrew-core

6. Address review feedback

## Step 6: Maintenance and Updates

### 6.1 Release New Version

```bash
# Update version
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# GoReleaser will automatically update your tap
```

### 6.2 Manual Formula Update (if needed)

```bash
cd homebrew-tap
brew bump-formula-pr lockr --version=0.2.0
```

## Testing Checklist

Before each release:

- [ ] Test build on macOS (Intel and Apple Silicon)
- [ ] Test build on Linux (amd64 and arm64)
- [ ] Verify all dependencies are listed
- [ ] Test installation from tap
- [ ] Test basic functionality
- [ ] Update CHANGELOG
- [ ] Update version in README

## Troubleshooting

### CGO Cross-Compilation Issues

If you encounter CGO issues during cross-compilation:

```bash
# Install cross-compilation tools
brew install FiloSottile/musl-cross/musl-cross

# Use Docker for Linux builds
docker run --rm -v "$PWD":/app -w /app golang:1.24 \
  bash -c "apt-get update && apt-get install -y libsqlcipher-dev && go build -o lockr ./go/cmd/lockr"
```

### Formula Installation Fails

```bash
# Debug installation
brew install --verbose --debug lockr

# Check formula syntax
brew audit --strict lockr
```

## Resources

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [GoReleaser Documentation](https://goreleaser.com/intro/)
- [Acceptable Formulae](https://docs.brew.sh/Acceptable-Formulae)
- [Homebrew Core Guidelines](https://docs.brew.sh/How-To-Open-a-Homebrew-Pull-Request)

## Quick Start Summary

1. **Initial Setup** (one-time):
   ```bash
   # Install GoReleaser
   brew install goreleaser

   # Create homebrew-tap repository on GitHub
   # Add .goreleaser.yml to lockr repository
   # Add GitHub Actions workflow
   ```

2. **Create Release**:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   # GitHub Actions does the rest
   ```

3. **Users Install**:
   ```bash
   brew tap metabot/tap
   brew install lockr
   ```

4. **Later: Submit to homebrew-core** (for wider distribution)
