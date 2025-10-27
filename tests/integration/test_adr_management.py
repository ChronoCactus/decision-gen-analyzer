"""Tests for AI-powered ADR analysis components."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

from src.models import ADR, ADRAnalysisResult, ADRWithAnalysis
from src.adr_validation import ADRAnalysisService, AnalysisPersona
from src.adr_generation import ADRGenerationService
from src.models import ADRGenerationPrompt, ADRGenerationResult, ADRGenerationOptions
from src.persona_manager import PersonaManager


class TestADRAnalysisService:
    """Test AI-powered ADR analysis service."""

    @pytest.fixture
    def mock_llama_client(self):
        """Mock Llama client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_lightrag_client(self):
        """Mock LightRAG client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def analysis_service(self, mock_llama_client, mock_lightrag_client):
        """Create ADR analysis service with mocked clients."""
        return ADRAnalysisService(mock_llama_client, mock_lightrag_client)

    @pytest.fixture
    def sample_adr(self):
        """Create a sample ADR for testing."""
        return ADR.create(
            title="Test ADR for AI Analysis",
            context_and_problem="We need to choose a database technology for our new microservice architecture",
            decision_outcome="Use PostgreSQL for its robust features and ecosystem support",
            consequences="Better data integrity, advanced querying capabilities, but higher operational complexity",
            author="Test Author",
            tags=["database", "architecture"],
            considered_options=["PostgreSQL", "MySQL", "MongoDB"],
            decision_drivers=["Data consistency requirements", "Complex querying needs"]
        )

    @pytest.mark.asyncio
    async def test_analyze_adr_single_persona(self, analysis_service, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test ADR analysis with a single persona."""
        # Mock context retrieval
        mock_lightrag_client.retrieve_documents.return_value = [
            {"content": "Related ADR about database choices..."}
        ]

        # Mock AI response (JSON format)
        mock_response = '''{
  "strengths": "Good technical justification, considers multiple options",
  "weaknesses": "Missing cost analysis, no migration plan",
  "risks": "Vendor lock-in potential, learning curve for team",
  "recommendations": "Add cost-benefit analysis, include migration strategy",
  "overall_assessment": "MODIFY - Good foundation but needs more detail",
  "score": 7
}'''
        mock_llama_client.generate.return_value = mock_response

        result = await analysis_service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

        assert isinstance(result, ADRAnalysisResult)
        assert result.persona == "technical_lead"
        assert result.score == 7
        assert "Good technical justification" in result.sections.strengths
        assert "cost analysis" in result.sections.weaknesses
        assert "migration strategy" in result.sections.recommendations
        assert result.score_display == "7/10"

        mock_llama_client.generate.assert_called_once()
        mock_lightrag_client.retrieve_documents.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_adr_multiple_personas(self, analysis_service, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test ADR analysis with multiple personas."""
        # Mock context retrieval
        mock_lightrag_client.retrieve_documents.return_value = []

        # Mock AI responses for different personas (JSON format)
        def mock_generate(*args, **kwargs):
            prompt = args[0] if args else ""
            if "Technical Lead" in prompt:
                return '''{"strengths": "Good technical foundation", "weaknesses": "Missing details", "risks": "Technical risks", "recommendations": "Add technical details", "overall_assessment": "MODIFY", "score": 8}'''
            elif "Business Analyst" in prompt:
                return '''{"strengths": "Business value", "weaknesses": "Cost concerns", "risks": "Financial risks", "recommendations": "Add cost analysis", "overall_assessment": "MODIFY", "score": 6}'''
            elif "Risk Manager" in prompt:
                return '''{"strengths": "Risk awareness", "weaknesses": "Incomplete risk assessment", "risks": "High operational risks", "recommendations": "Comprehensive risk analysis", "overall_assessment": "MODIFY", "score": 7}'''
            else:
                return '''{"strengths": "Default", "weaknesses": "Default", "risks": "Default", "recommendations": "Default", "overall_assessment": "REVIEW", "score": 5}'''

        mock_llama_client.generate.side_effect = mock_generate

        personas = [AnalysisPersona.TECHNICAL_LEAD, AnalysisPersona.BUSINESS_ANALYST, AnalysisPersona.RISK_MANAGER]
        result = await analysis_service.analyze_adr_with_multiple_personas(sample_adr, personas)

        assert isinstance(result, ADRWithAnalysis)
        assert len(result.analysis_results) == 3
        assert "technical_lead" in result.analysis_results
        assert "business_analyst" in result.analysis_results
        assert "risk_manager" in result.analysis_results

        assert result.analysis_results["technical_lead"].score == 8
        assert result.analysis_results["business_analyst"].score == 6
        assert result.analysis_results["risk_manager"].score == 7

        # Test computed properties
        assert result.average_score == 7.0
        assert result.consensus_recommendation == "MODIFY"

    @pytest.mark.asyncio
    async def test_context_retrieval_failure(self, analysis_service, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test analysis when context retrieval fails."""
        # Mock context retrieval failure
        mock_lightrag_client.retrieve_documents.side_effect = Exception("Connection failed")

        # Mock AI response
        mock_llama_client.generate.return_value = "SCORE: 5\nANALYSIS WITHOUT CONTEXT..."

        result = await analysis_service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

        assert isinstance(result, ADRAnalysisResult)
        assert result.persona == "technical_lead"
        assert result.score == 5  # Should extract from text fallback
        # Should still work even with context failure
        assert result.raw_response == "SCORE: 5\nANALYSIS WITHOUT CONTEXT..."

    def test_persona_instructions(self, analysis_service):
        """Test that persona instructions are properly defined."""
        for persona in AnalysisPersona:
            instructions = analysis_service._get_persona_instructions(persona)
            assert "role" in instructions
            assert "instructions" in instructions
            assert len(instructions["instructions"]) > 0

    def test_analysis_prompt_construction(self, analysis_service, sample_adr):
        """Test that analysis prompts are properly constructed."""
        context = "Sample context from LightRAG"
        prompt = analysis_service._build_analysis_prompt(sample_adr, AnalysisPersona.TECHNICAL_LEAD, context)

        assert sample_adr.metadata.title in prompt
        assert sample_adr.content.context_and_problem in prompt
        assert sample_adr.content.decision_outcome in prompt
        assert "Technical Lead" in prompt
        assert context in prompt
        assert '"strengths"' in prompt  # JSON format
        assert '"score"' in prompt

    @pytest.mark.asyncio
    async def test_error_handling_and_retries(self, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test error handling and retry logic."""
        # Create service with low retry count for testing
        service = ADRAnalysisService(mock_llama_client, mock_lightrag_client, max_retries=2)

        # Mock context retrieval
        mock_lightrag_client.retrieve_documents.return_value = []

        # Mock LLM failures followed by success
        mock_llama_client.generate.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            '''{"strengths": "Good", "weaknesses": "Some", "risks": "Low", "recommendations": "Monitor", "overall_assessment": "ACCEPT", "score": 8}'''
        ]

        result = await service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

        assert isinstance(result, ADRAnalysisResult)
        assert result.score == 8
        assert mock_llama_client.generate.call_count == 3  # Two failures + one success

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test timeout handling in analysis."""
        # Create service with short timeout
        service = ADRAnalysisService(mock_llama_client, mock_lightrag_client, analysis_timeout=0.1)

        mock_lightrag_client.retrieve_documents.return_value = []

        # Mock a slow response that will timeout
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.2)  # Longer than timeout
            return '''{"strengths": "Good", "weaknesses": "Some", "risks": "Low", "recommendations": "Monitor", "overall_assessment": "ACCEPT", "score": 8}'''

        mock_llama_client.generate.side_effect = slow_response

        with pytest.raises(RuntimeError, match="timed out"):
            await service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

    @pytest.mark.asyncio
    async def test_context_relevance_scoring(self, analysis_service, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test that context relevance scoring works properly."""
        # Mock different context results with varying relevance
        mock_lightrag_client.retrieve_documents.side_effect = [
            [{"content": f"PostgreSQL is great for {sample_adr.content.context_and_problem[:50]}..."}],
            [{"content": "Unrelated content about weather"}],
            [{"content": f"Database choice impacts {sample_adr.metadata.tags[0]} architecture"}]
        ]

        mock_llama_client.generate.return_value = '''{"strengths": "Good", "weaknesses": "Some", "risks": "Low", "recommendations": "Monitor", "overall_assessment": "ACCEPT", "score": 8}'''

        result = await analysis_service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

        assert isinstance(result, ADRAnalysisResult)
        # Should have called retrieve_documents multiple times for comprehensive search
        assert mock_lightrag_client.retrieve_documents.call_count >= 3

    @pytest.mark.asyncio
    async def test_json_parsing_fallback(self, analysis_service, mock_llama_client, mock_lightrag_client, sample_adr):
        """Test fallback to text parsing when JSON parsing fails."""
        mock_lightrag_client.retrieve_documents.return_value = []

        # Mock invalid JSON response
        mock_llama_client.generate.return_value = "INVALID JSON RESPONSE\nSCORE: 6\nSTRENGTHS: Some good points"

        result = await analysis_service.analyze_adr(sample_adr, AnalysisPersona.TECHNICAL_LEAD)

        # Should still return a result using fallback parsing
        assert isinstance(result, ADRAnalysisResult)
        assert result.score == 6  # Should extract from text

    @pytest.mark.asyncio
    async def test_comprehensive_multi_persona_analysis(self, mock_llama_client, mock_lightrag_client):
        """Integration test for comprehensive multi-persona analysis."""
        service = ADRAnalysisService(mock_llama_client, mock_lightrag_client)

        # Create a more complex ADR
        complex_adr = ADR.create(
            title="Microservices Architecture Decision",
            context_and_problem="Our monolithic application is becoming difficult to maintain and deploy. We need to decide whether to adopt microservices architecture.",
            decision_outcome="Adopt microservices with domain-driven design principles",
            consequences="Better scalability and maintainability, but increased operational complexity",
            author="Architecture Team",
            tags=["architecture", "microservices", "scalability"],
            considered_options=["Monolithic", "Microservices", "Serverless"],
            decision_drivers=["Scalability requirements", "Team autonomy", "Technology diversity"]
        )

        mock_lightrag_client.retrieve_documents.return_value = [
            {"content": "Previous ADR about microservices migration challenges..."},
            {"content": "Domain-driven design best practices..."}
        ]

        # Mock comprehensive responses for all personas
        persona_responses = {
            "technical_lead": '''{"strengths": "Technical benefits clear", "weaknesses": "Complexity concerns", "risks": "Distributed system challenges", "recommendations": "Start small", "overall_assessment": "ACCEPT with caution", "score": 8}''',
            "business_analyst": '''{"strengths": "Business value high", "weaknesses": "Cost implications", "risks": "ROI uncertainty", "recommendations": "Detailed cost analysis", "overall_assessment": "MODIFY for cost clarity", "score": 7}''',
            "architect": '''{"strengths": "Architecturally sound", "weaknesses": "Design complexity", "risks": "Integration challenges", "recommendations": "Strong governance", "overall_assessment": "ACCEPT with governance", "score": 9}''',
        }

        def mock_generate(*args, **kwargs):
            prompt = args[0]
            if "Technical Lead" in prompt:
                return persona_responses["technical_lead"]
            elif "Business Analyst" in prompt:
                return persona_responses["business_analyst"]
            elif "Architect" in prompt:
                return persona_responses["architect"]
            return '''{"strengths": "Default", "weaknesses": "Default", "risks": "Default", "recommendations": "Default", "overall_assessment": "REVIEW", "score": 5}'''

        mock_llama_client.generate.side_effect = mock_generate

        result = await service.analyze_adr_with_multiple_personas(
            complex_adr,
            [AnalysisPersona.TECHNICAL_LEAD, AnalysisPersona.BUSINESS_ANALYST, AnalysisPersona.ARCHITECT]
        )

        assert isinstance(result, ADRWithAnalysis)
        assert len(result.analysis_results) == 3
        assert result.average_score == 8.0  # (8+7+9)/3
        assert result.consensus_recommendation in ["ACCEPT", "MODIFY"]  # Most common recommendation


class TestADRAnalysisModels:
    """Test ADR analysis data models."""

    @pytest.fixture
    def sample_adr(self):
        """Create a sample ADR for testing."""
        return ADR.create(
            title="Test ADR for AI Analysis",
            context_and_problem="We need to choose a database technology for our new microservice architecture",
            decision_outcome="Use PostgreSQL for its robust features and ecosystem support",
            consequences="Better data integrity, advanced querying capabilities, but higher operational complexity",
            author="Test Author",
            tags=["database", "architecture"],
            considered_options=["PostgreSQL", "MySQL", "MongoDB"],
            decision_drivers=["Data consistency requirements", "Complex querying needs"]
        )

    def test_analysis_result_creation(self):
        """Test creation of analysis result."""
        from datetime import datetime, UTC
        result = ADRAnalysisResult(
            persona="technical_lead",
            timestamp=datetime.now(UTC).isoformat(),
            sections={
                "strengths": "Good",
                "weaknesses": "Some",
                "risks": "Low",
                "recommendations": "Monitor",
                "overall_assessment": "ACCEPT"
            },
            score=8,
            raw_response="AI response here"
        )

        assert result.persona == "technical_lead"
        assert result.score == 8
        assert result.sections.strengths == "Good"

    def test_adr_with_analysis_creation(self, sample_adr):
        """Test creation of ADR with analysis."""
        from datetime import datetime, UTC
        analysis = ADRAnalysisResult(
            persona="technical_lead",
            timestamp=datetime.now(UTC).isoformat(),
            sections={
                "strengths": "Good foundation",
                "weaknesses": "Missing details",
                "risks": "Technical risks",
                "recommendations": "Add more details",
                "overall_assessment": "MODIFY"
            },
            score=7,
            raw_response="Analysis response"
        )

        adr_with_analysis = ADRWithAnalysis(
            adr=sample_adr,
            analysis_results={"technical_lead": analysis}
        )

        assert adr_with_analysis.adr == sample_adr
        assert len(adr_with_analysis.analysis_results) == 1
        assert adr_with_analysis.analysis_results["technical_lead"].score == 7


class TestADRGenerationService:
    """Test ADR generation service."""

    @pytest.fixture
    def mock_llama_client(self):
        """Mock Llama client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_lightrag_client(self):
        """Mock LightRAG client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_persona_manager(self):
        """Mock persona manager."""
        manager = MagicMock(spec=PersonaManager)
        return manager

    @pytest.fixture
    def generation_service(self, mock_llama_client, mock_lightrag_client, mock_persona_manager):
        """Create ADR generation service with mocked dependencies."""
        return ADRGenerationService(mock_llama_client, mock_lightrag_client, mock_persona_manager)

    @pytest.fixture
    def sample_generation_prompt(self):
        """Create a sample generation prompt."""
        return ADRGenerationPrompt(
            title="Database Selection for Microservices",
            context="Building a new microservices architecture",
            problem_statement="Choose appropriate database technology",
            constraints=["Must support ACID", "High availability required"],
            stakeholders=["Development Team", "Operations Team"],
            tags=["database", "microservices"]
        )

    @pytest.mark.asyncio
    async def test_generate_adr_fallback(self, generation_service, mock_llama_client, mock_lightrag_client, mock_persona_manager, sample_generation_prompt):
        """Test ADR generation with fallback when LLM fails."""
        # Mock failures
        mock_lightrag_client.query.return_value = {"data": []}
        mock_llama_client.generate.side_effect = Exception("LLM unavailable")
        mock_persona_manager.get_persona_config.return_value = MagicMock(
            name="Test Persona",
            description="Test description",
            focus_areas=["test"],
            evaluation_criteria=["test"]
        )

        result = await generation_service.generate_adr(
            sample_generation_prompt,
            personas=[AnalysisPersona.TECHNICAL_LEAD]
        )

        assert isinstance(result, ADRGenerationResult)
        assert result.generated_title == sample_generation_prompt.title
        assert result.confidence_score == 0.5  # Fallback confidence
        assert len(result.considered_options) >= 1

    def test_validate_generation_result_perfect(self, generation_service):
        """Test validation of a high-quality generation result."""
        result = ADRGenerationResult(
            prompt=ADRGenerationPrompt(
                title="Test ADR",
                context="Context",
                problem_statement="Problem"
            ),
            generated_title="Comprehensive Database Selection Strategy",
            context_and_problem="Detailed context and problem statement with sufficient length for proper analysis.",
            considered_options=[
                ADRGenerationOptions(
                    option_name="PostgreSQL",
                    description="Robust RDBMS",
                    pros=["ACID compliance", "Rich features"],
                    cons=["Complex setup"]
                ),
                ADRGenerationOptions(
                    option_name="MySQL",
                    description="Popular RDBMS",
                    pros=["Easy to use"],
                    cons=["Limited features"]
                ),
                ADRGenerationOptions(
                    option_name="MongoDB",
                    description="Document database",
                    pros=["Flexible schema"],
                    cons=["No ACID"]
                )
            ],
            decision_outcome="Choose PostgreSQL for its comprehensive feature set and ACID compliance requirements.",
            consequences="Positive: Strong data integrity, advanced features. Negative: Higher complexity.",
            decision_drivers=["Data consistency", "Complex queries", "ACID requirements"],
            confidence_score=0.9,
            personas_used=["technical_lead", "architect", "security_expert"]
        )

        validation = generation_service.validate_generation_result(result)

        assert validation["assessment"] == "Excellent"
        assert validation["overall_score"] >= 0.8
        assert len(validation["strengths"]) > 0
        assert len(validation["issues"]) == 0

    def test_validate_generation_result_poor(self, generation_service):
        """Test validation of a low-quality generation result."""
        result = ADRGenerationResult(
            prompt=ADRGenerationPrompt(
                title="Test ADR",
                context="Context",
                problem_statement="Problem"
            ),
            generated_title="X",  # Too short
            context_and_problem="Short",  # Too brief
            considered_options=[],  # No options
            decision_outcome="",  # Empty
            consequences="",  # Empty
            decision_drivers=[],  # No drivers
            confidence_score=None,  # No confidence
            personas_used=[]  # No personas
        )

        validation = generation_service.validate_generation_result(result)

        assert validation["assessment"] == "Needs improvement"
        assert validation["overall_score"] < 0.4
        assert len(validation["issues"]) > 0
        assert "Title is too short" in validation["issues"]

    def test_convert_to_adr(self, generation_service, sample_generation_prompt):
        """Test conversion of generation result to ADR object."""
        result = ADRGenerationResult(
            prompt=sample_generation_prompt,
            generated_title="Database Technology Decision",
            context_and_problem="Context and problem details",
            considered_options=[
                ADRGenerationOptions(
                    option_name="PostgreSQL",
                    description="Chosen option",
                    pros=["Good"],
                    cons=["Complex"]
                )
            ],
            decision_outcome="Selected PostgreSQL",
            consequences="Benefits outweigh drawbacks",
            decision_drivers=["Performance", "Features"],
            confidence_score=0.8,
            personas_used=["technical_lead"]
        )

        adr = generation_service.convert_to_adr(result, author="Test Author")

        assert adr.metadata.title == "Database Technology Decision"
        assert adr.metadata.author == "Test Author"
        assert adr.metadata.tags == sample_generation_prompt.tags
        assert adr.content.context_and_problem == result.context_and_problem
        assert adr.content.decision_outcome == result.decision_outcome
        assert len(adr.content.considered_options) == 1
