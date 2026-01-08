#!/bin/bash
# Script to publish the package to PyPI
# Usage: ./publish.sh [test|prod]
#
# Before running, make sure you have:
# 1. Created accounts on Test PyPI and PyPI
# 2. Created API tokens (see PYPI_SETUP.md)
# 3. Set UV_PUBLISH_PASSWORD environment variable with your API token
#    OR uv will prompt you for credentials

set -e

ENV=${1:-test}

if [ "$ENV" = "test" ]; then
    echo "Publishing to Test PyPI (test.pypi.org)..."
    echo ""
    echo "⚠️  Make sure you have:"
    echo "   1. Created an account at https://test.pypi.org/"
    echo "   2. Created an API token at https://test.pypi.org/manage/account/token/"
    echo "   3. Set UV_PUBLISH_PASSWORD with your Test PyPI token"
    echo "      Or you'll be prompted for:"
    echo "        Username: __token__"
    echo "        Password: pypi-your-token-here"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to cancel..."
    REPOSITORY="--repository-url https://test.pypi.org/legacy/"
    URL="https://test.pypi.org/project/marketdata-sdk-py"
elif [ "$ENV" = "prod" ]; then
    echo "Publishing to PyPI (pypi.org)..."
    echo ""
    echo "⚠️  Make sure you have:"
    echo "   1. Created an account at https://pypi.org/"
    echo "   2. Created an API token at https://pypi.org/manage/account/token/"
    echo "   3. Set UV_PUBLISH_PASSWORD with your PyPI token"
    echo "      Or you'll be prompted for:"
    echo "        Username: __token__"
    echo "        Password: pypi-your-token-here"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to cancel..."
    REPOSITORY=""
    URL="https://pypi.org/project/marketdata-sdk-py"
else
    echo "Usage: $0 [test|prod]"
    echo ""
    echo "See PYPI_SETUP.md for detailed setup instructions."
    exit 1
fi

# Build the package
echo "Building package..."
uv build

# Publish the package
echo "Publishing package..."
uv publish $REPOSITORY

echo ""
echo "✅ Package published successfully!"
echo "View at: $URL"
echo ""
echo "To install from Test PyPI:"
echo "  pip install --index-url https://test.pypi.org/simple/ marketdata-sdk-py"
echo ""
echo "To install from PyPI:"
echo "  pip install marketdata-sdk-py"
