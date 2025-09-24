#!/bin/bash
set -e

echo "🔨 Building Lockr Python package..."

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Install/upgrade build tools
echo "Installing build dependencies..."
python -m pip install --upgrade pip
python -m pip install --upgrade build twine

# Run tests first
echo "Running tests..."
python -m pytest tests/ -v

# Type check
echo "Running type checks..."
python -m mypy lockr/

# Build package
echo "Building package..."
python -m build

# Verify package
echo "Verifying package..."
python -m twine check dist/*

echo "✅ Build complete! Files created:"
ls -la dist/

echo ""
echo "To install locally:"
echo "  pip install dist/lockr-1.0.0-py3-none-any.whl"
echo ""
echo "To publish to PyPI:"
echo "  python -m twine upload dist/*"
echo ""
echo "To publish to Test PyPI:"
echo "  python -m twine upload --repository testpypi dist/*"