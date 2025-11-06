# ADR Export/Import Feature

## Overview

The Decision Analyzer supports exporting and importing Architectural Decision Records (ADRs) with a **versioned schema** that enables forward and backward compatibility. This allows you to:

- **Export ADRs** individually or in bulk for backup, sharing, or migration
- **Import ADRs** from previous exports or external sources
- **Maintain compatibility** across different versions of the Decision Analyzer
- **Validate data** during import to ensure integrity

## Schema Versioning

### Current Version: 1.0.0

The versioned schema includes metadata about the export itself, allowing the system to:
- Identify which version of the schema was used
- Apply appropriate migrations when importing older formats
- Reject unsupported future versions with clear error messages

### Supported Versions

- **1.0.0** (Current) - Initial versioned schema with complete ADR fields

Future versions will be added as the ADR data model evolves. The system is designed to support multiple versions simultaneously through migration logic.

## Versioned Export Schema Structure

### Schema Metadata

Every export includes metadata about the export itself:

```json
{
  "schema": {
    "schema_version": "1.0.0",
    "exported_at": "2025-11-06T12:34:56.789012",
    "exported_by": "user@example.com",
    "total_records": 1
  }
}
```

**Fields:**
- `schema_version` (string, required): Version of the export schema
- `exported_at` (string, required): ISO 8601 timestamp of export
- `exported_by` (string, optional): Identifier of who/what performed the export
- `total_records` (int, required): Number of ADRs in this export

### Single ADR Export Format

```json
{
  "schema": {
    "schema_version": "1.0.0",
    "exported_at": "2025-11-06T12:34:56.789012",
    "exported_by": "user@example.com",
    "total_records": 1
  },
  "adr": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Database Selection for User Management",
    "status": "accepted",
    "created_at": "2025-11-01T10:00:00Z",
    "updated_at": "2025-11-02T15:30:00Z",
    "author": "Architecture Team",
    "tags": ["database", "postgresql"],
    "related_adrs": [],
    "custom_fields": {},
    "context_and_problem": "We need to choose a database...",
    "decision_drivers": ["ACID compliance", "Scalability"],
    "considered_options": ["PostgreSQL", "MySQL", "MongoDB"],
    "decision_outcome": "Adopt PostgreSQL...",
    "consequences": "Positive:\n- ACID compliance\nNegative:\n- Higher resource usage",
    "confirmation": null,
    "pros_and_cons": null,
    "more_information": null,
    "options_details": [
      {
        "name": "PostgreSQL",
        "description": "Robust relational database",
        "pros": ["ACID compliant", "Rich feature set"],
        "cons": ["Higher resource usage"]
      }
    ],
    "consequences_structured": {
      "positive": ["ACID compliance", "Rich querying"],
      "negative": ["Higher resource usage"]
    },
    "referenced_adrs": [
      {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "title": "Cloud Provider Selection",
        "summary": "Decision to use AWS for infrastructure hosting..."
      }
    ],
    "persona_responses": null
  }
}
```

### Bulk ADR Export Format

```json
{
  "schema": {
    "schema_version": "1.0.0",
    "exported_at": "2025-11-06T12:34:56.789012",
    "exported_by": "user@example.com",
    "total_records": 2
  },
  "adrs": [
    {
      "id": "...",
      "title": "First ADR",
      ...
    },
    {
      "id": "...",
      "title": "Second ADR",
      ...
    }
  ]
}
```

## API Endpoints

### Export Endpoints

#### 1. Export Single ADR

```http
GET /adrs/{adr_id}/export?format=versioned_json&exported_by=user@example.com
```

**Query Parameters:**
- `format` (optional): Export format. Options: `versioned_json` (default), `markdown`
- `exported_by` (optional): Identifier of who is exporting

**Response:** File download (JSON or Markdown)

**Example:**
```bash
curl -X GET "http://localhost:8000/adrs/550e8400-e29b-41d4-a716-446655440000/export?format=versioned_json" \
  -H "accept: application/json" \
  -o adr_export.json
```

#### 2. Export ADRs in Bulk

```http
POST /adrs/export
Content-Type: application/json

{
  "format": "versioned_json",
  "adr_ids": ["id1", "id2"],  // Optional: omit to export all
  "exported_by": "user@example.com"
}
```

**Request Body:**
- `format` (optional): Export format (default: `versioned_json`)
- `adr_ids` (optional): List of ADR IDs to export. If omitted, exports all ADRs
- `exported_by` (optional): Identifier of who is exporting

**Response:** File download with all selected ADRs

**Example (export all):**
```bash
curl -X POST "http://localhost:8000/adrs/export" \
  -H "Content-Type: application/json" \
  -d '{"format": "versioned_json"}' \
  -o all_adrs_export.json
```

**Example (export specific ADRs):**
```bash
curl -X POST "http://localhost:8000/adrs/export" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "versioned_json",
    "adr_ids": ["550e8400-e29b-41d4-a716-446655440000", "660e8400-e29b-41d4-a716-446655440001"],
    "exported_by": "admin@example.com"
  }' \
  -o selected_adrs_export.json
```

### Import Endpoints

#### 1. Import Single ADR

```http
POST /adrs/import/single
Content-Type: application/json

{
  "data": {
    "schema": {...},
    "adr": {...}
  },
  "overwrite_existing": false
}
```

**Request Body:**
- `data` (required): Complete versioned export object for a single ADR
- `overwrite_existing` (optional): If `true`, replaces existing ADRs with same ID (default: `false`)

**Automatic RAG Indexing:** Imported ADRs are automatically pushed to LightRAG for indexing.

**Response:**
```json
{
  "message": "Successfully imported ADR: Database Selection",
  "imported_count": 1,
  "skipped_count": 0,
  "errors": []
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/adrs/import/single" \
  -H "Content-Type: application/json" \
  -d @adr_export.json
```

#### 2. Import ADRs in Bulk (from JSON data)

```http
POST /adrs/import
Content-Type: application/json

{
  "data": {
    "schema": {...},
    "adrs": [...]  // or "adr": {...} for single ADR format
  },
  "overwrite_existing": false
}
```

**Request Body:**
- `data` (required): Complete versioned export object. Accepts both:
  - **Bulk format**: Object with `adrs` array containing multiple ADRs
  - **Single format**: Object with `adr` field containing a single ADR
- `overwrite_existing` (optional): If `true`, replaces existing ADRs (default: `false`)

**Note:** The endpoint automatically detects whether the data is in single or bulk format and handles it appropriately. You can import a single exported ADR without needing to convert it to bulk format.

**Automatic RAG Indexing:** All imported ADRs are automatically pushed to LightRAG for indexing. If the RAG push fails, the import will still succeed (error is logged).

**Response:**
```json
{
  "message": "Import completed: 5 imported, 2 skipped",
  "imported_count": 5,
  "skipped_count": 2,
  "errors": [
    "ADR 550e8400-e29b-41d4-a716-446655440000 already exists (use overwrite_existing=true to replace)"
  ]
}
```

#### 3. Import ADRs from File Upload

```http
POST /adrs/import/file
Content-Type: multipart/form-data

file: <binary file data>
overwrite_existing: false
```

**Form Data:**
- `file` (required): The exported JSON file
- `overwrite_existing` (optional): Boolean query parameter

**Automatic RAG Indexing:** Imported ADRs are automatically pushed to LightRAG for indexing.

**Example:**
```bash
curl -X POST "http://localhost:8000/adrs/import/file?overwrite_existing=false" \
  -F "file=@all_adrs_export.json"
```

## Python Usage

### Export

```python
from src.adr_import_export import ADRImportExport
from src.adr_file_storage import get_adr_storage

# Get ADRs from storage
storage = get_adr_storage()
adr = storage.get_adr("adr-id-here")

# Export single ADR to versioned format
export_data = ADRImportExport.export_single_versioned(
    adr,
    exported_by="script@example.com"
)

# Save to file
ADRImportExport.export_single_versioned_to_file(
    adr,
    "output.json",
    exported_by="script@example.com"
)

# Export multiple ADRs
adrs, _ = storage.list_adrs(limit=1000)
bulk_export = ADRImportExport.export_bulk_versioned(
    adrs,
    exported_by="bulk_script@example.com"
)

# Save bulk export to file
ADRImportExport.export_bulk_versioned_to_file(
    adrs,
    "all_adrs.json",
    exported_by="bulk_script@example.com"
)
```

### Import

```python
from src.adr_import_export import ADRImportExport
from src.adr_file_storage import get_adr_storage

# Import single ADR from file
adr = ADRImportExport.import_single_versioned_from_file("exported_adr.json")

# Save to storage
storage = get_adr_storage()
storage.save_adr(adr)

# Import multiple ADRs from file
adrs = ADRImportExport.import_bulk_versioned_from_file("all_adrs.json")

# Save all to storage
for adr in adrs:
    storage.save_adr(adr)

# Import from dict (useful for API)
import json
with open("export.json") as f:
    data = json.load(f)

adr = ADRImportExport.import_single_versioned(data)
# or
adrs = ADRImportExport.import_bulk_versioned(data)
```

### Automatic RAG Indexing

**Important:** When you import ADRs through the API endpoints (`/adrs/import`, `/adrs/import/file`, or `/adrs/import/single`), the system **automatically pushes them to LightRAG** for indexing. This means:

- ✅ Imported ADRs are immediately searchable and available for contextual analysis
- ✅ No manual "Push to RAG" action required after import
- ✅ Works for both single and bulk imports
- ⚠️ If RAG push fails, the import will still succeed (error is logged but not propagated)

**Note:** If you import ADRs programmatically using the Python functions above (bypassing the API), you'll need to manually push them to RAG using the `/adrs/{adr_id}/push-to-rag` endpoint.

## Schema Evolution & Migration

### Adding a New Field (Non-Breaking Change)

When adding a new optional field to ADRs:

1. Add the field to the current schema version models
2. Make it optional with a default value
3. Update export logic to include the new field
4. Update import logic to handle both presence and absence of the field

**Example:** Adding `risk_level` field
```python
class ADRExportV1(BaseModel):
    # ... existing fields ...
    risk_level: Optional[str] = Field(default=None, description="Risk assessment")
```

This is **backward compatible** - old exports without `risk_level` will import successfully.

### Changing Field Structure (Breaking Change)

When making breaking changes:

1. Create a new schema version (e.g., v2.0.0)
2. Define new models: `ADRExportV2`, `SingleADRExportV2`, `BulkADRExportV2`
3. Add v2.0.0 to `SUPPORTED_SCHEMA_VERSIONS`
4. Update `CURRENT_SCHEMA_VERSION` to "2.0.0"
5. Implement migration logic from v1 to v2 in import methods

**Example Migration Pattern:**
```python
def import_single_versioned(data: Dict[str, Any]) -> ADR:
    schema_version = data.get("schema", {}).get("schema_version", "1.0.0")
    
    if schema_version == "1.0.0":
        # Import v1 format
        adr = _import_v1(data)
    elif schema_version == "2.0.0":
        # Import v2 format
        adr = _import_v2(data)
    else:
        raise ValueError(f"Unsupported version: {schema_version}")
    
    return adr

def _import_v1(data: Dict[str, Any]) -> ADR:
    """Import v1 format and migrate to current internal format."""
    export_v1 = SingleADRExport(**data)
    # Migration logic here
    return _export_v1_to_adr(export_v1.adr)

def _import_v2(data: Dict[str, Any]) -> ADR:
    """Import v2 format."""
    export_v2 = SingleADRExportV2(**data)
    return _export_v2_to_adr(export_v2.adr)
```

### Version Compatibility Matrix

| Import Version | Current System | Status |
|---------------|----------------|---------|
| 1.0.0         | 1.0.0          | ✅ Fully supported |
| Future 2.0.0  | 1.0.0          | ❌ Rejected with error |
| 1.0.0         | Future 2.0.0   | ✅ Supported via migration |

## Error Handling

### Unsupported Schema Version

```python
# Attempting to import a future version
ValueError: Unsupported schema version: 2.0.0. Supported versions: ['1.0.0']
```

**Solution:** Update to a newer version of Decision Analyzer that supports schema v2.0.0

### Invalid JSON Structure

```python
# Malformed JSON or missing required fields
ValidationError: 1 validation error for SingleADRExport
adr -> title
  field required (type=value_error.missing)
```

**Solution:** Ensure the export file is valid and not corrupted

### Duplicate ADR ID on Import

```json
{
  "message": "Import completed: 0 imported, 1 skipped",
  "imported_count": 0,
  "skipped_count": 1,
  "errors": [
    "ADR 550e8400-e29b-41d4-a716-446655440000 already exists (use overwrite_existing=true to replace)"
  ]
}
```

**Solution:** Set `overwrite_existing: true` in the import request to replace existing ADRs

## Best Practices

### 1. Regular Backups

Schedule regular exports of all ADRs:

```bash
# Weekly backup script
curl -X POST "http://localhost:8000/adrs/export" \
  -H "Content-Type: application/json" \
  -d '{"format": "versioned_json", "exported_by": "backup-cron"}' \
  -o "backup_$(date +%Y%m%d).json"
```

### 2. Version Control for ADRs

Store exported ADRs in Git for version history:

```bash
git add exports/
git commit -m "ADR export $(date +%Y-%m-%d)"
git push
```

### 3. Testing Imports

Always test imports in a non-production environment first:

1. Export from production
2. Import to staging with `overwrite_existing: false`
3. Verify data integrity
4. Only then import to production if needed

### 4. Document Custom Fields

If using `custom_fields`, document their structure:

```python
# Good practice: Define custom field schema
adr.metadata.custom_fields = {
    "cost_estimate": "50000",
    "implementation_quarter": "Q1-2026",
    "approved_by": ["cto@example.com", "cfo@example.com"]
}
```

### 5. Include Metadata

Always include `exported_by` to track export sources:

```python
export = ADRImportExport.export_bulk_versioned(
    adrs,
    exported_by=f"{user_email}@{hostname}"
)
```

## Troubleshooting

### Issue: Export returns 404

**Cause:** ADR ID doesn't exist

**Solution:** Verify ADR ID using `GET /adrs/` to list all ADRs

### Issue: Import fails with validation errors

**Cause:** Export file is corrupted or from incompatible version

**Solution:** 
1. Check `schema.schema_version` in the file
2. Validate JSON structure
3. Re-export from source system if possible

### Issue: Import succeeds but ADRs are missing fields

**Cause:** Exporting from older version, fields may not have existed

**Solution:** This is expected behavior. Optional fields will be `null` for old exports.

## Future Enhancements

Planned improvements for export/import:

- [ ] Support for YAML export format with versioned schema
- [ ] Incremental exports (only changed ADRs since last export)
- [ ] Export templates/personas along with ADRs
- [ ] Automatic schema migration UI
- [ ] Export/import audit trail
- [ ] Compressed export formats (.zip)

## Related Documentation

- [API Documentation](http://localhost:8000/docs) - Interactive API reference when running the backend
- [Quick Start Guide](./QUICKSTART.md) - Getting started with Decision Analyzer
- [Testing Guide](./TESTING.md) - Testing export/import functionality
