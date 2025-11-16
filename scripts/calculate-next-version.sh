#!/bin/bash
# Script to calculate next semantic version based on conventional commits
# Usage: ./calculate-next-version.sh [current_version]
# If no current_version provided, starts at 0.0.0

set -e

# Get the last tag, or default to 0.0.0
LAST_TAG="${1:-$(git describe --tags --abbrev=0 2>/dev/null || echo "")}"
if [ -z "$LAST_TAG" ]; then
    LAST_TAG="0.0.0"
fi

echo "Last version: $LAST_TAG" >&2

# Parse the version
if [[ $LAST_TAG =~ ^v?([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    MAJOR="${BASH_REMATCH[1]}"
    MINOR="${BASH_REMATCH[2]}"
    PATCH="${BASH_REMATCH[3]}"
else
    echo "Error: Invalid version format: $LAST_TAG" >&2
    exit 1
fi

echo "Parsed version: MAJOR=$MAJOR, MINOR=$MINOR, PATCH=$PATCH" >&2

# Get all commit messages since the last tag (subject + body)
if git rev-parse "$LAST_TAG" >/dev/null 2>&1; then
    COMMIT_RANGE="$LAST_TAG..HEAD"
else
    # No previous tag exists, get all commits
    COMMIT_RANGE="--all"
fi

# Check if there are any commits
COMMIT_COUNT=$(git rev-list $COMMIT_RANGE --count 2>/dev/null || echo "0")
if [ "$COMMIT_COUNT" -eq 0 ]; then
    echo "No new commits since $LAST_TAG" >&2
    echo "$LAST_TAG"
    exit 0
fi

echo "Analyzing $COMMIT_COUNT commits..." >&2

# Flags for version bumping
HAS_BREAKING=false
HAS_FEATURE=false
HAS_FIX=false

# Iterate through each commit
git log $COMMIT_RANGE --format="%H" | while read commit_hash; do
    # Get commit subject and body
    subject=$(git log -1 --format="%s" "$commit_hash")
    body=$(git log -1 --format="%b" "$commit_hash")
    full_message="$subject"$'\n'"$body"
    
    echo "  - $subject" >&2
    
    # Check for breaking changes (! in subject or BREAKING CHANGE in body)
    if [[ $full_message =~ !: ]] || [[ $full_message =~ BREAKING\ CHANGE ]]; then
        echo "    → Breaking change detected" >&2
        echo "BREAKING" > /tmp/version_calc_breaking_$$
    # Check for features (minor version bump)
    elif [[ $subject =~ ^feat ]]; then
        echo "    → Feature detected" >&2
        if [ ! -f /tmp/version_calc_breaking_$$ ]; then
            echo "FEATURE" > /tmp/version_calc_feature_$$
        fi
    # Check for fixes and other patch-level changes
    elif [[ $subject =~ ^(fix|docs|test|perf|style|ci|chore|build|refactor) ]]; then
        echo "    → Patch-level change detected" >&2
        if [ ! -f /tmp/version_calc_breaking_$$ ] && [ ! -f /tmp/version_calc_feature_$$ ]; then
            echo "FIX" > /tmp/version_calc_fix_$$
        fi
    fi
done

# Check what was found (using temp files since subshell doesn't modify parent vars)
if [ -f /tmp/version_calc_breaking_$$ ]; then
    HAS_BREAKING=true
    rm -f /tmp/version_calc_breaking_$$
fi
if [ -f /tmp/version_calc_feature_$$ ]; then
    HAS_FEATURE=true
    rm -f /tmp/version_calc_feature_$$
fi
if [ -f /tmp/version_calc_fix_$$ ]; then
    HAS_FIX=true
    rm -f /tmp/version_calc_fix_$$
fi

# Calculate new version
if [ "$HAS_BREAKING" = true ]; then
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    echo "Bumping MAJOR version (breaking change)" >&2
elif [ "$HAS_FEATURE" = true ]; then
    MINOR=$((MINOR + 1))
    PATCH=0
    echo "Bumping MINOR version (new feature)" >&2
elif [ "$HAS_FIX" = true ]; then
    PATCH=$((PATCH + 1))
    echo "Bumping PATCH version (fix/patch)" >&2
else
    echo "No conventional commits found, keeping version at $LAST_TAG" >&2
    echo "$LAST_TAG"
    exit 0
fi

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "New version: $NEW_VERSION" >&2
echo "$NEW_VERSION"
