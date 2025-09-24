#!/bin/bash
set -e

echo "🧪 Testing Lockr installation..."

# Create a temporary virtual environment
TEMP_ENV=$(mktemp -d)/test-env
echo "Creating temporary environment: $TEMP_ENV"
python -m venv "$TEMP_ENV"
source "$TEMP_ENV/bin/activate"

# Install the package
echo "Installing package from dist/..."
if [ ! -d "dist" ]; then
    echo "❌ No dist/ directory found. Run build.sh first."
    exit 1
fi

WHEEL_FILE=$(ls dist/*.whl | head -1)
if [ -z "$WHEEL_FILE" ]; then
    echo "❌ No wheel file found in dist/. Run build.sh first."
    exit 1
fi

pip install "$WHEEL_FILE"

echo "✅ Package installed successfully"

# Test CLI commands
echo "Testing CLI commands..."

# Test help
echo "  Testing --help..."
lockr --help > /dev/null
echo "  ✅ Help command works"

# Test version info by checking if command exists
echo "  Testing command availability..."
which lockr > /dev/null
echo "  ✅ lockr command is available in PATH"

# Test package import
echo "  Testing Python imports..."
python -c "import lockr; print('✅ Package imports successfully')"

echo "✅ All tests passed!"

# Cleanup
echo "Cleaning up temporary environment..."
deactivate
rm -rf "$TEMP_ENV"

echo "🎉 Installation test complete!"