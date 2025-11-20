"""Tests for data models."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.models import (
    ADR,
    ADRContent,
    ADRMetadata,
    ADRStatus,
    AnalysisPersona,
    ConsequencesStructured,
    OptionDetails,
)


class TestADRStatus:
    """Test ADRStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert ADRStatus.PROPOSED.value == "proposed"
        assert ADRStatus.ACCEPTED.value == "accepted"
        assert ADRStatus.DEPRECATED.value == "deprecated"
        assert ADRStatus.SUPERSEDED.value == "superseded"
        assert ADRStatus.REJECTED.value == "rejected"

    def test_status_from_string(self):
        """Test status can be created from string."""
        status = ADRStatus("proposed")
        assert status == ADRStatus.PROPOSED


class TestAnalysisPersona:
    """Test AnalysisPersona enum."""

    def test_persona_values(self):
        """Test persona values are defined."""
        assert AnalysisPersona.TECHNICAL_LEAD.value == "technical_lead"
        assert AnalysisPersona.BUSINESS_ANALYST.value == "business_analyst"
        assert AnalysisPersona.SECURITY_EXPERT.value == "security_expert"

    def test_all_personas_exist(self):
        """Test all expected personas exist."""
        expected_personas = [
            "technical_lead",
            "business_analyst",
            "risk_manager",
            "architect",
            "product_manager",
            "customer_support",
            "philosopher",
            "security_expert",
            "devops_engineer",
            "qa_engineer",
        ]
        persona_values = [p.value for p in AnalysisPersona]
        for expected in expected_personas:
            assert expected in persona_values


class TestADRMetadata:
    """Test ADRMetadata model."""

    def test_create_metadata_with_defaults(self):
        """Test creating metadata with default values."""
        metadata = ADRMetadata(title="Test ADR")

        assert metadata.title == "Test ADR"
        assert metadata.status == ADRStatus.PROPOSED
        assert isinstance(metadata.id, UUID)
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)
        assert metadata.author is None
        assert metadata.tags == []
        assert metadata.related_adrs == []
        assert metadata.custom_fields == {}

    def test_create_metadata_with_all_fields(self):
        """Test creating metadata with all fields specified."""
        adr_id = uuid4()
        created_at = datetime.now(UTC)
        related_id = uuid4()

        metadata = ADRMetadata(
            id=adr_id,
            title="Test ADR",
            status=ADRStatus.ACCEPTED,
            created_at=created_at,
            updated_at=created_at,
            author="Test Author",
            tags=["architecture", "database"],
            related_adrs=[related_id],
            custom_fields={"custom_key": "custom_value"},
        )

        assert metadata.id == adr_id
        assert metadata.title == "Test ADR"
        assert metadata.status == ADRStatus.ACCEPTED
        assert metadata.created_at == created_at
        assert metadata.author == "Test Author"
        assert metadata.tags == ["architecture", "database"]
        assert metadata.related_adrs == [related_id]
        assert metadata.custom_fields == {"custom_key": "custom_value"}

    def test_metadata_validation_requires_title(self):
        """Test that title is required."""
        with pytest.raises(ValidationError) as exc_info:
            ADRMetadata()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("title",) for error in errors)


class TestConsequencesStructured:
    """Test ConsequencesStructured model."""

    def test_create_consequences_with_defaults(self):
        """Test creating consequences with defaults."""
        consequences = ConsequencesStructured()

        assert consequences.positive == []
        assert consequences.negative == []

    def test_create_consequences_with_lists(self):
        """Test creating consequences with lists."""
        consequences = ConsequencesStructured(
            positive=["Better performance", "Easier maintenance"],
            negative=["Higher cost", "More complexity"],
        )

        assert len(consequences.positive) == 2
        assert len(consequences.negative) == 2
        assert "Better performance" in consequences.positive
        assert "Higher cost" in consequences.negative


class TestOptionDetails:
    """Test OptionDetails model."""

    def test_create_option_minimal(self):
        """Test creating option with minimal fields."""
        option = OptionDetails(name="PostgreSQL")

        assert option.name == "PostgreSQL"
        assert option.description is None
        assert option.pros == []
        assert option.cons == []

    def test_create_option_complete(self):
        """Test creating option with all fields."""
        option = OptionDetails(
            name="PostgreSQL",
            description="Open source relational database",
            pros=["ACID compliance", "Strong community"],
            cons=["Complex setup", "Resource intensive"],
        )

        assert option.name == "PostgreSQL"
        assert option.description == "Open source relational database"
        assert len(option.pros) == 2
        assert len(option.cons) == 2

    def test_option_requires_name(self):
        """Test that name is required."""
        with pytest.raises(ValidationError) as exc_info:
            OptionDetails()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)


class TestADRContent:
    """Test ADRContent model."""

    def test_create_content_minimal(self):
        """Test creating content with minimal required fields."""
        content = ADRContent(
            context_and_problem="We need a database",
            decision_outcome="Use PostgreSQL",
            consequences="Better reliability",
        )

        assert content.context_and_problem == "We need a database"
        assert content.decision_outcome == "Use PostgreSQL"
        assert content.consequences == "Better reliability"
        assert content.considered_options == []
        assert content.decision_drivers is None

    def test_create_content_complete(self):
        """Test creating content with all fields."""
        content = ADRContent(
            context_and_problem="We need a database",
            considered_options=["PostgreSQL", "MySQL", "MongoDB"],
            decision_outcome="Use PostgreSQL",
            consequences="Better reliability",
            decision_drivers=["Data consistency", "Query complexity"],
            confirmation="Use pg_dump for backups",
            options_details=[
                OptionDetails(
                    name="PostgreSQL",
                    pros=["ACID"],
                    cons=["Complex"],
                )
            ],
            consequences_structured=ConsequencesStructured(
                positive=["Better reliability"],
                negative=["Higher cost"],
            ),
            more_information="See wiki for details",
        )

        assert len(content.considered_options) == 3
        assert len(content.decision_drivers) == 2
        assert content.confirmation is not None
        assert len(content.options_details) == 1
        assert content.consequences_structured is not None
        assert content.more_information is not None

    def test_content_requires_key_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            ADRContent()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("context_and_problem",) for error in errors)
        assert any(error["loc"] == ("decision_outcome",) for error in errors)
        assert any(error["loc"] == ("consequences",) for error in errors)


class TestADR:
    """Test ADR model."""

    def test_create_adr_using_create_method(self):
        """Test creating ADR using the create class method."""
        adr = ADR.create(
            title="Use PostgreSQL",
            context_and_problem="We need a database",
            decision_outcome="Use PostgreSQL",
            consequences="Better reliability",
            author="Test Author",
        )

        assert adr.metadata.title == "Use PostgreSQL"
        assert adr.metadata.author == "Test Author"
        assert adr.metadata.status == ADRStatus.PROPOSED
        assert adr.content.context_and_problem == "We need a database"
        assert adr.content.decision_outcome == "Use PostgreSQL"

    def test_create_adr_with_all_fields(self):
        """Test creating ADR with all optional fields."""
        adr = ADR.create(
            title="Use PostgreSQL",
            context_and_problem="We need a database",
            decision_outcome="Use PostgreSQL",
            consequences="Better reliability",
            considered_options=["PostgreSQL", "MySQL"],
            author="Test Author",
            decision_drivers=["Consistency", "Performance"],
            confirmation="Use pg_dump",
            pros_and_cons={"PostgreSQL": ["Pro1"], "MySQL": ["Con1"]},
            more_information="See docs",
            tags=["database", "backend"],
        )

        assert len(adr.content.considered_options) == 2
        assert len(adr.content.decision_drivers) == 2
        assert len(adr.metadata.tags) == 2
        assert adr.content.confirmation is not None
        assert adr.content.more_information is not None

    def test_update_content(self):
        """Test updating ADR content."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Original",
            decision_outcome="Original",
            consequences="Original",
        )

        original_updated_at = adr.metadata.updated_at

        adr.update_content(
            context_and_problem="Updated context",
            decision_outcome="Updated decision",
        )

        assert adr.content.context_and_problem == "Updated context"
        assert adr.content.decision_outcome == "Updated decision"
        assert adr.content.consequences == "Original"  # Not updated
        assert adr.metadata.updated_at > original_updated_at

    def test_add_tag(self):
        """Test adding tags to ADR."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Test",
            decision_outcome="Test",
            consequences="Test",
        )

        adr.add_tag("database")
        adr.add_tag("architecture")
        adr.add_tag("database")  # Duplicate

        assert len(adr.metadata.tags) == 2
        assert "database" in adr.metadata.tags
        assert "architecture" in adr.metadata.tags

    def test_remove_tag(self):
        """Test removing tags from ADR."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Test",
            decision_outcome="Test",
            consequences="Test",
            tags=["database", "architecture"],
        )

        adr.remove_tag("database")

        assert len(adr.metadata.tags) == 1
        assert "architecture" in adr.metadata.tags
        assert "database" not in adr.metadata.tags

    def test_add_related_adr(self):
        """Test adding related ADRs."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Test",
            decision_outcome="Test",
            consequences="Test",
        )

        related_id1 = uuid4()
        related_id2 = uuid4()

        adr.add_related_adr(related_id1)
        adr.add_related_adr(related_id2)
        adr.add_related_adr(related_id1)  # Duplicate

        assert len(adr.metadata.related_adrs) == 2
        assert related_id1 in adr.metadata.related_adrs
        assert related_id2 in adr.metadata.related_adrs

    def test_to_markdown(self):
        """Test converting ADR to markdown."""
        adr = ADR.create(
            title="Use PostgreSQL",
            context_and_problem="We need a database",
            decision_outcome="Use PostgreSQL",
            consequences="Better reliability",
            author="Test Author",
            tags=["database"],
        )

        markdown = adr.to_markdown()

        assert "# Use PostgreSQL" in markdown
        assert "**Status:** proposed" in markdown
        assert "**Author:** Test Author" in markdown
        assert "**Tags:** database" in markdown
        assert "## Context and Problem Statement" in markdown
        assert "We need a database" in markdown
        assert "## Decision Outcome" in markdown
        assert "Use PostgreSQL" in markdown

    def test_adr_serialization(self):
        """Test ADR can be serialized to dict and JSON."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Test",
            decision_outcome="Test",
            consequences="Test",
        )

        # Test dict conversion
        adr_dict = adr.model_dump()
        assert isinstance(adr_dict, dict)
        assert adr_dict["metadata"]["title"] == "Test"

        # Test JSON conversion
        adr_json = adr.model_dump_json()
        assert isinstance(adr_json, str)
        assert "Test" in adr_json

    def test_adr_deserialization(self):
        """Test ADR can be deserialized from dict."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Test",
            decision_outcome="Test",
            consequences="Test",
        )

        # Serialize and deserialize
        adr_dict = adr.model_dump()
        restored_adr = ADR.model_validate(adr_dict)

        assert restored_adr.metadata.title == adr.metadata.title
        assert restored_adr.metadata.id == adr.metadata.id
        assert (
            restored_adr.content.context_and_problem == adr.content.context_and_problem
        )
