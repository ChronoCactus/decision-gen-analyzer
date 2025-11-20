#!/bin/bash

# Check if npx is available
if ! command -v npx &> /dev/null; then
    echo "⚠️  Warning: npx not available, skipping commit message validation"
    exit 0
fi

# Check if commitlint is available
if ! npx commitlint --version &> /dev/null; then
    echo "⚠️  Warning: commitlint not available, skipping commit message validation"
    exit 0
fi

# Run commitlint on the commit message
npx commitlint --edit "$1"
