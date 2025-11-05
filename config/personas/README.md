# Persona Configuration

This directory contains JSON configuration files for analysis personas used in ADR generation and analysis.

## Overview

Each persona provides a unique perspective during ADR (Architectural Decision Record) generation. The system dynamically loads all personas from this directory, allowing you to customize existing personas or add new ones.

## Persona Configuration Format

Each persona is defined in a JSON file with the following structure:

```json
{
  "name": "Persona Display Name",
  "description": "Brief description shown in the UI",
  "instructions": "Detailed instructions for the LLM on how to analyze from this perspective",
  "focus_areas": [
    "Key area 1",
    "Key area 2",
    "..."
  ],
  "evaluation_criteria": [
    "Question or criterion 1?",
    "Question or criterion 2?",
    "..."
  ]
}
```

### Fields

- **name** (string, required): The display name shown in the UI
- **description** (string, required): A brief description of the persona's focus (shown in persona selection)
- **instructions** (string, required): Detailed instructions for the LLM explaining how to analyze decisions from this perspective
- **focus_areas** (array of strings, required): List of key areas this persona focuses on
- **evaluation_criteria** (array of strings, required): List of questions or criteria the persona should evaluate

## Default Personas

The system includes 10 default personas:

1. **technical_lead.json** - Technical feasibility and implementation
2. **business_analyst.json** - Business value and ROI
3. **risk_manager.json** - Risk assessment and mitigation
4. **architect.json** - System design and architectural consistency
5. **product_manager.json** - User impact and product strategy
6. **customer_support.json** - Support implications and user experience
7. **security_expert.json** - Security and compliance
8. **devops_engineer.json** - Deployment and operational concerns
9. **qa_engineer.json** - Testability and quality assurance
10. **philosopher.json** - Fundamental principles and ethics

## Adding Custom Personas

### Step 1: Define the Persona in Code

First, add your persona to the `AnalysisPersona` enum in `src/models.py`:

```python
class AnalysisPersona(str, Enum):
    # ... existing personas ...
    MY_CUSTOM_PERSONA = "my_custom_persona"
```

### Step 2: Create Configuration File

Create a new JSON file in this directory named `{persona_value}.json` (e.g., `my_custom_persona.json`):

```json
{
  "name": "My Custom Persona",
  "description": "A custom perspective for specialized analysis",
  "instructions": "Focus on [specific aspects]. Consider [key factors]. Evaluate [criteria].",
  "focus_areas": [
    "Focus area 1",
    "Focus area 2",
    "Focus area 3"
  ],
  "evaluation_criteria": [
    "How does this affect [aspect]?",
    "What are the implications for [concern]?",
    "Does this align with [principle]?"
  ]
}
```

### Step 3: Restart Services

If running in Docker:
```bash
docker compose restart backend celery_worker
```

If running locally:
```bash
# Restart your backend server
```

The new persona will be automatically discovered and available in the UI.

## Customizing Existing Personas

You can modify any existing persona configuration by editing its JSON file. Changes will be picked up on the next API call (no caching).

### Example: Customizing the DevOps Engineer Persona

Edit `devops_engineer.json` to add focus on cost optimization:

```json
{
  "name": "DevOps Engineer",
  "description": "DevOps perspective focusing on deployment, monitoring, scalability, and operational concerns",
  "instructions": "Focus on deployment strategies, infrastructure requirements, monitoring capabilities, scalability, cost optimization, and operational concerns...",
  "focus_areas": [
    "Deployment strategies",
    "Infrastructure requirements",
    "Monitoring and observability",
    "Scalability and performance",
    "Cost optimization",
    "..."
  ],
  "evaluation_criteria": [
    "How will this be deployed and managed?",
    "What are the cost implications?",
    "..."
  ]
}
```

## Docker Volume Mounting

The `config/personas` directory is mounted as a volume in Docker Compose, allowing you to modify persona configurations without rebuilding images:

```yaml
volumes:
  - ./config:/app/config
```

This means you can:
- Add new persona JSON files
- Edit existing persona configurations
- Remove persona configurations (will fall back to generic defaults)

All changes are immediately available without rebuilding Docker images.

## Best Practices

1. **Be Specific**: Provide detailed instructions that guide the LLM on what to focus on
2. **Clear Focus Areas**: List 5-10 concrete areas the persona should evaluate
3. **Actionable Criteria**: Frame evaluation criteria as questions the persona should answer
4. **Consistent Tone**: Match the expertise level and perspective in all fields
5. **Comprehensive Coverage**: Ensure the persona covers all aspects of their domain

## Example Custom Personas

### Data Engineer Persona

```json
{
  "name": "Data Engineer",
  "description": "Data architecture and pipeline perspective",
  "instructions": "Focus on data architecture, ETL pipelines, data quality, and analytics infrastructure. Consider data governance, scalability of data solutions, and integration with data platforms.",
  "focus_areas": [
    "Data pipeline architecture",
    "ETL/ELT design",
    "Data quality and validation",
    "Analytics infrastructure",
    "Data governance",
    "Scalability of data solutions"
  ],
  "evaluation_criteria": [
    "How does this affect data pipelines?",
    "What are the data quality implications?",
    "Is this approach scalable for data volume?",
    "Does this align with data governance policies?"
  ]
}
```

### Compliance Officer Persona

```json
{
  "name": "Compliance Officer",
  "description": "Regulatory compliance and legal perspective",
  "instructions": "Focus on regulatory compliance, legal requirements, audit trails, and data privacy. Consider industry regulations (GDPR, HIPAA, SOX), contractual obligations, and documentation requirements.",
  "focus_areas": [
    "Regulatory compliance",
    "Legal requirements",
    "Audit trail capabilities",
    "Data privacy and protection",
    "Industry-specific regulations",
    "Documentation and reporting"
  ],
  "evaluation_criteria": [
    "Does this meet regulatory requirements?",
    "Are audit trails sufficient?",
    "What are the data privacy implications?",
    "Are there contractual considerations?"
  ]
}
```

## Troubleshooting

### Persona Not Appearing in UI

1. Verify the JSON file name matches the persona value from the enum (e.g., `my_custom_persona.json`)
2. Check that the JSON is valid using a JSON validator
3. Ensure all required fields are present
4. Restart the backend service
5. Check backend logs for parsing errors

### Fallback to Generic Config

If a persona config file is missing or invalid, the system will use a generic fallback configuration. Check logs for warnings about failed persona config loading.

## Support

For issues or questions about persona configuration, please refer to the main documentation or open an issue on the project repository.
