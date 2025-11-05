# Decision Analyzer - AI Copilot Instructions

## Architecture Overview

This is a **multi-persona ADR (Architectural Decision Record) analysis and generation system** with async task processing. The architecture has 3 main layers:

1. **React/Next.js Frontend** (`frontend/`) - TypeScript UI on port 3000
2. **FastAPI Backend** (`src/api/`) - Python REST API on port 8000
3. **Celery Worker** (`src/celery_app.py`) - Async task processor with Redis queue

**Data Flow**: Frontend → FastAPI routes (`src/api/routes.py`) → Queue Celery tasks → Worker processes using LLM clients → Store results in LightRAG vector DB

## Critical Integration Points

### External Services (Network Dependencies)
- **Llama.cpp Servers** - LLM inference, supports multiple backends for parallel processing:
  - `LLAMA_CPP_URL` (required) - Primary server on port 11434
  - `LLAMA_CPP_URL_1` (optional) - Secondary server for parallel persona generation
  - `LLAMA_CPP_URL_EMBEDDING` (optional) - Dedicated server for embeddings
  - Used by `LlamaCppClient` (single) or `LlamaCppClientPool` (multiple backends)
- **LightRAG Server** (`LIGHTRAG_URL`) - Vector database on port 9621, used by `LightRAGClient`
- **Redis** - Task queue and result backend on port 6379 (6380 externally in docker-compose)

**Important**: These services run on external IPs configured in docker-compose environment variables. Always use async context managers (`async with client:` or `async with pool:`) for these clients.

### Multi-Persona System with Parallel Processing
The core feature: analyze ADRs through different "personas" (technical lead, business analyst, security expert, etc.). Each persona has:
- JSON config in `config/personas/*.json` defining focus areas and evaluation criteria
- **Dynamic Loading**: Personas are loaded from filesystem on each API call (no caching)
- **Customizable**: Users can add new personas by dropping JSON files in `config/personas/` (mounted as Docker volume)
- Loaded by `PersonaManager` class from `src/persona_manager.py`
- Used in parallel by `ADRGenerationService._generate_persona_perspectives()`
- API endpoint `/api/v1/adrs/personas` dynamically reads from config files

**10 Default Personas**: technical_lead, business_analyst, risk_manager, architect, product_manager, customer_support, security_expert, devops_engineer, qa_engineer, philosopher

**Pattern**: Generate separate perspectives in parallel → synthesize into final ADR with all viewpoints considered.

**Performance**: When `LLAMA_CPP_URL_1` is configured, `LlamaCppClientPool` distributes persona generation requests across multiple backends, reducing generation time by ~50%.

**Customization**: See `config/personas/README.md` for instructions on adding custom personas.

## Critical Developer Workflows

### Starting the Full Stack
```bash
docker compose up --build  # Starts redis, backend API, celery worker, frontend
```

**Port Mapping**: External services use host network IPs (not localhost) in Docker environment. Check `docker-compose.yml` for `LLAMA_CPP_URL`, `LLAMA_CPP_URL_1`, `LLAMA_CPP_URL_EMBEDDING`, and `LIGHTRAG_URL` variables.

### Running Backend Only
```bash
./scripts/run_backend.sh  # Starts uvicorn with correct PYTHONPATH
```

### Testing
```bash
make test                      # Run all tests (backend + frontend)
make test-backend              # Run all backend tests
make test-backend-unit         # Backend unit tests only
make test-backend-integration  # Backend integration tests only
make test-frontend             # Run frontend tests
make test-coverage             # All tests with coverage
```

**Test Structure**: 
- **Backend**: Tests co-located in `src/*/tests/` directories (e.g., `src/tests/test_models.py`)
- **Frontend**: Tests alongside source files with `.test.tsx` extension (e.g., `ADRCard.test.tsx`)
- **Integration**: Tests in `tests/integration/` directory

**Test Patterns**:

*Backend (pytest):*
```python
# src/tests/test_example.py
import pytest
from unittest.mock import AsyncMock

class TestExample:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        return client
    
    @pytest.mark.asyncio
    async def test_method(self, mock_client):
        # Arrange
        mock_client.generate.return_value = '{"data": "test"}'
        
        # Act
        result = await service.method()
        
        # Assert
        assert result is not None
        mock_client.generate.assert_awaited()
```

*Frontend (Vitest + React Testing Library):*
```tsx
// components/Example.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'

describe('Example', () => {
  it('handles interaction', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    
    render(<Example onClick={onClick} />)
    await user.click(screen.getByRole('button'))
    
    expect(onClick).toHaveBeenCalledOnce()
  })
})
```

**Mocking Strategy**: Mock everything - all external services (LLM, Vector DB, Redis, File I/O, HTTP requests).

See `docs/TESTING.md` for comprehensive testing guide.

## Data Models and Conventions

### Core Model Hierarchy
```python
ADR (src/models.py)
├── metadata: ADRMetadata (id, title, status, author, tags)
└── content: ADRContent (context, options, decision, consequences)
    ├── consequences_structured: ConsequencesStructured (positive/negative lists)
    ├── options_details: List[OptionDetails] (name, pros, cons)
    └── referenced_adrs: List[Dict] (ADRs used during generation)
```

### Async Task Pattern (Celery)
```python
# In src/celery_app.py - tasks use nested async functions:
@celery_app.task(bind=True)
def generate_adr_task(self, ...):
    async def _generate():
        async with LlamaCppClient() as llama:
            # async work here
    return asyncio.run(_generate())
```

**Why**: Celery tasks must be sync functions, but our clients are async. Wrap async code in `asyncio.run()`.

### Consequences Parsing (Recent Bug Fix)
The `consequences` field is plain text from LLM with format:
```
Positive:
- item 1
- item 2

Negative:
- item 1
```

**Pattern in `celery_app.py`**: Parse this by splitting on newlines, strip bullet markers (`- `, `* `, `• `), populate `consequences_structured` for frontend rendering. See lines 182-223 for implementation.

## Frontend Conventions

### Component Structure
- `src/components/` - Reusable components (ADRModal, GenerateADRModal, PersonasModal)
- Custom hook: `useEscapeKey` for modal closure
- API client: `src/lib/api.ts` - centralized fetch wrapper

### Type Safety
All API types in `src/types/api.ts` must match backend Pydantic models. When backend models change, update TypeScript interfaces.

### Styling
Tailwind CSS with custom classes. Status colors defined inline (e.g., `getStatusColor()` in ADRModal).

## LLM Prompt Engineering Patterns

### Structured JSON Responses
Always request JSON from LLM with explicit schema in prompt. Example from `adr_generation.py`:

```python
prompt = """You must respond with a JSON object containing:
{
  "title": "...",
  "context_and_problem": "...",
  ...
}"""
```

### Parsing Robustness
```python
# Pattern: Extract JSON from markdown code blocks
import re
json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
if json_match:
    data = json.loads(json_match.group(1))
```

See `_parse_synthesis_response()` in `adr_generation.py` for full implementation.

### Text Formatting Polish
After LLM generation, use `_polish_formatting()` and `_apply_formatting_cleanup()` to fix:
- Line breaks in phrases (e.g., "GPU\nRAM" → "GPU, RAM")
- Non-breaking hyphens (‑ → -)
- Bullet point consistency

## Configuration Management

### Settings Pattern
All config via `src/config.py` using `pydantic-settings`:
```python
from src.config import get_settings
settings = get_settings()  # Loads from env vars
```

### Environment Variables
- Development: `.env` (root) and `frontend/.env.local`
- Docker: `docker-compose.yml` environment section
- Required: `LLAMA_CPP_URL`, `LIGHTRAG_URL`, `REDIS_URL`
- Optional: `LLAMA_CPP_URL_1` (secondary backend), `LLAMA_CPP_URL_EMBEDDING` (embedding backend)

## Storage and File Handling

### ADR Storage
ADRs stored as JSON files in `data/adrs/` (volume mounted in Docker). File operations use `aiofiles` for async I/O.

**Pattern**: `ADRFileStorage` class manages CRUD operations. Always use `async with` for file operations.

### LightRAG Vector Storage
Documents stored with `doc_id` as ADR UUID. Content includes:
- Full ADR text
- Metadata for semantic search
- Used by `_get_related_context()` during generation to find relevant past decisions

## Common Pitfalls

1. **Async Context Managers**: Always use `async with client:` or `async with pool:` - clients need proper session cleanup. Works with both `LlamaCppClient` and `LlamaCppClientPool`
2. **PYTHONPATH**: Backend expects `PYTHONPATH=/app/src` in Docker, `./src` locally
3. **Port Conflicts**: Frontend uses 3003 in package.json, docker-compose uses 3000 externally
4. **Celery Tasks**: Must be sync functions wrapping async code with `asyncio.run()`
5. **JSON Parsing**: LLMs sometimes wrap JSON in markdown - always extract with regex first

## Key Files Reference

- `src/models.py` - All Pydantic data models, enums
- `src/adr_generation.py` - Core generation service with persona orchestration and parallel processing
- `src/llama_client.py` - LLM client and client pool for parallel requests
- `src/celery_app.py` - Task definitions, consequences parsing logic
- `src/api/routes.py` - All REST endpoints
- `config/personas/*.json` - Persona configurations
- `docker-compose.yml` - Service definitions and network config
- `docs/PARALLEL_PROCESSING.md` - Multi-backend configuration guide
