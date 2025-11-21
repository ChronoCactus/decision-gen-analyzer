# Branching Strategy and Release Process

## Overview

This project uses a **develop/main branching model** designed to bundle multiple features and fixes into coherent releases, reducing release notification fatigue for users.

## Branch Structure

```
main (production releases)
  └── develop (integration branch)
        ├── feature/queue-clearing
        ├── feature/multi-backend-support
        └── fix/websocket-reconnect
```

### Branches

- **`main`** - Production-ready code, tagged with versions (v1.0.0, v1.1.0, etc.)
- **`develop`** - Integration branch where features accumulate before release
- **`feature/*`** - Individual feature branches
- **`fix/*`** - Bug fix branches
- **`hotfix/*`** - Emergency fixes branched from `main`

## Workflow

### 1. Feature Development

```bash
# Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/my-awesome-feature

# Make changes, commit using conventional commits
git commit -m "feat: add queue clearing option"
git commit -m "test: add tests for queue clearing"
git commit -m "docs: document queue clearing feature"

# Push and create PR to develop
git push origin feature/my-awesome-feature
```

**PR Target**: `develop`

### 2. Feature Integration

- Features are reviewed and merged into `develop`
- Multiple PRs accumulate in `develop` over time
- `develop` becomes a staging ground for the next release

### 3. Release Process

When ready to release (e.g., 5 features and 3 bug fixes are ready):

```bash
# Create release PR: develop → main
# GitHub web UI: 
#   - Base: main
#   - Compare: develop
#   - Title: "Release v1.2.0" (version will be calculated)
```

**What Happens on Merge**:
1. GitHub Actions calculates semantic version from all commits since last tag
2. Docker images built and published to ghcr.io
3. Git tag created (e.g., `v1.2.0`)
4. GitHub Release created with auto-generated notes
5. All features/fixes bundled under single version

**After Merge**:
```bash
# Sync develop with main
git checkout develop
git merge main
git push origin develop
```

### 4. Hotfix Process (Emergency Fixes)

For critical bugs in production:

```bash
# Branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-security-fix

# Make fix, commit
git commit -m "fix!: patch security vulnerability CVE-2025-xxxx"

# Create PR to main
git push origin hotfix/critical-security-fix
```

**After Merge**:
```bash
# Also merge back to develop
git checkout develop
git merge main
git push origin develop
```

## Commit Conventions

### Standard Types

- `feat:` - New feature (triggers **minor** bump: 0.1.0 → 0.2.0)
- `fix:` - Bug fix (triggers **patch** bump: 0.1.0 → 0.1.1)
- `docs:` - Documentation only
- `style:` - Code style/formatting
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Test changes
- `chore:` - Build/tooling changes
- `ci:` - CI/CD changes

### Breaking Changes

Add `!` or `BREAKING CHANGE:` for **major** bumps (0.1.0 → 1.0.0):

```bash
git commit -m "feat!: redesign persona API"
# or
git commit -m "feat: redesign persona API

BREAKING CHANGE: PersonaManager.get_persona() now returns PersonaConfig objects"
```

### Examples

```bash
# Feature
git commit -m "feat: add real-time queue monitoring"

# Bug fix
git commit -m "fix: resolve WebSocket reconnection issue"

# Documentation
git commit -m "docs: update branching strategy"

# With scope
git commit -m "fix(frontend): correct dark mode colors in modal"

# Breaking change
git commit -m "feat!: replace REST API with GraphQL"
```

## Version Calculation

When `develop` is merged to `main`, the version is calculated from **all commits** since the last tag:

### Priority Rules

1. **Any** breaking change commit → **Major** bump (1.0.0 → 2.0.0)
2. **Any** feature commit → **Minor** bump (1.0.0 → 1.1.0)
3. **Only** fixes/docs/etc → **Patch** bump (1.0.0 → 1.0.1)

### Example Scenario

Commits in `develop` since last release (v0.5.0):
- `feat: add queue clearing option`
- `feat: add multi-backend support`
- `feat: add dark mode to all components`
- `fix: resolve websocket reconnection`
- `fix: correct persona config loading`
- `docs: update README with new features`

**Calculation**: 3 features detected → **Minor** bump

**Result**: v0.5.0 → **v0.6.0** (bundling all 6 changes)

## FAQ

### Q: When should I merge to `main`?

A: When you're ready to cut a release. Bundle multiple features/fixes together for a cohesive release.

### Q: What if I have one critical feature to release immediately?

A: You can still do single-feature releases:
1. Merge feature to `develop`
2. Immediately create release PR: `develop` → `main`
3. Result: Release with just that one feature

### Q: How do I know what version will be generated?

A: Use the version calculation script:
```bash
./scripts/calculate-next-version.sh
```

This is the same script used by GitHub Actions.

### Q: What if I accidentally merged to `main` instead of `develop`?

A: Don't panic! You have options:
1. **If not pushed**: Reset and repush to correct branch
2. **If pushed and CI running**: Cancel the workflow, create hotfix
3. **If released**: Version is incremented, continue with `develop` for next release

### Q: Should I delete feature branches after merge?

A: Yes, after merging to `develop`, delete the feature branch to keep the repo clean.

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Full contribution guidelines
- [.github/workflows/README.md](../.github/workflows/README.md) - CI/CD workflows
- [docs/TESTING.md](../docs/TESTING.md) - Testing guidelines
- [scripts/calculate-next-version.sh](../scripts/calculate-next-version.sh) - Version calculation

## Questions?

Open a [GitHub Discussion](https://github.com/ChronoCactus/decision-gen-analyzer/discussions) or create an issue!
