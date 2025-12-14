"""Data models for Architectural Decision Records (ADRs)."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ADRStatus(str, Enum):
    """Status of an ADR."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class RecordType(str, Enum):
    """Type of record (Decision or Principle)."""

    DECISION = "decision"
    PRINCIPLE = "principle"


class RetrievalMode(str, Enum):
    """RAG retrieval modes for LightRAG queries.

    Different modes provide different retrieval strategies:
    - LOCAL: Focuses on specific entities and their direct relationships
    - GLOBAL: Analyzes broader patterns and relationships across the knowledge graph
    - HYBRID: Combines local and global approaches for comprehensive results
    - NAIVE: Simple vector similarity search without knowledge graph
    - MIX: Integrates knowledge graph retrieval with vector search (recommended)
    - BYPASS: Direct LLM query without knowledge retrieval
    """

    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    NAIVE = "naive"
    MIX = "mix"
    BYPASS = "bypass"


class AnalysisPersona(str, Enum):
    """DEPRECATED: Different personas for ADR analysis.

    This enum is deprecated and maintained only for backwards compatibility with existing tests.
    Use string-based persona values instead (e.g., "technical_lead", "architect").
    Personas are now loaded dynamically from JSON configuration files in config/personas/.

    See config/personas/README.md for how to define custom personas.
    """

    TECHNICAL_LEAD = "technical_lead"
    BUSINESS_ANALYST = "business_analyst"
    RISK_MANAGER = "risk_manager"
    ARCHITECT = "architect"
    PRODUCT_MANAGER = "product_manager"
    CUSTOMER_SUPPORT = "customer_support"
    PHILOSOPHER = "philosopher"
    SECURITY_EXPERT = "security_expert"
    DEVOPS_ENGINEER = "devops_engineer"
    QA_ENGINEER = "qa_engineer"


class ADRMetadata(BaseModel):
    """Metadata for an ADR."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    title: str = Field(..., description="ADR title")
    status: ADRStatus = Field(default=ADRStatus.PROPOSED, description="Current status")
    record_type: RecordType = Field(
        default=RecordType.DECISION, description="Type of record"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )
    author: Optional[str] = Field(default=None, description="Author of the ADR")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    folder_path: Optional[str] = Field(
        default=None,
        description="Folder path for organizing ADRs (e.g., '/Architecture/Backend')",
    )
    related_adrs: List[UUID] = Field(
        default_factory=list, description="Related ADR IDs"
    )
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata fields"
    )


class ConsequencesStructured(BaseModel):
    """Structured consequences with positive and negative aspects."""

    positive: List[str] = Field(
        default_factory=list, description="Positive consequences"
    )
    negative: List[str] = Field(
        default_factory=list, description="Negative consequences"
    )


class OptionDetails(BaseModel):
    """Details about a considered option including pros and cons."""

    name: str = Field(..., description="Name of the option")
    description: Optional[str] = Field(
        default=None, description="Description of the option"
    )
    pros: List[str] = Field(
        default_factory=list, description="Advantages of this option"
    )
    cons: List[str] = Field(
        default_factory=list, description="Disadvantages of this option"
    )


class PrincipleDetails(BaseModel):
    """Details specific to Guiding Principles."""

    statement: str = Field(..., description="The core principle statement")
    rationale: str = Field(..., description="Why this principle is true/important")
    implications: List[str] = Field(
        default_factory=list, description="What this means for the organization"
    )
    counter_arguments: List[str] = Field(
        default_factory=list, description="Why it might not be true or exceptions"
    )
    proof_statements: List[str] = Field(
        default_factory=list,
        description="Examples or evidence supporting the principle",
    )
    exceptions: List[str] = Field(
        default_factory=list,
        description="Situations where this principle might not apply",
    )


class ADRContent(BaseModel):
    """Content structure for an ADR following the standard ADR template."""

    context_and_problem: str = Field(..., description="Context and problem statement")
    considered_options: List[str] = Field(
        default_factory=list, description="Options that were considered (simple list)"
    )
    decision_outcome: str = Field(
        ..., description="The chosen option and justification"
    )
    consequences: str = Field(..., description="Positive and negative consequences")
    decision_drivers: Optional[List[str]] = Field(
        default=None, description="Forces or concerns driving the decision"
    )
    confirmation: Optional[str] = Field(
        default=None, description="How compliance is confirmed"
    )
    pros_and_cons: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Pros and cons for each option (deprecated)"
    )
    options_details: Optional[List[OptionDetails]] = Field(
        default=None, description="Detailed options with pros/cons"
    )
    consequences_structured: Optional[ConsequencesStructured] = Field(
        default=None, description="Structured consequences"
    )
    principle_details: Optional[PrincipleDetails] = Field(
        default=None, description="Details specific to Guiding Principles"
    )
    referenced_adrs: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Referenced ADR information during generation. Each entry contains 'id', 'title', and 'summary' (truncated to 60 chars)",
    )
    more_information: Optional[str] = Field(
        default=None, description="Additional evidence, team agreement, etc."
    )
    original_generation_prompt: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original generation prompt used to create this ADR. Stored as dict with keys: title, context, problem_statement, constraints, stakeholders, tags, retrieval_mode. Used for refinement.",
    )


class ADR(BaseModel):
    """Complete ADR document."""

    metadata: ADRMetadata
    content: ADRContent
    persona_responses: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Individual persona responses during generation"
    )

    @classmethod
    def create(
        cls,
        title: str,
        context_and_problem: str,
        decision_outcome: str,
        consequences: str,
        considered_options: Optional[List[str]] = None,
        author: Optional[str] = None,
        decision_drivers: Optional[List[str]] = None,
        confirmation: Optional[str] = None,
        pros_and_cons: Optional[Dict[str, List[str]]] = None,
        more_information: Optional[str] = None,
        tags: Optional[List[str]] = None,
        record_type: RecordType = RecordType.DECISION,
    ) -> "ADR":
        """Create a new ADR."""
        metadata = ADRMetadata(
            title=title,
            author=author,
            tags=tags or [],
            record_type=record_type,
        )
        content = ADRContent(
            context_and_problem=context_and_problem,
            decision_drivers=decision_drivers,
            considered_options=considered_options or [],
            decision_outcome=decision_outcome,
            consequences=consequences,
            confirmation=confirmation,
            pros_and_cons=pros_and_cons,
            more_information=more_information,
        )
        return cls(metadata=metadata, content=content)

    def update_content(
        self,
        context_and_problem: Optional[str] = None,
        decision_drivers: Optional[List[str]] = None,
        considered_options: Optional[List[str]] = None,
        decision_outcome: Optional[str] = None,
        consequences: Optional[str] = None,
        confirmation: Optional[str] = None,
        pros_and_cons: Optional[Dict[str, List[str]]] = None,
        more_information: Optional[str] = None,
    ) -> None:
        """Update ADR content."""
        if context_and_problem is not None:
            self.content.context_and_problem = context_and_problem
        if decision_drivers is not None:
            self.content.decision_drivers = decision_drivers
        if considered_options is not None:
            self.content.considered_options = considered_options
        if decision_outcome is not None:
            self.content.decision_outcome = decision_outcome
        if consequences is not None:
            self.content.consequences = consequences
        if confirmation is not None:
            self.content.confirmation = confirmation
        if pros_and_cons is not None:
            self.content.pros_and_cons = pros_and_cons
        if more_information is not None:
            self.content.more_information = more_information
        self.metadata.updated_at = datetime.now(UTC)

    def add_tag(self, tag: str) -> None:
        """Add a tag to the ADR."""
        if tag not in self.metadata.tags:
            self.metadata.tags.append(tag)
            self.metadata.updated_at = datetime.now(UTC)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the ADR."""
        if tag in self.metadata.tags:
            self.metadata.tags.remove(tag)
            self.metadata.updated_at = datetime.now(UTC)

    def set_folder_path(self, folder_path: Optional[str]) -> None:
        """Set the folder path for organizing the ADR."""
        # Normalize path: ensure it starts with / and has no trailing /
        if folder_path:
            folder_path = "/" + folder_path.strip("/")
            if folder_path == "/":
                folder_path = None
        self.metadata.folder_path = folder_path
        self.metadata.updated_at = datetime.now(UTC)

    def add_related_adr(self, adr_id: UUID) -> None:
        """Add a related ADR."""
        if adr_id not in self.metadata.related_adrs:
            self.metadata.related_adrs.append(adr_id)

    def to_markdown(self) -> str:
        """Convert ADR to Markdown format following the standard ADR template."""
        lines = [
            f"# {self.metadata.title}",
            "",
            f"**Status:** {self.metadata.status.value}",
            f"**Created:** {self.metadata.created_at.isoformat()}",
            f"**Updated:** {self.metadata.updated_at.isoformat()}",
        ]

        if self.metadata.author:
            lines.append(f"**Author:** {self.metadata.author}")

        if self.metadata.tags:
            lines.append(f"**Tags:** {', '.join(self.metadata.tags)}")

        if self.metadata.related_adrs:
            related_ids = [str(adr_id) for adr_id in self.metadata.related_adrs]
            lines.append(f"**Related ADRs:** {', '.join(related_ids)}")

        lines.extend(
            [
                "",
                "## Context and Problem Statement",
                "",
                self.content.context_and_problem,
            ]
        )

        if self.content.decision_drivers:
            lines.extend(
                [
                    "",
                    "## Decision Drivers",
                    "",
                ]
            )
            for driver in self.content.decision_drivers:
                lines.append(f"* {driver}")

        lines.extend(
            [
                "",
                "## Considered Options",
                "",
            ]
        )
        for option in self.content.considered_options:
            lines.append(f"* {option}")

        lines.extend(
            [
                "",
                "## Decision Outcome",
                "",
                self.content.decision_outcome,
                "",
                "## Consequences",
                "",
                self.content.consequences,
            ]
        )

        if self.content.confirmation:
            lines.extend(
                [
                    "",
                    "## Confirmation",
                    "",
                    self.content.confirmation,
                ]
            )

        if self.content.pros_and_cons:
            lines.extend(
                [
                    "",
                    "## Pros and Cons of the Options",
                    "",
                ]
            )
            for option, items in self.content.pros_and_cons.items():
                lines.extend(
                    [
                        f"### {option}",
                        "",
                    ]
                )
                for item in items:
                    lines.append(f"* {item}")
                lines.append("")

        if self.content.more_information:
            lines.extend(
                [
                    "",
                    "## More Information",
                    "",
                    self.content.more_information,
                ]
            )

        return "\n".join(lines)


class AnalysisResult(BaseModel):
    """Result of ADR analysis."""

    adr_id: UUID
    persona: str
    analysis: str
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recommendations: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PersonaConfig(BaseModel):
    """Configuration for analysis personas."""

    name: str
    description: str
    system_prompt: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)


class AnalysisSections(BaseModel):
    """Sections of an ADR analysis."""

    strengths: str = Field(..., description="Key strengths identified in the ADR")
    weaknesses: str = Field(..., description="Key weaknesses or concerns")
    risks: str = Field(..., description="Potential risks or issues")
    recommendations: str = Field(
        ..., description="Suggestions for improvements or changes"
    )
    overall_assessment: str = Field(
        ..., description="Overall evaluation with justification"
    )


class ADRAnalysisResult(BaseModel):
    """Structured result of ADR analysis by a specific persona."""

    persona: str = Field(..., description="The persona that performed the analysis")
    timestamp: str = Field(
        ..., description="ISO timestamp of when analysis was performed"
    )
    sections: AnalysisSections = Field(
        ..., description="Analysis content organized by sections"
    )
    score: Optional[int] = Field(
        default=None, ge=1, le=10, description="Overall score from 1-10"
    )
    raw_response: str = Field(..., description="Raw response from the LLM")

    @property
    def score_display(self) -> str:
        """Get display string for the score."""
        if self.score is None:
            return "N/A"
        return f"{self.score}/10"


class ADRWithAnalysis(BaseModel):
    """ADR with associated analysis results."""

    adr: ADR
    analysis_results: Dict[str, ADRAnalysisResult] = Field(
        default_factory=dict, description="Analysis results by persona"
    )

    @property
    def average_score(self) -> Optional[float]:
        """Calculate average score across all personas."""
        scores = [
            result.score
            for result in self.analysis_results.values()
            if result.score is not None
        ]
        return sum(scores) / len(scores) if scores else None

    @property
    def consensus_recommendation(self) -> str:
        """Get the most common recommendation across personas."""
        recommendations = []
        for result in self.analysis_results.values():
            # Extract recommendation type from overall_assessment
            assessment = result.sections.overall_assessment.lower()
            if "accept" in assessment:
                recommendations.append("ACCEPT")
            elif "reject" in assessment:
                recommendations.append("REJECT")
            elif "modify" in assessment:
                recommendations.append("MODIFY")
            else:
                recommendations.append("REVIEW")

        if not recommendations:
            return "UNKNOWN"

        # Return most common recommendation
        from collections import Counter

        most_common = Counter(recommendations).most_common(1)[0][0]
        return most_common


class AnalysisBatchResult(BaseModel):
    """Results from analyzing multiple ADRs."""

    batch_id: str = Field(..., description="Unique identifier for this analysis batch")
    adrs_analyzed: List[ADRWithAnalysis] = Field(
        default_factory=list, description="ADRs with their analysis results"
    )
    personas_used: List[str] = Field(
        default_factory=list, description="Personas used in the analysis"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the batch was created",
    )
    total_analysis_time: Optional[float] = Field(
        default=None, description="Total time spent on analysis in seconds"
    )

    @property
    def average_score(self) -> Optional[float]:
        """Calculate average score across all ADRs and personas."""
        scores = []
        for adr_analysis in self.adrs_analyzed:
            if adr_analysis.average_score is not None:
                scores.append(adr_analysis.average_score)
        return sum(scores) / len(scores) if scores else None


class ADRGenerationPrompt(BaseModel):
    """Input prompt for ADR generation."""

    title: str = Field(..., description="Desired title for the ADR")
    context: str = Field(..., description="Context and background information")
    problem_statement: str = Field(
        ..., description="The problem that needs to be solved"
    )
    record_type: RecordType = Field(
        default=RecordType.DECISION, description="Type of record to generate"
    )
    constraints: Optional[List[str]] = Field(
        default=None, description="Constraints or requirements"
    )
    stakeholders: Optional[List[str]] = Field(
        default=None, description="Key stakeholders involved"
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Relevant tags for categorization"
    )
    retrieval_mode: str = Field(
        default="naive",
        description="RAG retrieval mode: local, global, hybrid, naive, mix, or bypass",
    )
    status_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter referenced ADRs by status values (e.g., ['accepted', 'proposed']). If None, all statuses are included.",
    )


class ADRGenerationOptions(BaseModel):
    """Options that were considered during ADR generation."""

    option_name: str = Field(..., description="Name of the option")
    description: str = Field(..., description="Description of the option")
    pros: List[str] = Field(
        default_factory=list, description="Advantages of this option"
    )
    cons: List[str] = Field(
        default_factory=list, description="Disadvantages of this option"
    )


class ADRGenerationResult(BaseModel):
    """Result of ADR generation process."""

    prompt: ADRGenerationPrompt
    generated_title: str = Field(..., description="Generated ADR title")
    context_and_problem: str = Field(
        ..., description="Generated context and problem statement"
    )
    considered_options: List[ADRGenerationOptions] = Field(
        default_factory=list, description="Options that were considered"
    )
    decision_outcome: str = Field(
        ..., description="The chosen option and justification"
    )
    consequences: str = Field(..., description="Positive and negative consequences")
    consequences_structured: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Structured consequences with positive and negative arrays",
    )
    principle_details: Optional[PrincipleDetails] = Field(
        default=None, description="Details specific to Guiding Principles"
    )
    decision_drivers: List[str] = Field(
        default_factory=list, description="Forces driving the decision"
    )
    confidence_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in the generated ADR"
    )
    related_context: List[str] = Field(
        default_factory=list, description="Related context retrieved from vector DB"
    )
    referenced_adrs: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Referenced ADR information during generation. Each entry contains 'id', 'title', and 'summary'",
    )
    personas_used: List[str] = Field(
        default_factory=list, description="Personas involved in generation"
    )
    persona_responses: Optional[List["PersonaSynthesisInput"]] = Field(
        default=None, description="Individual persona responses"
    )
    original_prompt_text: Optional[str] = Field(
        default=None, description="Original prompt text for refinement purposes"
    )


class PersonaSynthesisInput(BaseModel):
    """Input for persona synthesis during ADR generation."""

    persona: str = Field(..., description="The persona providing input")
    perspective: str = Field(
        ..., description="The persona's perspective on the decision"
    )
    recommended_option: Optional[str] = Field(
        default=None, description="Option recommended by this persona"
    )
    proposed_principle: Optional[str] = Field(
        default=None, description="Principle proposed by this persona (for Principles)"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Detailed reasoning from this persona"
    )
    rationale: Optional[str] = Field(
        default=None, description="Rationale for the principle (alias for reasoning)"
    )
    concerns: List[str] = Field(
        default_factory=list, description="Key concerns raised by this persona"
    )
    requirements: List[str] = Field(
        default_factory=list, description="Requirements identified by this persona"
    )
    implications: List[str] = Field(
        default_factory=list, description="Implications identified by this persona"
    )
    counter_arguments: List[str] = Field(
        default_factory=list, description="Counter arguments identified by this persona"
    )
    proof_statements: List[str] = Field(
        default_factory=list, description="Proof statements identified by this persona"
    )
    exceptions: List[str] = Field(
        default_factory=list, description="Exceptions identified by this persona"
    )
    original_prompt_text: Optional[str] = Field(
        default=None,
        description="Original prompt text used to generate this persona's response",
    )
    refinement_history: List[str] = Field(
        default_factory=list,
        description="History of refinement prompts applied to this persona",
    )


class ADRGenerationBatch(BaseModel):
    """Batch of ADR generation requests."""

    batch_id: str = Field(
        ..., description="Unique identifier for this generation batch"
    )
    prompts: List[ADRGenerationPrompt] = Field(
        default_factory=list, description="Generation prompts in this batch"
    )
    personas_to_use: List[str] = Field(
        default_factory=list, description="Personas to involve in generation"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the batch was created",
    )
    results: List[ADRGenerationResult] = Field(
        default_factory=list, description="Generated ADR results"
    )


class PersonaRefinement(BaseModel):
    """Refinement request for a specific persona."""

    persona: str = Field(..., description="The persona to refine")
    refinement_prompt: str = Field(
        ..., description="Additional prompt to refine the persona's perspective"
    )


class RefinePersonasRequest(BaseModel):
    """Request to refine specific personas in an ADR."""

    refinements: List[PersonaRefinement] = Field(
        ..., description="List of persona refinements to apply"
    )
    persona_provider_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of persona name to provider ID override",
    )
    synthesis_provider_id: Optional[str] = Field(
        default=None,
        description="Optional provider ID for synthesis generation",
    )


class ConflictType(str, Enum):
    """Types of conflicts between ADRs."""

    CONTRADICTORY_DECISIONS = "contradictory_decisions"
    OVERLAPPING_SCOPE = "overlapping_scope"
    INCONSISTENT_ASSUMPTIONS = "inconsistent_assumptions"
    COMPETING_TECHNOLOGIES = "competing_technologies"
    RESOURCE_CONFLICTS = "resource_conFLICTS"


class ADRConflict(BaseModel):
    """Represents a conflict between ADRs."""

    conflict_type: ConflictType = Field(..., description="Type of conflict detected")
    primary_adr_id: UUID = Field(
        ..., description="ID of the primary ADR in the conflict"
    )
    conflicting_adr_id: UUID = Field(..., description="ID of the conflicting ADR")
    description: str = Field(..., description="Description of the conflict")
    severity: str = Field(
        ..., description="Severity level: low, medium, high, critical"
    )
    impact_areas: List[str] = Field(
        default_factory=list, description="Areas impacted by the conflict"
    )
    resolution_suggestions: List[str] = Field(
        default_factory=list, description="Suggested ways to resolve the conflict"
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the conflict was detected",
    )


class ContinuityAssessment(BaseModel):
    """Assessment of how well an ADR maintains continuity with related decisions."""

    adr_id: UUID = Field(..., description="ID of the ADR being assessed")
    overall_score: float = Field(
        ge=0.0, le=1.0, description="Overall continuity score (0-1)"
    )
    alignment_score: float = Field(
        ge=0.0, le=1.0, description="How well aligned with related ADRs"
    )
    consistency_score: float = Field(
        ge=0.0, le=1.0, description="Internal consistency of the ADR"
    )
    evolution_score: float = Field(
        ge=0.0, le=1.0, description="How well the decision has evolved"
    )
    strengths: List[str] = Field(
        default_factory=list, description="Continuity strengths"
    )
    concerns: List[str] = Field(default_factory=list, description="Continuity concerns")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the assessment was performed",
    )


class ReassessmentRecommendation(BaseModel):
    """Recommendation for re-assessing an ADR."""

    adr_id: UUID = Field(..., description="ID of the ADR to re-assess")
    priority: str = Field(..., description="Priority level: low, medium, high, urgent")
    reason: str = Field(..., description="Reason for recommending re-assessment")
    triggers: List[str] = Field(
        default_factory=list, description="What triggered this recommendation"
    )
    suggested_actions: List[str] = Field(
        default_factory=list, description="Suggested actions to take"
    )
    estimated_effort: str = Field(
        ..., description="Estimated effort required: small, medium, large"
    )
    business_impact: str = Field(
        ..., description="Potential business impact if not addressed"
    )
    recommended_by: List[str] = Field(
        default_factory=list, description="Personas that recommended this"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the recommendation was created",
    )


class ContextualAnalysisResult(BaseModel):
    """Results of contextual analysis of an ADR."""

    target_adr: ADR = Field(..., description="The ADR being analyzed")
    related_adrs: List[ADR] = Field(
        default_factory=list, description="Related ADRs found in context"
    )
    conflicts: List[ADRConflict] = Field(
        default_factory=list, description="Conflicts detected"
    )
    continuity_assessment: ContinuityAssessment = Field(
        ..., description="Continuity assessment results"
    )
    reassessment_recommendations: List[ReassessmentRecommendation] = Field(
        default_factory=list, description="Re-assessment recommendations"
    )
    persona_analyses: Dict[str, ADRAnalysisResult] = Field(
        default_factory=dict, description="Analysis from each persona"
    )
    overall_assessment: str = Field(..., description="Overall assessment summary")
    key_findings: List[str] = Field(
        default_factory=list, description="Key findings from the analysis"
    )
    action_items: List[str] = Field(
        default_factory=list, description="Recommended action items"
    )
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the analysis was performed",
    )
    analysis_duration: Optional[float] = Field(
        default=None, description="Time taken for analysis in seconds"
    )


class AnalysisReport(BaseModel):
    """Structured analysis report for ADR contextual analysis."""

    report_id: str = Field(..., description="Unique identifier for this report")
    title: str = Field(..., description="Report title")
    executive_summary: str = Field(..., description="Executive summary of findings")
    target_adr_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Summary of the target ADR"
    )
    contextual_analysis: ContextualAnalysisResult = Field(
        ..., description="Detailed contextual analysis"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Key recommendations"
    )
    next_steps: List[str] = Field(
        default_factory=list, description="Suggested next steps"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the report was generated",
    )
    report_format: str = Field(
        default="markdown", description="Format of the report: markdown, html, json"
    )

    def to_markdown(self) -> str:
        """Convert the report to markdown format."""
        lines = [
            f"# {self.title}",
            "",
            f"**Report ID:** {self.report_id}",
            f"**Generated:** {self.generated_at.isoformat()}",
            "",
            "## Executive Summary",
            "",
            self.executive_summary,
            "",
            "## Target ADR Summary",
            "",
            f"- **Title:** {self.target_adr_summary.get('title', 'N/A')}",
            f"- **Status:** {self.target_adr_summary.get('status', 'N/A')}",
            f"- **Author:** {self.target_adr_summary.get('author', 'N/A')}",
            f"- **Created:** {self.target_adr_summary.get('created_at', 'N/A')}",
        ]

        if self.contextual_analysis.conflicts:
            lines.extend(
                [
                    "",
                    "## Conflicts Detected",
                    "",
                    f"Found {len(self.contextual_analysis.conflicts)} potential conflicts:",
                    "",
                ]
            )
            for i, conflict in enumerate(self.contextual_analysis.conflicts, 1):
                lines.extend(
                    [
                        f"### Conflict {i}: {conflict.conflict_type.value.replace('_', ' ').title()}",
                        "",
                        f"**Severity:** {conflict.severity}",
                        f"**Description:** {conflict.description}",
                        "",
                        "**Impact Areas:**",
                        *[f"- {area}" for area in conflict.impact_areas],
                        "",
                        "**Resolution Suggestions:**",
                        *[
                            f"- {suggestion}"
                            for suggestion in conflict.resolution_suggestions
                        ],
                        "",
                    ]
                )

        lines.extend(
            [
                "",
                "## Continuity Assessment",
                "",
                f"**Overall Score:** {self.contextual_analysis.continuity_assessment.overall_score:.1%}",
                f"**Alignment Score:** {self.contextual_analysis.continuity_assessment.alignment_score:.1%}",
                f"**Consistency Score:** {self.contextual_analysis.continuity_assessment.consistency_score:.1%}",
                "",
                "**Strengths:**",
                *[
                    f"- {strength}"
                    for strength in self.contextual_analysis.continuity_assessment.strengths
                ],
                "",
                "**Concerns:**",
                *[
                    f"- {concern}"
                    for concern in self.contextual_analysis.continuity_assessment.concerns
                ],
            ]
        )

        if self.contextual_analysis.reassessment_recommendations:
            lines.extend(
                [
                    "",
                    "## Re-assessment Recommendations",
                    "",
                    f"Found {len(self.contextual_analysis.reassessment_recommendations)} recommendations:",
                    "",
                ]
            )
            for i, rec in enumerate(
                self.contextual_analysis.reassessment_recommendations, 1
            ):
                lines.extend(
                    [
                        f"### Recommendation {i}",
                        "",
                        f"**Priority:** {rec.priority}",
                        f"**Reason:** {rec.reason}",
                        "",
                        "**Suggested Actions:**",
                        *[f"- {action}" for action in rec.suggested_actions],
                        "",
                        f"**Estimated Effort:** {rec.estimated_effort}",
                        f"**Business Impact:** {rec.business_impact}",
                        "",
                    ]
                )

        if self.recommendations:
            lines.extend(
                [
                    "",
                    "## Key Recommendations",
                    "",
                    *[f"- {rec}" for rec in self.recommendations],
                    "",
                ]
            )

        if self.next_steps:
            lines.extend(
                [
                    "",
                    "## Next Steps",
                    "",
                    *[f"- {step}" for step in self.next_steps],
                    "",
                ]
            )

        return "\n".join(lines)
