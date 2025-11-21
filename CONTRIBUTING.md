# Contributing to Decision Generator Analyzer

Thank you for your interest in contributing to the Decision Generator Analyzer! This document outlines our development workflow, branching strategy, and guidelines for contributions.

## Table of Contents
- [Branching Strategy](#branching-strategy)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Code Quality Standards](#code-quality-standards)

> **Quick Reference**: See [docs/BRANCHING_STRATEGY.md](docs/BRANCHING_STRATEGY.md) for a detailed guide with examples and FAQs.

## Branching Strategy

We use a **develop/main branching model** to manage releases and bundle features effectively:

### Branch Structure

- **`main`** - Production-ready code. Only updated via PRs from `develop` during release cycles.
- **`develop`** - Integration branch for upcoming releases. Features are merged here first.
- **`feature/*`** - Individual feature branches created from `develop`.
- **`fix/*`** - Bug fix branches created from `develop`.
- **`hotfix/*`** - Critical fixes that need immediate deployment (branched from `main`).

### Workflow Overview

```
feature/my-feature → develop → main (releases)
      ↓                ↓         ↓
   (PR #1)         (PR #2)    (v1.2.0)
```

### Detailed Workflow

1. **Feature Development**
   - Create a feature branch from `develop`:
     ```bash
     git checkout develop
     git pull origin develop
     git checkout -b feature/my-awesome-feature
     ```
   - Make your changes and commit using [conventional commits](#commit-conventions)
   - Push your branch and open a PR to `develop`

2. **Feature Integration**
   - PRs are reviewed and merged into `develop`
   - Multiple features and fixes accumulate in `develop`
   - This allows bundling related changes under a single version

3. **Release Process**
   - When ready to cut a release, open a PR from `develop` → `main`
   - This PR bundles all features and fixes since the last release
   - Merging to `main` triggers:
     - Semantic version calculation (based on all commits since last tag)
     - Docker image builds and publishes to ghcr.io
     - GitHub release creation with release notes
   - After merge, sync `develop` with `main`:
     ```bash
     git checkout develop
     git merge main
     git push origin develop
     ```

4. **Hotfixes** (Critical bugs in production)
   - Branch from `main`:
     ```bash
     git checkout main
     git pull origin main
     git checkout -b hotfix/critical-bug-fix
     ```
   - Make the fix, open PR to `main`
   - After merge, also merge `main` back to `develop` to keep them in sync

### Why This Strategy?

**Benefits:**
- **Bundled Releases**: Group multiple features/fixes into meaningful release versions (e.g., v1.2.0 includes 5 features instead of 5 separate releases)
- **Reduced Notification Fatigue**: Users get one release notification for multiple improvements
- **Stable Main Branch**: `main` always reflects production-ready, released code
- **Flexible Release Timing**: Release when ready, not on every merge
- **Clear History**: Release PRs (`develop` → `main`) provide a clear snapshot of what's in each version

## Development Workflow

### Setting Up Your Environment

1. **Clone and Setup**
   ```bash
   git clone https://github.com/benjigill/decision-gen-analyzer.git
   cd decision-analyzer
   git checkout develop  # Start from develop
   ```

2. **Backend Setup**
   ```bash
   pip install -e .
   ./scripts/run_backend.sh
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Full Stack with Docker**
   ```bash
   docker compose up --build
   ```

### Making Changes

1. **Create a Feature Branch**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write code following our [code quality standards](#code-quality-standards)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   make test              # Run all tests
   make test-backend      # Backend only
   make test-frontend     # Frontend only
   ```

4. **Commit Your Changes**
   - Use [conventional commits](#commit-conventions)
   - Keep commits focused and atomic
   ```bash
   git add .
   git commit -m "feat: add multi-persona comparison view"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   - Open a PR to `develop` on GitHub
   - Fill out the PR template with details about your changes
   - Link any related issues

## Pull Request Process

### PR Requirements

All PRs must meet these requirements before merging:

- [ ] **Tests Pass**: All CI checks must pass (when implemented)
- [ ] **Code Quality**: Linting and formatting standards met
- [ ] **Test Coverage**: New code includes appropriate tests
- [ ] **Documentation**: README/docs updated if needed
- [ ] **Conventional Commits**: Commit messages follow convention
- [ ] **No Merge Conflicts**: Branch is up to date with target branch
- [ ] **Review Approved**: At least one maintainer approval

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Closes #123

## Testing
Describe how you tested this change

## Checklist
- [ ] My code follows the code quality standards
- [ ] I have added tests that prove my fix/feature works
- [ ] I have updated the documentation accordingly
- [ ] My commits follow the conventional commit convention
```

### Review Process

1. **Automated Checks**: CI runs tests, linting (future implementation)
2. **Code Review**: Maintainers review the code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, maintainers will merge

### Version Calculation

When a release PR (`develop` → `main`) is merged, the version is calculated based on **all commits since the last tag**:

- If **any** commit has breaking change → **Major bump** (1.0.0 → 2.0.0)
- Else if **any** commit is a feature → **Minor bump** (1.0.0 → 1.1.0)
- Else → **Patch bump** (1.0.0 → 1.0.1)

Example: If `develop` has 3 features and 2 bug fixes since last release, merging to `main` will trigger a **minor version bump** (0.5.0 → 0.6.0), bundling all 5 changes under one release.

## Testing Requirements

### Backend Tests (Python/pytest)

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test component interactions
- **Test Location**: Co-located with source in `src/*/tests/`

```bash
make test-backend           # All backend tests
make test-backend-unit      # Unit tests only
make test-backend-integration  # Integration tests only
pytest src/tests/test_specific.py  # Single file
```

### Frontend Tests (TypeScript/Vitest)

- **Component Tests**: Test React components with React Testing Library
- **Hook Tests**: Test custom hooks
- **Test Location**: Alongside source files with `.test.tsx` extension

```bash
make test-frontend          # All frontend tests
cd frontend && npm test     # Run in watch mode
```

### Coverage

```bash
make test-coverage          # Generate coverage report
open htmlcov/index.html     # View backend coverage
```

### Testing Guidelines

- Write tests for all new features and bug fixes
- Aim for >80% code coverage
- Mock external dependencies (LLM, Vector DB, Redis, etc.)
- Use clear test names that describe what's being tested
- Follow existing test patterns in the codebase

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide.

## Code Quality Standards

### Backend (Python)

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Linting
ruff check src/ tests/
```

**Standards:**
- Type hints for all function signatures
- Async/await for I/O operations
- Pydantic models for data validation
- Docstrings for public functions and classes
- Follow PEP 8 style guide

### Frontend (TypeScript/React)

```bash
cd frontend

# Linting
npm run lint

# Type checking
npm run type-check
```

**Standards:**
- TypeScript strict mode enabled
- Functional components with hooks
- Dark mode support for all UI components (see `.github/copilot-instructions.md`)
- Tailwind CSS for styling
- Proper prop types and interfaces

### Pre-commit Hooks

Consider setting up pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually
pre-commit run --all-files
```

## Questions or Issues?

Open a [GitHub Issue](https://github.com/ChronoCactus/decision-gen-analyzer/issues)

## Code of Conduct

Please be respectful and constructive in all interactions. We're building this together!

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
