# LightRAG Document ID Caching System

## Overview

This system provides a Redis-based cache for mapping ADR file paths to LightRAG's internal document IDs, enabling proper document deletion and management.

## Problem Statement

LightRAG uses internal document IDs (format: `doc-{hash}`) that are different from the file paths we use when storing documents. The deletion API requires these internal IDs, but:

1. The `/documents/text` (insert) endpoint doesn't return the document ID
2. There's no `/documents/{filename}` endpoint to query a single document
3. The only way to get document IDs is through the `/documents/paginated` endpoint

## Solution Architecture

### Components

1. **LightRAGDocumentCache** (`src/lightrag_doc_cache.py`)
   - Redis-based cache storing `file_path -> doc_id` mappings
   - Uses Redis keys with 24-hour TTL
   - Provides async context manager interface

2. **LightRAG Sync Service** (`src/lightrag_sync.py`)
   - Background task that periodically syncs the cache with LightRAG
   - Fetches paginated documents and updates cache
   - Can sync individual documents after insertion
   - Default sync interval: 5 minutes

3. **Updated LightRAGClient** (`src/lightrag_client.py`)
   - New `get_paginated_documents()` method to fetch document lists
   - Updated `delete_document()` to accept optional `lightrag_doc_id` parameter
   - Falls back to filename if doc ID not provided (may not work)

4. **API Route Updates** (`src/api/routes.py`)
   - Delete route queries cache before deletion
   - Insert route triggers background sync task
   - Both operations handle cache failures gracefully

### Data Flow

#### Document Insertion
```
1. User creates ADR → File storage
2. ADR pushed to LightRAG → `/documents/text`
3. Background task triggered → `sync_single_document(adr_id)`
4. Task fetches recent documents → `/documents/paginated`
5. Finds document by file_path → Caches mapping
```

#### Document Deletion
```
1. User deletes ADR → File storage deleted
2. System queries cache → `get_doc_id(adr_id)`
3. If found: Delete using doc ID → `/documents/delete_document`
4. Cache entry removed
5. If not found: Log warning, attempt with filename
```

#### Background Sync
```
1. Background task runs every 5 minutes
2. Fetches all documents in batches → `/documents/paginated`
3. Updates cache with all file_path → doc_id mappings
4. Records last sync timestamp
```

## Redis Cache Structure

### Keys
- `lightrag:doc:{file_path}` - Maps file path to document ID
  - Value: `doc-{hash}`
  - TTL: 24 hours
- `lightrag:last_sync` - Timestamp of last full sync
  - Value: Unix timestamp
  - No TTL

### Example
```
lightrag:doc:d9f6f90f-53a4-4276-91c4-66fad1760b4f.txt → doc-0ee7a2a777da1f721a408f0bb936e201
```

## Usage

### Manual Cache Operations

```python
from lightrag_doc_cache import LightRAGDocumentCache

# Get document ID
async with LightRAGDocumentCache() as cache:
    doc_id = await cache.get_doc_id("adr-123")
    if doc_id:
        print(f"Document ID: {doc_id}")

# Set document ID
async with LightRAGDocumentCache() as cache:
    await cache.set_doc_id("adr-123", "doc-abc123...")

# Clear cache
async with LightRAGDocumentCache() as cache:
    await cache.clear_all()
```

### Running Background Sync

```python
from lightrag_sync import sync_lightrag_cache_task

# Start background sync task
asyncio.create_task(sync_lightrag_cache_task(interval_seconds=300))
```

### Sync Single Document

```python
from lightrag_sync import sync_single_document

# After inserting a document
doc_id = await sync_single_document(adr_id="test-123", max_retries=3)
```

## Environment Variables

- `REDIS_URL` - Redis connection string (default: `redis://localhost:6379/0`)
- `LIGHTRAG_URL` - LightRAG server URL
- `LIGHTRAG_API_KEY` - LightRAG API key (optional)

## Deployment Considerations

### Docker Compose

The system requires Redis to be running. In `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    volumes:
      - redis_data:/data
  
  backend:
    environment:
      - REDIS_URL=redis://redis:6379/0
```

### Background Task

To enable automatic cache syncing, start the background task on application startup. Add to `src/api/main.py`:

```python
from lightrag_sync import sync_lightrag_cache_task
import asyncio

@app.on_event("startup")
async def startup_event():
    # Start background cache sync
    asyncio.create_task(sync_lightrag_cache_task(interval_seconds=300))
```

## Performance

### Cache Hit Rate
- High: After full sync completes, all document lookups hit cache
- Medium: During first 5 minutes after app start, only recently added docs cached
- Low: If Redis is down, all operations fall back to filename-based deletion (may fail)

### Sync Performance
- **Single document sync**: ~2-5 seconds (fetches recent 50 documents)
- **Full sync (100 documents)**: ~10-15 seconds
- **Full sync (1000 documents)**: ~1-2 minutes

## Error Handling

### Cache Unavailable
- System logs warning but continues operation
- Deletion attempted with filename (may not work)
- No impact on other operations

### Sync Failures
- Background task retries on next interval
- Individual document sync has exponential backoff (3 retries)
- Failures logged but don't affect user operations

## Testing

Tests are located in `src/tests/test_lightrag_client.py`:

```bash
pytest src/tests/test_lightrag_client.py -v
```

Key test cases:
- Delete with document ID (preferred)
- Delete without document ID (fallback)
- Paginated document fetching
- Cache operations

## Future Enhancements

1. **Webhook Support**: If LightRAG adds webhooks, update cache immediately on document processing
2. **Batch Operations**: Add support for bulk delete operations
3. **Cache Metrics**: Track hit rate, sync duration, cache size
4. **Smart Sync**: Only sync documents modified since last sync
5. **Fallback Query**: If doc ID not in cache, query paginated endpoint just-in-time

## Troubleshooting

### Documents not deleting properly
- Check if cache is being populated: `redis-cli GET "lightrag:doc:your-file.txt"`
- Verify background sync is running (check logs for "LightRAG cache sync completed")
- Manually trigger sync after inserting: `await sync_single_document(adr_id)`

### Cache growing too large
- Reduce TTL in `LightRAGDocumentCache.CACHE_TTL`
- Run periodic cache cleanup: `await cache.clear_all()`
- Monitor Redis memory usage

### Sync taking too long
- Reduce `page_size` in sync task (default: 100)
- Increase sync `interval_seconds` (default: 300)
- Consider filtering to only "processed" status documents
