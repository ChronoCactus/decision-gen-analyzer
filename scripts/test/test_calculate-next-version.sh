#!/bin/bash
# Test suite for calculate-next-version.sh
# Tests various scenarios to ensure correct version calculation

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
VERSION_SCRIPT="$PROJECT_ROOT/scripts/calculate-next-version.sh"

# Verify version script exists
if [ ! -f "$VERSION_SCRIPT" ]; then
    echo "Error: Cannot find calculate-next-version.sh at $VERSION_SCRIPT"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TEST_DIR=""

# Cleanup function
cleanup() {
    if [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ]; then
        cd /
        rm -rf "$TEST_DIR"
    fi
}

trap cleanup EXIT

# Helper function to print test results
print_result() {
    local test_name="$1"
    local expected="$2"
    local actual="$3"
    
    if [ "$expected" = "$actual" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo -e "  Expected: $expected"
        echo -e "  Got:      $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Create a test git repository
setup_test_repo() {
    TEST_DIR=$(mktemp -d)
    cd "$TEST_DIR"
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test User"
}

# Test 1: No commits, no tags (should return 0.0.0)
test_no_commits() {
    echo -e "\n${YELLOW}Test 1: No commits, no tags${NC}"
    setup_test_repo
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "No commits should return 0.0.0" "0.0.0" "$RESULT"
}

# Test 2: Initial feat commit (should bump to 0.1.0)
test_initial_feat() {
    echo -e "\n${YELLOW}Test 2: Initial feat commit${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "feat: initial feature"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Initial feat should bump to 0.1.0" "0.1.0" "$RESULT"
}

# Test 3: Initial fix commit (should bump to 0.0.1)
test_initial_fix() {
    echo -e "\n${YELLOW}Test 3: Initial fix commit${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "fix: initial fix"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Initial fix should bump to 0.0.1" "0.0.1" "$RESULT"
}

# Test 4: Breaking change with ! (should bump to 1.0.0)
test_breaking_change_exclamation() {
    echo -e "\n${YELLOW}Test 4: Breaking change with !${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "feat!: breaking change"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "feat! should bump to 1.0.0" "1.0.0" "$RESULT"
}

# Test 5: Breaking change in commit body (should bump to 1.0.0)
test_breaking_change_body() {
    echo -e "\n${YELLOW}Test 5: Breaking change in commit body${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "feat: new feature

BREAKING CHANGE: This breaks compatibility"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "BREAKING CHANGE should bump to 1.0.0" "1.0.0" "$RESULT"
}

# Test 6: Multiple patch commits (should bump to 0.0.1)
test_multiple_patch_commits() {
    echo -e "\n${YELLOW}Test 6: Multiple patch commits${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "fix: first fix"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "docs: update docs"
    
    touch test3.txt
    git add test3.txt
    git commit -q -m "test: add tests"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Multiple patches should bump to 0.0.1" "0.0.1" "$RESULT"
}

# Test 7: Mix of feat and fix (feat takes precedence - should bump to 0.1.0)
test_feat_and_fix() {
    echo -e "\n${YELLOW}Test 7: Mix of feat and fix${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "fix: first fix"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "feat: new feature"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "feat + fix should bump to 0.1.0" "0.1.0" "$RESULT"
}

# Test 8: With existing tag 1.2.3, feat commit (should bump to 1.3.0)
test_existing_tag_feat() {
    echo -e "\n${YELLOW}Test 8: Existing tag 1.2.3 + feat${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "1.2.3"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "feat: new feature"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "1.2.3 + feat should bump to 1.3.0" "1.3.0" "$RESULT"
}

# Test 9: With existing tag 1.2.3, fix commit (should bump to 1.2.4)
test_existing_tag_fix() {
    echo -e "\n${YELLOW}Test 9: Existing tag 1.2.3 + fix${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "1.2.3"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "fix: bug fix"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "1.2.3 + fix should bump to 1.2.4" "1.2.4" "$RESULT"
}

# Test 10: With existing tag 1.2.3, breaking change (should bump to 2.0.0)
test_existing_tag_breaking() {
    echo -e "\n${YELLOW}Test 10: Existing tag 1.2.3 + breaking change${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "1.2.3"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "refactor!: major refactor"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "1.2.3 + breaking should bump to 2.0.0" "2.0.0" "$RESULT"
}

# Test 11: Tag with v prefix (should handle correctly)
test_tag_with_v_prefix() {
    echo -e "\n${YELLOW}Test 11: Tag with v prefix${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "v2.5.7"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "feat: new feature"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "v2.5.7 + feat should bump to 2.6.0" "2.6.0" "$RESULT"
}

# Test 12: No new commits since tag (should keep same version)
test_no_new_commits() {
    echo -e "\n${YELLOW}Test 12: No new commits since tag${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "3.1.4"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "No new commits should keep 3.1.4" "3.1.4" "$RESULT"
}

# Test 13: All conventional commit types (patch)
test_all_patch_types() {
    echo -e "\n${YELLOW}Test 13: All patch-level commit types${NC}"
    setup_test_repo
    
    for type in fix docs test perf style ci chore build refactor; do
        touch "test_${type}.txt"
        git add "test_${type}.txt"
        git commit -q -m "${type}: ${type} commit"
    done
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "All patch types should bump to 0.0.1" "0.0.1" "$RESULT"
}

# Test 14: Conventional commits with scope
test_commits_with_scope() {
    echo -e "\n${YELLOW}Test 14: Commits with scope${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "feat(api): add new endpoint"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "fix(ui): correct button color"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "feat(scope) should bump to 0.1.0" "0.1.0" "$RESULT"
}

# Test 15: Breaking change with scope
test_breaking_with_scope() {
    echo -e "\n${YELLOW}Test 15: Breaking change with scope${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "feat(api)!: redesign endpoints"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "feat(scope)! should bump to 1.0.0" "1.0.0" "$RESULT"
}

# Test 16: Non-conventional commits (should not bump version)
test_non_conventional_commits() {
    echo -e "\n${YELLOW}Test 16: Non-conventional commits${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "random commit message"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "another random message"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Non-conventional commits should stay at 0.0.0" "0.0.0" "$RESULT"
}

# Test 17: With tag, non-conventional commits (should keep tag version)
test_tag_non_conventional() {
    echo -e "\n${YELLOW}Test 17: Tag + non-conventional commits${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "5.0.0"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "random update"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "5.0.0 + non-conventional should stay at 5.0.0" "5.0.0" "$RESULT"
}

# Test 18: Complex scenario - multiple types with precedence
test_complex_precedence() {
    echo -e "\n${YELLOW}Test 18: Complex precedence scenario${NC}"
    setup_test_repo
    
    touch test1.txt
    git add test1.txt
    git commit -q -m "initial commit"
    git tag "10.5.2"
    
    touch test2.txt
    git add test2.txt
    git commit -q -m "fix: bug fix"
    
    touch test3.txt
    git add test3.txt
    git commit -q -m "feat: new feature"
    
    touch test4.txt
    git add test4.txt
    git commit -q -m "docs: update docs"
    
    touch test5.txt
    git add test5.txt
    git commit -q -m "refactor!: breaking refactor"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Breaking change should take precedence -> 11.0.0" "11.0.0" "$RESULT"
}

# Test 19: fix! breaking change
test_fix_breaking() {
    echo -e "\n${YELLOW}Test 19: fix! breaking change${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "fix!: breaking bug fix"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "fix! should bump to 1.0.0" "1.0.0" "$RESULT"
}

# Test 20: Multiline commit messages
test_multiline_commit() {
    echo -e "\n${YELLOW}Test 20: Multiline commit message${NC}"
    setup_test_repo
    
    touch test.txt
    git add test.txt
    git commit -q -m "feat: add amazing feature

This is a longer description
of the feature that spans
multiple lines"
    
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    print_result "Multiline feat should bump to 0.1.0" "0.1.0" "$RESULT"
}

# Run all tests
echo "========================================"
echo "Testing calculate-next-version.sh"
echo "========================================"

# Store original directory
ORIGINAL_DIR=$(pwd)

# Run all tests
test_no_commits
test_initial_feat
test_initial_fix
test_breaking_change_exclamation
test_breaking_change_body
test_multiple_patch_commits
test_feat_and_fix
test_existing_tag_feat
test_existing_tag_fix
test_existing_tag_breaking
test_tag_with_v_prefix
test_no_new_commits
test_all_patch_types
test_commits_with_scope
test_breaking_with_scope
test_non_conventional_commits
test_tag_non_conventional
test_complex_precedence
test_fix_breaking
test_multiline_commit

# Return to original directory
cd "$ORIGINAL_DIR"

# Print summary
echo ""
echo "========================================"
echo "Test Results"
echo "========================================"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo "========================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
