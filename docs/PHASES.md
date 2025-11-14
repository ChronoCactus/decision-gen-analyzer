# Project Phases

This document outlines the development roadmap for the Decision Generator Analyzer project. Each phase represents a major milestone with significant feature sets, and will likely correspond to a major version release (with many minor versions and patches within each phase).

## Phase 1: Generation 🚧 **IN PROGRESS**

**Status**: In Progress  
**Version**: 1.x

### Overview
Phase 1 establishes the foundation for AI-powered ADR generation with multi-persona analysis, import/export capabilities, and a modern web interface.

### Completed Features
- ✅ Multi-persona ADR generation (technical lead, business analyst, architect, etc.)
- ✅ Vector-based storage with LightRAG integration
- ✅ Import/Export functionality for ADR management
- ✅ Parallel LLM processing for faster generation
- ✅ Custom persona configuration via JSON files

### Planned Features
- 🚧 Multi-turn analysis conversations or generation per ADR
- 🚧 Convert existing Markdown ADRs to JSON format (import from other repos)
- 🚧 UI-based custom persona creation and management
- 🚧 Web-search result integration for real-time context

### Technical Highlights
- LangChain-based LLM integration supporting multiple providers (Ollama, OpenAI, OpenRouter, etc.)
- Redis pub/sub for cross-process WebSocket communication
- Queue visibility with real-time task monitoring
- File-based persona configuration with hot-reload

---

## Phase 2: Analyzation 📅 **PLANNED**

**Status**: Planned  
**Version**: 2.x (Target)

### Overview
Phase 2 introduces advanced analysis capabilities for existing ADRs, including contextual analysis, conflict detection, and decision paradigm evaluation.

### Planned Features
- 🚧 Analyze existing ADRs in context of other decisions
- 🚧 Conflict detection across decision records
- 🚧 Reasoning fallacy identification
- 🚧 Decision paradigm questioning (consistency checks)
- 🚧 Temporal analysis (how decisions evolve over time)
- 🚧 Multi-ADR comparison views
- 🚧 Automated re-analysis with web search integration
- 🚧 Analysis report generation with recommendations

### Technical Objectives
- Enhanced RAG retrieval for multi-document context
- Graph-based relationship analysis using LightRAG
- Conflict resolution suggestions using LLM reasoning
- Analysis history and versioning
- Batch analysis operations
- Analysis quality scoring

### Use Cases
- **Conflict Detection**: "Does ADR-005 contradict ADR-002's security approach?"
- **Paradigm Validation**: "Are all our scaling decisions consistent with our cost-optimization principle?"
- **Reasoning Review**: "Identify circular reasoning or unfounded assumptions in ADR-012"
- **Context Analysis**: "How does this ADR fit with our existing microservices decisions?"

---

## Phase 3: Decision Change Trees 📅 **PLANNED**

**Status**: Planned  
**Version**: 3.x (Target)

### Overview
Phase 3 introduces explicit relationship modeling between decisions, creating a navigable dependency graph that goes beyond semantic similarity.

### Planned Features
- 📅 Explicit relationship types: depends-on, relates-to, affected-by, supersedes, blocks
- 📅 Visual decision dependency maps
- 📅 Functional relationship navigation
- 📅 Change impact analysis ("What happens if we change ADR-003?")
- 📅 Dependency validation (prevent breaking changes)
- 📅 Relationship versioning and history
- 📅 Automatic relationship suggestion based on content
- 📅 Bidirectional relationship enforcement

### Technical Objectives
- Graph database integration (or enhanced LightRAG graph capabilities)
- Relationship type schema and validation
- D3.js or similar for interactive visualizations
- Change propagation algorithms
- Circular dependency detection
- Relationship impact scoring

### Use Cases
- **Impact Analysis**: "If we change our database from PostgreSQL to MongoDB (ADR-008), what other decisions are affected?"
- **Dependency Mapping**: "Show me all decisions that depend on our authentication strategy (ADR-015)"
- **Change Planning**: "Can we safely deprecate ADR-022 without breaking dependencies?"
- **Architecture Review**: "Visualize all decisions related to our data pipeline"

### Relationship Types
- **Depends On**: Decision A requires Decision B to be valid
- **Relates To**: Decision A is contextually connected to Decision B
- **Affected By**: Decision A's effectiveness changes based on Decision B
- **Supersedes**: Decision A replaces Decision B
- **Blocks**: Decision A prevents Decision B from being implemented
- **Complements**: Decision A works best when combined with Decision B

---

## Phase 4: Decision Severity Scoring 📅 **PLANNED**

**Status**: Planned  
**Version**: 4.x (Target)

### Overview
Phase 4 introduces quantitative scoring for decision importance, dependency strength, and change impact, enabling risk-aware decision management.

### Planned Features
- 📅 Decision cardinality scoring (how central is this decision?)
- 📅 Dependency strength metrics (how MUCH does A depend on B?)
- 📅 Change impact prediction with severity levels
- 📅 Impact threshold configuration (critical/high/medium/low)
- 📅 Automated risk assessment for proposed changes
- 📅 Decision criticality heatmaps
- 📅 Historical impact tracking
- 📅 Scoring pattern identification

### Technical Objectives
- Bespoke RAG solution for severity relationship management
- Machine learning for impact prediction (potentially fine-tuned models)
- Scoring algorithm development and validation
- Threshold-based alerting system
- Historical scoring analysis
- Severity propagation calculations

### Scoring Dimensions
- **Cardinality**: How many decisions reference or depend on this one?
- **Criticality**: How important is this decision to system architecture?
- **Stability**: How likely is this decision to change?
- **Blast Radius**: How many systems/teams are affected?
- **Reversibility**: How difficult/costly is it to reverse this decision?
- **Dependency Strength**: 0-100 scale for "how much" one decision depends on another

### Use Cases
- **Change Risk Assessment**: "What's the severity score of changing ADR-005? Is it above our 'critical' threshold?"
- **Prioritization**: "Which decisions should we review first based on criticality scores?"
- **Impact Prediction**: "If we change ADR-010 (severity: 85), what's the downstream impact score?"
- **Safe Deletion**: "Can we safely remove ADR-007 (dependency strength < 20 across all relationships)?"
- **Architecture Review**: "Show me all decisions with criticality > 80"

### Example Severity Calculation
```
ADR-008: Database Selection (PostgreSQL)
├── Cardinality: 45 (45 decisions reference this)
├── Criticality: 95 (core infrastructure decision)
├── Stability: 30 (unlikely to change)
├── Blast Radius: 85 (affects 8 teams, 23 services)
├── Reversibility: 20 (extremely difficult to reverse)
└── OVERALL SEVERITY: 87/100 (CRITICAL)

Change Impact Threshold: 75 (requires VP approval)
```

---

## Phase 5: Compartmentalization 📅 **PLANNED**

**Status**: Planned  
**Version**: 5.x (Target)

### Overview
Phase 5 transforms the system into an enterprise-grade platform with multi-tenancy, RBAC, and organizational structure support.

### Planned Features
- 📅 Decision tree compartmentalization (separate workspaces/domains)
- 📅 Role-Based Access Control (RBAC)
- 📅 Team and organization management
- 📅 Cross-compartment decision visibility controls
- 📅 Audit logging and compliance features
- 📅 Permission inheritance and delegation
- 📅 SSO/SAML integration
- 📅 Multi-tenant architecture

### Technical Objectives
- Database partitioning or schema separation
- Authentication and authorization framework
- Permission system design and implementation
- Audit trail infrastructure
- SSO provider integrations
- Admin dashboard and user management UI
- API key management for programmatic access

### RBAC Roles (Example)
- **Admin**: Full system access, user management
- **Architect**: Create/edit/delete decisions, manage relationships
- **Contributor**: Create/edit decisions, view all
- **Reviewer**: Comment on decisions, view all
- **Viewer**: Read-only access to permitted compartments
- **Auditor**: Read-only access with audit log visibility

### Compartmentalization Patterns
- **By Department**: Engineering, Product, Security, Legal
- **By Product**: Product A decisions, Product B decisions
- **By Lifecycle**: Active, Deprecated, Archived
- **By Security Level**: Public, Internal, Confidential, Restricted

### Use Cases
- **Enterprise Isolation**: "Engineering can see all decisions, but Legal only sees compliance-related ADRs"
- **Client Separation**: "Consultant firm managing decisions for multiple clients in isolated compartments"
- **Security Boundaries**: "Security-sensitive architectural decisions require special clearance"
- **Cross-Team Visibility**: "Team A can reference Team B's public decisions but can't edit them"
- **Audit Requirements**: "Track who accessed/modified which decisions for SOC 2 compliance"

### Security Considerations
- Encrypted data at rest and in transit
- Granular permission checks at API and UI layers
- Audit logging for all sensitive operations
- Rate limiting and abuse prevention
- Data retention and deletion policies
- Export controls and data sovereignty

---

## Feedback and Iteration

This roadmap is subject to change based on:
- User feedback and feature requests
- Technical discoveries during implementation
- Market needs and competitive landscape
- Resource availability and priorities

For questions or suggestions about the roadmap, please open an issue on GitHub.
