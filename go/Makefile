# Lockr Go Implementation Makefile

.PHONY: build test clean lint fmt deps run benchmark install

# Build configuration
BINARY_NAME=lockr
BUILD_DIR=./bin
CMD_DIR=./cmd/lockr
VERSION?=dev
BUILD_TIME=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
LDFLAGS=-ldflags="-X main.Version=${VERSION} -X main.BuildTime=${BUILD_TIME}"

# Go configuration
GO_FILES=$(shell find . -type f -name '*.go' -not -path './vendor/*')
GOPATH=$(shell go env GOPATH)

# Default target
all: fmt lint test build

# Build the binary
build:
	@echo "Building ${BINARY_NAME}..."
	@mkdir -p ${BUILD_DIR}
	CGO_ENABLED=1 go build ${LDFLAGS} -o ${BUILD_DIR}/${BINARY_NAME} ${CMD_DIR}
	@echo "Binary built: ${BUILD_DIR}/${BINARY_NAME}"

# Build for release (optimized)
build-release:
	@echo "Building ${BINARY_NAME} for release..."
	@mkdir -p ${BUILD_DIR}
	CGO_ENABLED=1 go build -a -installsuffix cgo ${LDFLAGS} -o ${BUILD_DIR}/${BINARY_NAME} ${CMD_DIR}
	@echo "Release binary built: ${BUILD_DIR}/${BINARY_NAME}"

# Install dependencies
deps:
	@echo "Installing dependencies..."
	go mod download
	go mod verify

# Run tests
test:
	@echo "Running tests..."
	go test -v -race -coverprofile=coverage.out ./...

# Run tests with coverage report
test-coverage: test
	@echo "Generating coverage report..."
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

# Run benchmarks
benchmark:
	@echo "Running benchmarks..."
	go test -bench=. -benchmem ./...

# Lint code
lint:
	@echo "Running linter..."
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run; \
	else \
		echo "golangci-lint not installed, skipping lint"; \
	fi

# Format code
fmt:
	@echo "Formatting code..."
	go fmt ./...
	@if command -v goimports >/dev/null 2>&1; then \
		goimports -w ${GO_FILES}; \
	fi

# Run the application
run: build
	@echo "Running ${BINARY_NAME}..."
	${BUILD_DIR}/${BINARY_NAME}

# Run with arguments
run-args: build
	@echo "Running ${BINARY_NAME} with args: ${ARGS}..."
	${BUILD_DIR}/${BINARY_NAME} ${ARGS}

# Install binary to GOPATH/bin
install:
	@echo "Installing ${BINARY_NAME}..."
	CGO_ENABLED=1 go install ${LDFLAGS} ${CMD_DIR}

# Clean build artifacts
clean:
	@echo "Cleaning..."
	go clean
	rm -rf ${BUILD_DIR}
	rm -f coverage.out coverage.html

# Development helpers
dev-setup: deps
	@echo "Setting up development environment..."
	@if ! command -v golangci-lint >/dev/null 2>&1; then \
		echo "Installing golangci-lint..."; \
		curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $$(go env GOPATH)/bin; \
	fi
	@if ! command -v goimports >/dev/null 2>&1; then \
		echo "Installing goimports..."; \
		go install golang.org/x/tools/cmd/goimports@latest; \
	fi

# Security scan
security:
	@echo "Running security scan..."
	@if command -v gosec >/dev/null 2>&1; then \
		gosec ./...; \
	else \
		echo "gosec not installed, skipping security scan"; \
	fi

# Compatibility test with Python implementation
test-compatibility:
	@echo "Running compatibility tests..."
	../tests/compatibility/test_vault_compatibility.sh

# Performance comparison with Python
benchmark-comparison:
	@echo "Running performance comparison..."
	../tests/performance/benchmark_all.sh

# Help
help:
	@echo "Available targets:"
	@echo "  build           - Build the binary"
	@echo "  build-release   - Build optimized release binary"
	@echo "  test            - Run tests"
	@echo "  test-coverage   - Run tests with coverage report"
	@echo "  benchmark       - Run benchmarks"
	@echo "  lint            - Run linter"
	@echo "  fmt             - Format code"
	@echo "  run             - Build and run"
	@echo "  run-args        - Build and run with ARGS"
	@echo "  install         - Install to GOPATH/bin"
	@echo "  clean           - Clean build artifacts"
	@echo "  deps            - Install dependencies"
	@echo "  dev-setup       - Setup development environment"
	@echo "  security        - Run security scan"
	@echo "  help            - Show this help"