# Version Calculation Script Tests

This directory contains tests for the semantic versioning calculation script.

## Test Suite

**File:** `test_calculate-next-version.sh`

Comprehensive test suite with 20 test scenarios covering all aspects of semantic versioning based on conventional commits.

### Running Tests

```bash
# Via Makefile (recommended)
make test-version-script

# Or directly
./scripts/test/test_calculate-next-version.sh
```

### Test Coverage

The test suite verifies:

1. **Initial states** - No commits, first commits
2. **Version bumps** - Patch, minor, major
3. **Breaking changes** - With `!` and `BREAKING CHANGE` in body
4. **Conventional commits** - All types (feat, fix, docs, etc.)
5. **Scopes** - Commits with scopes like `feat(api):`
6. **Tags** - Existing tags with different version formats
7. **Precedence** - Complex scenarios with multiple commit types
8. **Edge cases** - Non-conventional commits, multiline messages

### Expected Output

```
========================================
Testing calculate-next-version.sh
========================================

Test 1: No commits, no tags
✓ No commits should return 0.0.0

Test 2: Initial feat commit
✓ Initial feat should bump to 0.1.0

...

========================================
Test Results
========================================
Passed: 20
Failed: 0
========================================
All tests passed!
```

### Adding New Tests

To add a new test scenario:

1. Add a new test function following the naming pattern `test_<scenario_name>`
2. Use the helper functions:
   - `setup_test_repo()` - Create a fresh test repository
   - `print_result(test_name, expected, actual)` - Print test result
3. Call the new test function at the bottom of the script
4. Run tests to verify: `make test-version-script`

### Test Function Template

```bash
test_your_scenario() {
    echo -e "\n${YELLOW}Test N: Description${NC}"
    setup_test_repo
    
    # Setup git repository state
    touch test.txt
    git add test.txt
    git commit -q -m "your commit message"
    
    # Run version calculation
    RESULT=$("$VERSION_SCRIPT" 2>/dev/null)
    
    # Verify result
    print_result "Description should result in X.Y.Z" "X.Y.Z" "$RESULT"
}
```

### CI Integration

These tests should be run in CI before merging changes to the version calculation script:

```yaml
- name: Test version calculation
  run: make test-version-script
```

## Maintenance

When updating `scripts/calculate-next-version.sh`:

1. **Always run tests first** to establish baseline
2. **Make your changes** to the script
3. **Run tests again** to verify no regressions
4. **Add new tests** if implementing new functionality
5. **Update documentation** if behavior changes

All 20 tests must pass before merging any changes.
