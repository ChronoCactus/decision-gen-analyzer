# Testing Guide

This document provides comprehensive testing guidelines for the Decision Analyzer project.

## Table of Contents

- [Quick Start](#quick-start)
- [Testing Philosophy](#testing-philosophy)
- [Test Structure](#test-structure)
- [Backend Testing](#backend-testing)
- [Frontend Testing](#frontend-testing)
- [Running Tests](#running-tests)
- [Mocking Strategy](#mocking-strategy)
- [Best Practices](#best-practices)

---

## Quick Start

### Install Dependencies

**Backend** (already installed via pip):
```bash
pip install -e .
```

**Frontend**:
```bash
make install-frontend-deps
# or
cd frontend && npm install
```

### Run All Tests

```bash
make test
```

### Run Specific Test Suites

```bash
make test-backend              # All backend tests
make test-backend-unit         # Backend unit tests only
make test-backend-integration  # Backend integration tests only
make test-frontend             # Frontend tests
```

### Run Tests with Coverage

```bash
make test-coverage             # All tests with coverage
make test-coverage-backend     # Backend coverage only
make test-coverage-frontend    # Frontend coverage only
```

---

## Testing Philosophy

### Core Principles

1. **Co-located Tests**: Tests live close to the code they test
2. **Mock External Dependencies**: All external services are mocked
3. **Fast Feedback**: Tests should run quickly
4. **Clear Assertions**: Tests should be easy to read and understand
5. **Comprehensive Coverage**: Test both happy paths and edge cases

### What to Test

- **Unit Tests**: Individual functions, classes, and modules in isolation
- **Integration Tests**: Multiple components working together
- **Component Tests**: React components and their behavior
- **API Tests**: FastAPI routes and endpoints

### What NOT to Test

- Third-party libraries (assume they work)
- Configuration files (unless complex logic)
- Type definitions without logic

---

## Test Structure

### Backend (Python)

Tests are co-located with source code in `tests/` subdirectories:

```
src/
├── adr_generation.py
├── tests/
│   ├── __init__.py
│   └── test_adr_generation.py
├── api/
│   ├── routes.py
│   └── tests/
│       ├── __init__.py
│       └── test_routes.py
tests/
└── integration/
    ├── __init__.py
    ├── test_adr_management.py
    └── test_infrastructure.py
```

**Naming Convention**: `test_<module_name>.py`

### Frontend (TypeScript/React)

Tests are co-located with source files using `.test.tsx` or `.test.ts` extension:

```
frontend/src/
├── components/
│   ├── ADRCard.tsx
│   └── ADRCard.test.tsx
├── hooks/
│   ├── useEscapeKey.ts
│   └── useEscapeKey.test.ts
├── lib/
│   ├── api.ts
│   └── api.test.ts
```

**Naming Convention**: `<filename>.test.ts` or `<filename>.test.tsx`

---

## Backend Testing

### Test Framework

- **pytest**: Test runner
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Enhanced mocking
- **unittest.mock**: Standard library mocking

### Test Structure Pattern

```python
"""Tests for example module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.example import ExampleClass

class TestExampleClass:
    """Test ExampleClass functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock external client dependency."""
        client = AsyncMock()
        # Configure default behavior
        client.method.return_value = {"result": "success"}
        return client
    
    @pytest.fixture
    def example_instance(self, mock_client):
        """Create instance with mocked dependencies."""
        return ExampleClass(mock_client)
    
    @pytest.mark.asyncio
    async def test_example_method(self, example_instance, mock_client):
        """Test example method with mocked client."""
        # Arrange
        expected_result = {"data": "test"}
        mock_client.method.return_value = expected_result
        
        # Act
        result = await example_instance.method()
        
        # Assert
        assert result == expected_result
        mock_client.method.assert_called_once()
    
    def test_synchronous_method(self, example_instance):
        """Test synchronous method."""
        # Arrange
        input_data = "test"
        
        # Act
        result = example_instance.sync_method(input_data)
        
        # Assert
        assert result is not None
        assert isinstance(result, str)
```

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    mock_client = AsyncMock()
    mock_client.fetch.return_value = {"data": "value"}
    
    result = await my_async_function(mock_client)
    
    assert result is not None
    mock_client.fetch.assert_awaited_once()
```

### Testing FastAPI Routes

```python
from fastapi.testclient import TestClient
from src.api.main import app

def test_get_endpoint():
    """Test GET endpoint."""
    client = TestClient(app)
    
    response = client.get("/api/adrs")
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_post_endpoint():
    """Test POST endpoint with body."""
    client = TestClient(app)
    payload = {"title": "Test ADR"}
    
    response = client.post("/api/adrs", json=payload)
    
    assert response.status_code == 201
    assert response.json()["title"] == "Test ADR"
```

### Testing Pydantic Models

```python
import pytest
from pydantic import ValidationError
from src.models import ADR

def test_adr_creation():
    """Test ADR model creation with valid data."""
    adr = ADR.create(
        title="Test",
        context_and_problem="Problem",
        decision_outcome="Decision",
        consequences="Consequences",
        author="Author"
    )
    
    assert adr.title == "Test"
    assert adr.metadata.status == "proposed"

def test_adr_validation_error():
    """Test ADR validation with invalid data."""
    with pytest.raises(ValidationError):
        ADR(title="", context_and_problem="")  # Missing required fields
```

### Mocking LLM Clients

```python
@pytest.fixture
def mock_llama_client():
    """Mock Llama client for testing."""
    client = AsyncMock()
    client.generate.return_value = '{"title": "Generated", "content": "..."}'
    return client

@pytest.mark.asyncio
async def test_generation_service(mock_llama_client):
    """Test generation service with mocked LLM."""
    service = ADRGenerationService(mock_llama_client)
    
    result = await service.generate(prompt="Test")
    
    assert result is not None
    mock_llama_client.generate.assert_awaited()
```

### Running Backend Tests

```bash
# All backend tests
make test-backend

# Unit tests only (in src/*/tests/)
make test-backend-unit

# Integration tests only (in tests/integration/)
make test-backend-integration

# Specific test file
pytest src/tests/test_models.py -v

# Specific test class
pytest src/tests/test_models.py::TestADR -v

# Specific test method
pytest src/tests/test_models.py::TestADR::test_creation -v

# With coverage
make test-coverage-backend
```

---

## Frontend Testing

### Test Framework

- **Vitest**: Test runner (faster than Jest)
- **React Testing Library**: Component testing
- **@testing-library/jest-dom**: Custom matchers
- **@testing-library/user-event**: User interaction simulation

### Test Structure Pattern

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ExampleComponent from './ExampleComponent'

describe('ExampleComponent', () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks()
  })

  it('renders correctly', () => {
    render(<ExampleComponent title="Test" />)
    
    expect(screen.getByText('Test')).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()
    
    render(<ExampleComponent onClick={handleClick} />)
    
    await user.click(screen.getByRole('button'))
    
    expect(handleClick).toHaveBeenCalledOnce()
  })

  it('handles async operations', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: 'test' })
      })
    )
    global.fetch = mockFetch
    
    render(<ExampleComponent />)
    
    await waitFor(() => {
      expect(screen.getByText('test')).toBeInTheDocument()
    })
    
    expect(mockFetch).toHaveBeenCalledOnce()
  })
})
```

### Testing React Hooks

```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { useEscapeKey } from './useEscapeKey'

describe('useEscapeKey', () => {
  it('calls callback on escape key', () => {
    const callback = vi.fn()
    renderHook(() => useEscapeKey(callback))
    
    // Simulate escape key press
    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    document.dispatchEvent(event)
    
    expect(callback).toHaveBeenCalledOnce()
  })
})
```

### Testing API Client Functions

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchADRs, createADR } from './api'

describe('API Client', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('fetches ADRs successfully', async () => {
    const mockData = [{ id: '1', title: 'Test' }]
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    })
    
    const result = await fetchADRs()
    
    expect(result).toEqual(mockData)
    expect(fetch).toHaveBeenCalledWith('/api/adrs')
  })

  it('handles fetch errors', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    })
    
    await expect(fetchADRs()).rejects.toThrow()
  })

  it('creates ADR with POST request', async () => {
    const newADR = { title: 'New ADR' }
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: '1', ...newADR }),
    })
    
    const result = await createADR(newADR)
    
    expect(result.title).toBe('New ADR')
    expect(fetch).toHaveBeenCalledWith('/api/adrs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newADR),
    })
  })
})
```

### Testing Modal Components

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import Modal from './Modal'

describe('Modal', () => {
  it('renders when open', () => {
    render(<Modal isOpen={true} onClose={vi.fn()}>Content</Modal>)
    
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(<Modal isOpen={false} onClose={vi.fn()}>Content</Modal>)
    
    expect(screen.queryByText('Content')).not.toBeInTheDocument()
  })

  it('calls onClose when escape is pressed', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    
    render(<Modal isOpen={true} onClose={handleClose}>Content</Modal>)
    
    await user.keyboard('{Escape}')
    
    expect(handleClose).toHaveBeenCalled()
  })
})
```

### Running Frontend Tests

```bash
# All frontend tests
make test-frontend

# With UI interface
cd frontend && npm run test:ui

# Watch mode (auto-rerun on changes)
cd frontend && npm test

# With coverage
make test-coverage-frontend

# Specific test file
cd frontend && npm test -- src/components/ADRCard.test.tsx
```

---

## Mocking Strategy

### What to Mock

All external dependencies and services are mocked in unit tests:

1. **LLM Clients** (Llama.cpp)
   - Mock response generation
   - Mock API calls
   
2. **Vector Database** (LightRAG)
   - Mock document storage
   - Mock search queries

3. **Redis/Celery**
   - Mock task queuing
   - Mock result retrieval

4. **File System**
   - Mock file reads/writes (use `aiofiles` mocks)
   
5. **HTTP Requests**
   - Mock `fetch` calls
   - Mock external API responses

### Mock Example Patterns

**Backend - Async Client Mock:**
```python
@pytest.fixture
def mock_llama_client():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.generate.return_value = '{"response": "data"}'
    return client
```

**Frontend - Fetch Mock:**
```tsx
const mockFetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ data: 'test' })
  })
)
global.fetch = mockFetch
```

---

## Best Practices

### General

1. **Arrange-Act-Assert**: Structure tests clearly
2. **One Assertion Per Test**: Focus on one thing (when possible)
3. **Descriptive Names**: Test names should describe what they test
4. **Use Fixtures**: Reuse common setup with fixtures (pytest) or beforeEach (vitest)
5. **Clean Up**: Reset mocks and state between tests

### Backend

1. **Mark Async Tests**: Always use `@pytest.mark.asyncio`
2. **Mock Context Managers**: Use `__aenter__` and `__aexit__` for async context managers
3. **Test Validation**: Test both valid and invalid inputs for Pydantic models
4. **Isolate Tests**: Don't rely on test execution order

### Frontend

1. **Query by Role**: Prefer `getByRole` over `getByTestId`
2. **Wait for Changes**: Use `waitFor` for async operations
3. **User Events**: Use `@testing-library/user-event` for realistic interactions
4. **Avoid Implementation Details**: Test behavior, not implementation

### Do's and Don'ts

**DO:**
- ✅ Write tests before fixing bugs
- ✅ Test edge cases and error conditions
- ✅ Keep tests simple and focused
- ✅ Use meaningful variable names
- ✅ Clean up resources in fixtures

**DON'T:**
- ❌ Test implementation details
- ❌ Make tests dependent on each other
- ❌ Use real external services in unit tests
- ❌ Write flaky tests (non-deterministic)
- ❌ Skip writing tests for "simple" code

---

## CI/CD Integration

Tests should run automatically in CI/CD:

```bash
# In CI pipeline
make install-frontend-deps
make test
make test-coverage
```

---

## Troubleshooting

### Common Issues

**Import Errors in Tests:**
- Ensure `PYTHONPATH` is set correctly
- Check that `__init__.py` files exist

**Async Test Not Running:**
- Add `@pytest.mark.asyncio` decorator
- Check `pytest-asyncio` is installed

**Frontend Test Timeout:**
- Increase timeout in `waitFor`
- Check for missing `await` on async operations

**Mock Not Working:**
- Verify mock is applied before function call
- Check mock is reset between tests

---

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [Vitest documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

**Last Updated**: November 1, 2025
