"""Import/export utilities for ADRs with versioned schema support."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import yaml
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.models import (
    ADR,
    ADRContent,
    ADRMetadata,
    ADRStatus,
    ConsequencesStructured,
    OptionDetails,
)

logger = get_logger(__name__)

# Schema version constants
CURRENT_SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS = ["1.0.0"]


class ExportSchemaMetadata(BaseModel):
    """Metadata for the export schema itself."""

    schema_version: str = Field(
        default=CURRENT_SCHEMA_VERSION, description="Version of the export schema"
    )
    exported_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Export timestamp",
    )
    exported_by: Optional[str] = Field(
        default=None, description="User or system that exported the data"
    )
    total_records: int = Field(
        default=1, description="Total number of ADRs in this export"
    )


class ADRExportV1(BaseModel):
    """Versioned export format for a single ADR (v1.0.0)."""

    # Metadata
    id: str = Field(..., description="ADR unique identifier (UUID)")
    title: str = Field(..., description="ADR title")
    status: str = Field(..., description="ADR status")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    author: Optional[str] = Field(default=None, description="Author name")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    related_adrs: List[str] = Field(
        default_factory=list, description="Related ADR IDs (UUIDs)"
    )
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata fields"
    )

    # Content
    context_and_problem: str = Field(..., description="Context and problem statement")
    decision_drivers: Optional[List[str]] = Field(
        default=None, description="Decision drivers"
    )
    considered_options: List[str] = Field(
        default_factory=list, description="Considered options (simple list)"
    )
    decision_outcome: str = Field(..., description="Decision outcome and justification")
    consequences: str = Field(..., description="Consequences (plain text)")
    confirmation: Optional[str] = Field(
        default=None, description="How compliance is confirmed"
    )
    pros_and_cons: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Pros and cons (deprecated)"
    )
    more_information: Optional[str] = Field(
        default=None, description="Additional information"
    )

    # Extended fields (newer features)
    options_details: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Detailed options with pros/cons"
    )
    consequences_structured: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Structured consequences"
    )
    referenced_adrs: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Referenced ADRs during generation"
    )
    persona_responses: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Individual persona responses"
    )


class SingleADRExport(BaseModel):
    """Container for a single ADR export with schema metadata."""

    schema: ExportSchemaMetadata
    adr: ADRExportV1


class BulkADRExport(BaseModel):
    """Container for bulk ADR export with schema metadata."""

    schema: ExportSchemaMetadata
    adrs: List[ADRExportV1]


class ADRImportExport:
    """Utilities for importing and exporting ADRs with versioned schema support."""

    # ==================== Versioned Export/Import (Primary Methods) ====================

    @staticmethod
    def export_single_versioned(
        adr: ADR, exported_by: Optional[str] = None
    ) -> SingleADRExport:
        """Export a single ADR to versioned schema format.

        Args:
            adr: The ADR to export
            exported_by: Optional identifier of who/what exported the data

        Returns:
            SingleADRExport object with schema metadata
        """
        schema = ExportSchemaMetadata(
            schema_version=CURRENT_SCHEMA_VERSION,
            exported_by=exported_by,
            total_records=1,
        )

        adr_export = ADRImportExport._adr_to_export_v1(adr)

        return SingleADRExport(schema=schema, adr=adr_export)

    @staticmethod
    def export_bulk_versioned(
        adrs: List[ADR], exported_by: Optional[str] = None
    ) -> BulkADRExport:
        """Export multiple ADRs to versioned schema format.

        Args:
            adrs: List of ADRs to export
            exported_by: Optional identifier of who/what exported the data

        Returns:
            BulkADRExport object with schema metadata
        """
        schema = ExportSchemaMetadata(
            schema_version=CURRENT_SCHEMA_VERSION,
            exported_by=exported_by,
            total_records=len(adrs),
        )

        adr_exports = [ADRImportExport._adr_to_export_v1(adr) for adr in adrs]

        return BulkADRExport(schema=schema, adrs=adr_exports)

    @staticmethod
    def import_single_versioned(data: Dict[str, Any]) -> ADR:
        """Import a single ADR from versioned schema format.

        Args:
            data: Dictionary containing schema and adr fields

        Returns:
            ADR object

        Raises:
            ValueError: If schema version is not supported
        """
        schema_version = data.get("schema", {}).get("schema_version", "1.0.0")

        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema version: {schema_version}. Supported versions: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        # Parse the export container
        export_container = SingleADRExport(**data)

        # Convert to ADR based on schema version
        if schema_version == "1.0.0":
            adr = ADRImportExport._export_v1_to_adr(export_container.adr)
        else:
            # Future versions will have migration logic here
            raise ValueError(f"Schema version {schema_version} not yet implemented")

        logger.info(
            f"Imported ADR from versioned schema v{schema_version}",
            adr_id=str(adr.metadata.id),
            title=adr.metadata.title,
        )
        return adr

    @staticmethod
    def import_bulk_versioned(data: Dict[str, Any]) -> List[ADR]:
        """Import multiple ADRs from versioned schema format.

        Args:
            data: Dictionary containing schema and adrs fields

        Returns:
            List of ADR objects

        Raises:
            ValueError: If schema version is not supported
        """
        schema_version = data.get("schema", {}).get("schema_version", "1.0.0")

        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema version: {schema_version}. Supported versions: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        # Parse the export container
        export_container = BulkADRExport(**data)

        # Convert to ADRs based on schema version
        adrs = []
        if schema_version == "1.0.0":
            for adr_export in export_container.adrs:
                adr = ADRImportExport._export_v1_to_adr(adr_export)
                adrs.append(adr)
        else:
            # Future versions will have migration logic here
            raise ValueError(f"Schema version {schema_version} not yet implemented")

        logger.info(
            f"Imported {len(adrs)} ADRs from versioned schema v{schema_version}"
        )
        return adrs

    @staticmethod
    def _adr_to_export_v1(adr: ADR) -> ADRExportV1:
        """Convert an ADR to v1.0.0 export format."""
        # Convert options_details to dict if present
        options_details_dict = None
        if adr.content.options_details:
            options_details_dict = [
                opt.model_dump() for opt in adr.content.options_details
            ]

        # Convert consequences_structured to dict if present
        consequences_structured_dict = None
        if adr.content.consequences_structured:
            consequences_structured_dict = (
                adr.content.consequences_structured.model_dump()
            )

        return ADRExportV1(
            id=str(adr.metadata.id),
            title=adr.metadata.title,
            status=adr.metadata.status.value,
            created_at=adr.metadata.created_at.isoformat(),
            updated_at=adr.metadata.updated_at.isoformat(),
            author=adr.metadata.author,
            tags=adr.metadata.tags,
            related_adrs=[str(adr_id) for adr_id in adr.metadata.related_adrs],
            custom_fields=adr.metadata.custom_fields,
            context_and_problem=adr.content.context_and_problem,
            decision_drivers=adr.content.decision_drivers,
            considered_options=adr.content.considered_options,
            decision_outcome=adr.content.decision_outcome,
            consequences=adr.content.consequences,
            confirmation=adr.content.confirmation,
            pros_and_cons=adr.content.pros_and_cons,
            more_information=adr.content.more_information,
            options_details=options_details_dict,
            consequences_structured=consequences_structured_dict,
            referenced_adrs=adr.content.referenced_adrs,
            persona_responses=adr.persona_responses,
        )

    @staticmethod
    def _export_v1_to_adr(export: ADRExportV1) -> ADR:
        """Convert v1.0.0 export format to an ADR."""
        # Parse metadata
        metadata = ADRMetadata(
            id=UUID(export.id),
            title=export.title,
            status=ADRStatus(export.status),
            created_at=datetime.fromisoformat(export.created_at),
            updated_at=datetime.fromisoformat(export.updated_at),
            author=export.author,
            tags=export.tags,
            related_adrs=[UUID(adr_id) for adr_id in export.related_adrs],
            custom_fields=export.custom_fields,
        )

        # Convert options_details from dict if present
        options_details = None
        if export.options_details:
            options_details = [OptionDetails(**opt) for opt in export.options_details]

        # Convert consequences_structured from dict if present
        consequences_structured = None
        if export.consequences_structured:
            consequences_structured = ConsequencesStructured(
                **export.consequences_structured
            )

        # Parse content
        content = ADRContent(
            context_and_problem=export.context_and_problem,
            decision_drivers=export.decision_drivers,
            considered_options=export.considered_options,
            decision_outcome=export.decision_outcome,
            consequences=export.consequences,
            confirmation=export.confirmation,
            pros_and_cons=export.pros_and_cons,
            more_information=export.more_information,
            options_details=options_details,
            consequences_structured=consequences_structured,
            referenced_adrs=export.referenced_adrs,
        )

        return ADR(
            metadata=metadata,
            content=content,
            persona_responses=export.persona_responses,
        )

    # ==================== Legacy Export Methods (Backwards Compatibility) ====================

    @staticmethod
    def export_to_markdown(adr: ADR, output_path: str) -> None:
        """Export ADR to Markdown file."""
        markdown_content = adr.to_markdown()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(
            "ADR exported to Markdown", path=output_path, title=adr.metadata.title
        )

    @staticmethod
    def export_to_json(adr: ADR, output_path: str) -> None:
        """Export ADR to JSON file."""
        data = {
            "metadata": {
                "id": str(adr.metadata.id),
                "title": adr.metadata.title,
                "status": adr.metadata.status.value,
                "created_at": adr.metadata.created_at.isoformat(),
                "updated_at": adr.metadata.updated_at.isoformat(),
                "author": adr.metadata.author,
                "tags": adr.metadata.tags,
                "related_adrs": [str(adr_id) for adr_id in adr.metadata.related_adrs],
            },
            "content": {
                "context_and_problem": adr.content.context_and_problem,
                "decision_drivers": adr.content.decision_drivers,
                "considered_options": adr.content.considered_options,
                "decision_outcome": adr.content.decision_outcome,
                "consequences": adr.content.consequences,
                "confirmation": adr.content.confirmation,
                "pros_and_cons": adr.content.pros_and_cons,
                "more_information": adr.content.more_information,
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("ADR exported to JSON", path=output_path, title=adr.metadata.title)

    @staticmethod
    def export_to_yaml(adr: ADR, output_path: str) -> None:
        """Export ADR to YAML file."""
        data = {
            "metadata": {
                "id": str(adr.metadata.id),
                "title": adr.metadata.title,
                "status": adr.metadata.status.value,
                "created_at": adr.metadata.created_at.isoformat(),
                "updated_at": adr.metadata.updated_at.isoformat(),
                "author": adr.metadata.author,
                "tags": adr.metadata.tags,
                "related_adrs": [str(adr_id) for adr_id in adr.metadata.related_adrs],
            },
            "content": {
                "context_and_problem": adr.content.context_and_problem,
                "decision_drivers": adr.content.decision_drivers,
                "considered_options": adr.content.considered_options,
                "decision_outcome": adr.content.decision_outcome,
                "consequences": adr.content.consequences,
                "confirmation": adr.content.confirmation,
                "pros_and_cons": adr.content.pros_and_cons,
                "more_information": adr.content.more_information,
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        logger.info("ADR exported to YAML", path=output_path, title=adr.metadata.title)

    @staticmethod
    def import_from_markdown(file_path: str) -> ADR:
        """Import ADR from Markdown file with YAML frontmatter or inline metadata."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try YAML frontmatter first
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    markdown_content = parts[2].strip()
                except yaml.YAMLError:
                    # Fall back to inline parsing
                    return ADRImportExport._parse_inline_markdown(content)
            else:
                return ADRImportExport._parse_inline_markdown(content)
        else:
            # No frontmatter, parse inline
            return ADRImportExport._parse_inline_markdown(content)

        # Parse metadata from frontmatter
        metadata = ADRMetadata(
            id=UUID(frontmatter.get("id", str(UUID()))),
            title=frontmatter.get("title", "Untitled ADR"),
            status=ADRStatus(frontmatter.get("status", "proposed")),
            created_at=frontmatter.get("created_at"),
            updated_at=frontmatter.get("updated_at"),
            author=frontmatter.get("author"),
            tags=frontmatter.get("tags", []),
            related_adrs=[
                UUID(adr_id) for adr_id in frontmatter.get("related_adrs", [])
            ],
        )

        # Parse content
        content_obj = ADRImportExport._parse_markdown_content(markdown_content)

        adr = ADR(metadata=metadata, content=content_obj)
        logger.info(
            "ADR imported from Markdown", path=file_path, title=adr.metadata.title
        )
        return adr

    @staticmethod
    def import_from_json(file_path: str) -> ADR:
        """Import ADR from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata_dict = data["metadata"]
        content_dict = data["content"]

        metadata = ADRMetadata(
            id=UUID(metadata_dict["id"]),
            title=metadata_dict["title"],
            status=ADRStatus(metadata_dict["status"]),
            created_at=metadata_dict["created_at"],
            updated_at=metadata_dict["updated_at"],
            author=metadata_dict.get("author"),
            tags=metadata_dict.get("tags", []),
            related_adrs=[
                UUID(adr_id) for adr_id in metadata_dict.get("related_adrs", [])
            ],
        )

        content = ADRContent(
            context_and_problem=content_dict["context_and_problem"],
            decision_drivers=content_dict.get("decision_drivers"),
            considered_options=content_dict.get("considered_options", []),
            decision_outcome=content_dict["decision_outcome"],
            consequences=content_dict["consequences"],
            confirmation=content_dict.get("confirmation"),
            pros_and_cons=content_dict.get("pros_and_cons"),
            more_information=content_dict.get("more_information"),
        )

        adr = ADR(metadata=metadata, content=content)
        logger.info("ADR imported from JSON", path=file_path, title=adr.metadata.title)
        return adr

    @staticmethod
    def import_from_yaml(file_path: str) -> ADR:
        """Import ADR from YAML file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        metadata_dict = data["metadata"]
        content_dict = data["content"]

        metadata = ADRMetadata(
            id=UUID(metadata_dict["id"]),
            title=metadata_dict["title"],
            status=ADRStatus(metadata_dict["status"]),
            created_at=metadata_dict["created_at"],
            updated_at=metadata_dict["updated_at"],
            author=metadata_dict.get("author"),
            tags=metadata_dict.get("tags", []),
            related_adrs=[
                UUID(adr_id) for adr_id in metadata_dict.get("related_adrs", [])
            ],
        )

        content = ADRContent(
            context_and_problem=content_dict["context_and_problem"],
            decision_drivers=content_dict.get("decision_drivers"),
            considered_options=content_dict.get("considered_options", []),
            decision_outcome=content_dict["decision_outcome"],
            consequences=content_dict["consequences"],
            confirmation=content_dict.get("confirmation"),
            pros_and_cons=content_dict.get("pros_and_cons"),
            more_information=content_dict.get("more_information"),
        )

        adr = ADR(metadata=metadata, content=content)
        logger.info("ADR imported from YAML", path=file_path, title=adr.metadata.title)
        return adr

    @staticmethod
    def _parse_markdown_content(markdown_content: str) -> ADRContent:
        """Parse markdown content into ADRContent object."""
        lines = markdown_content.split("\n")
        context_and_problem = ""
        decision_drivers = None
        considered_options = []
        decision_outcome = ""
        consequences = ""
        confirmation = None
        pros_and_cons = None
        more_information = None

        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("## Context and Problem"):
                current_section = "context_and_problem"
            elif line.startswith("## Decision Drivers"):
                current_section = "decision_drivers"
                decision_drivers = []
            elif line.startswith("## Considered Options"):
                current_section = "considered_options"
                considered_options = []
            elif line.startswith("## Decision Outcome"):
                current_section = "decision_outcome"
            elif line.startswith("## Consequences"):
                current_section = "consequences"
            elif line.startswith("## Confirmation"):
                current_section = "confirmation"
            elif line.startswith("## Pros and Cons"):
                current_section = "pros_and_cons"
            elif line.startswith("## More Information"):
                current_section = "more_information"
            elif line.startswith("- ") and current_section in [
                "decision_drivers",
                "considered_options",
            ]:
                if (
                    current_section == "decision_drivers"
                    and decision_drivers is not None
                ):
                    decision_drivers.append(line[2:])
                elif current_section == "considered_options":
                    considered_options.append(line[2:])
            elif line and not line.startswith("#") and current_section:
                if current_section == "context_and_problem":
                    context_and_problem += line + " "
                elif current_section == "decision_outcome":
                    decision_outcome += line + " "
                elif current_section == "consequences":
                    consequences += line + " "
                elif current_section == "confirmation":
                    confirmation = (confirmation or "") + line + " "
                elif current_section == "pros_and_cons":
                    pros_and_cons = (pros_and_cons or "") + line + " "
                elif current_section == "more_information":
                    more_information = (more_information or "") + line + " "

        return ADRContent(
            context_and_problem=context_and_problem.strip(),
            decision_drivers=decision_drivers,
            considered_options=considered_options,
            decision_outcome=decision_outcome.strip(),
            consequences=consequences.strip(),
            confirmation=confirmation.strip() if confirmation else None,
            pros_and_cons=pros_and_cons.strip() if pros_and_cons else None,
            more_information=more_information.strip() if more_information else None,
        )

    @staticmethod
    def _parse_inline_markdown(content: str) -> ADR:
        """Parse ADR from markdown with inline metadata (no frontmatter)."""
        lines = content.split("\n")
        metadata = {}
        content_lines = []
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                metadata["title"] = line[2:]
            elif line.startswith("**Status:**"):
                status_str = line[11:].strip()
                metadata["status"] = status_str
            elif line.startswith("**Created:**"):
                metadata["created_at"] = line[12:].strip()
            elif line.startswith("**Updated:**"):
                metadata["updated_at"] = line[12:].strip()
            elif line.startswith("**Author:**"):
                metadata["author"] = line[11:].strip()
            elif line.startswith("**Tags:**"):
                tags_str = line[9:].strip()
                metadata["tags"] = (
                    [tag.strip() for tag in tags_str.split(",")] if tags_str else []
                )
            elif line.startswith("**Related ADRs:**"):
                related_str = line[16:].strip()
                if related_str:
                    try:
                        metadata["related_adrs"] = [
                            UUID(adr_id.strip()) for adr_id in related_str.split(",")
                        ]
                    except ValueError:
                        # If UUID parsing fails, skip related ADRs
                        metadata["related_adrs"] = []
                else:
                    metadata["related_adrs"] = []
            elif line.startswith("## "):
                current_section = line[3:].lower()
                content_lines.append(current_section)
            else:
                content_lines.append(line)

        # Create metadata object
        metadata_obj = ADRMetadata(
            id=UUID(metadata.get("id", str(UUID()))),
            title=metadata.get("title", "Untitled ADR"),
            status=ADRStatus(metadata.get("status", "proposed")),
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at"),
            author=metadata.get("author"),
            tags=metadata.get("tags", []),
            related_adrs=metadata.get("related_adrs", []),
        )

        # Parse content from the remaining lines
        content_str = "\n".join(content_lines)
        content_obj = ADRImportExport._parse_markdown_content(content_str)

        return ADR(metadata=metadata_obj, content=content_obj)

    @staticmethod
    def batch_export(
        adrs: List[ADR], output_dir: str, format: str = "markdown"
    ) -> None:
        """Export multiple ADRs to a directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for adr in adrs:
            filename = f"{adr.metadata.id}.{format}"
            filepath = output_path / filename

            if format == "markdown":
                ADRImportExport.export_to_markdown(adr, str(filepath))
            elif format == "json":
                ADRImportExport.export_to_json(adr, str(filepath))
            elif format == "yaml":
                ADRImportExport.export_to_yaml(adr, str(filepath))
            else:
                raise ValueError(f"Unsupported format: {format}")

        logger.info(
            "Batch export completed",
            count=len(adrs),
            format=format,
            directory=output_dir,
        )

    @staticmethod
    def batch_import(input_dir: str, format: str = "auto") -> List[ADR]:
        """Import multiple ADRs from a directory."""
        input_path = Path(input_dir)
        adrs = []

        for file_path in input_path.glob("*"):
            if file_path.is_file():
                try:
                    if format == "auto":
                        if file_path.suffix == ".md":
                            adr = ADRImportExport.import_from_markdown(str(file_path))
                        elif file_path.suffix == ".json":
                            adr = ADRImportExport.import_from_json(str(file_path))
                        elif file_path.suffix in [".yaml", ".yml"]:
                            adr = ADRImportExport.import_from_yaml(str(file_path))
                        else:
                            continue
                    elif format == "markdown":
                        adr = ADRImportExport.import_from_markdown(str(file_path))
                    elif format == "json":
                        adr = ADRImportExport.import_from_json(str(file_path))
                    elif format == "yaml":
                        adr = ADRImportExport.import_from_yaml(str(file_path))
                    else:
                        raise ValueError(f"Unsupported format: {format}")

                    adrs.append(adr)
                except Exception as e:
                    logger.warning(
                        "Failed to import ADR", path=str(file_path), error=str(e)
                    )
                    continue

        logger.info("Batch import completed", count=len(adrs), directory=input_dir)
        return adrs

    # ==================== File-based Versioned Export/Import ====================

    @staticmethod
    def export_single_versioned_to_file(
        adr: ADR, output_path: str, exported_by: Optional[str] = None
    ) -> None:
        """Export a single ADR to a versioned JSON file.

        Args:
            adr: The ADR to export
            output_path: Path to the output file
            exported_by: Optional identifier of who/what exported the data
        """
        export_data = ADRImportExport.export_single_versioned(adr, exported_by)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                export_data.model_dump(mode="json"), f, indent=2, ensure_ascii=False
            )

        logger.info(
            "Exported ADR to versioned file",
            path=output_path,
            adr_id=str(adr.metadata.id),
        )

    @staticmethod
    def export_bulk_versioned_to_file(
        adrs: List[ADR], output_path: str, exported_by: Optional[str] = None
    ) -> None:
        """Export multiple ADRs to a versioned JSON file.

        Args:
            adrs: List of ADRs to export
            output_path: Path to the output file
            exported_by: Optional identifier of who/what exported the data
        """
        export_data = ADRImportExport.export_bulk_versioned(adrs, exported_by)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                export_data.model_dump(mode="json"), f, indent=2, ensure_ascii=False
            )

        logger.info(f"Exported {len(adrs)} ADRs to versioned file", path=output_path)

    @staticmethod
    def import_single_versioned_from_file(file_path: str) -> ADR:
        """Import a single ADR from a versioned JSON file.

        Args:
            file_path: Path to the file to import

        Returns:
            ADR object
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ADRImportExport.import_single_versioned(data)

    @staticmethod
    def import_bulk_versioned_from_file(file_path: str) -> List[ADR]:
        """Import multiple ADRs from a versioned JSON file.

        Args:
            file_path: Path to the file to import

        Returns:
            List of ADR objects
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ADRImportExport.import_bulk_versioned(data)
