"""Import/export utilities for ADRs."""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from uuid import UUID

import yaml

from models import ADR, ADRMetadata, ADRContent, ADRStatus
from logger import get_logger

logger = get_logger(__name__)


class ADRImportExport:
    """Utilities for importing and exporting ADRs."""

    @staticmethod
    def export_to_markdown(adr: ADR, output_path: str) -> None:
        """Export ADR to Markdown file."""
        markdown_content = adr.to_markdown()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info("ADR exported to Markdown", path=output_path, title=adr.metadata.title)

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
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
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
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        logger.info("ADR exported to YAML", path=output_path, title=adr.metadata.title)

    @staticmethod
    def import_from_markdown(file_path: str) -> ADR:
        """Import ADR from Markdown file with YAML frontmatter or inline metadata."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Try YAML frontmatter first
        if content.startswith('---'):
            parts = content.split('---', 2)
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
            id=UUID(frontmatter.get('id', str(UUID()))),
            title=frontmatter.get('title', 'Untitled ADR'),
            status=ADRStatus(frontmatter.get('status', 'proposed')),
            created_at=frontmatter.get('created_at'),
            updated_at=frontmatter.get('updated_at'),
            author=frontmatter.get('author'),
            tags=frontmatter.get('tags', []),
            related_adrs=[UUID(adr_id) for adr_id in frontmatter.get('related_adrs', [])],
        )

        # Parse content
        content_obj = ADRImportExport._parse_markdown_content(markdown_content)

        adr = ADR(metadata=metadata, content=content_obj)
        logger.info("ADR imported from Markdown", path=file_path, title=adr.metadata.title)
        return adr

    @staticmethod
    def import_from_json(file_path: str) -> ADR:
        """Import ADR from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata_dict = data['metadata']
        content_dict = data['content']

        metadata = ADRMetadata(
            id=UUID(metadata_dict['id']),
            title=metadata_dict['title'],
            status=ADRStatus(metadata_dict['status']),
            created_at=metadata_dict['created_at'],
            updated_at=metadata_dict['updated_at'],
            author=metadata_dict.get('author'),
            tags=metadata_dict.get('tags', []),
            related_adrs=[UUID(adr_id) for adr_id in metadata_dict.get('related_adrs', [])],
        )

        content = ADRContent(
            context_and_problem=content_dict['context_and_problem'],
            decision_drivers=content_dict.get('decision_drivers'),
            considered_options=content_dict.get('considered_options', []),
            decision_outcome=content_dict['decision_outcome'],
            consequences=content_dict['consequences'],
            confirmation=content_dict.get('confirmation'),
            pros_and_cons=content_dict.get('pros_and_cons'),
            more_information=content_dict.get('more_information'),
        )

        adr = ADR(metadata=metadata, content=content)
        logger.info("ADR imported from JSON", path=file_path, title=adr.metadata.title)
        return adr

    @staticmethod
    def import_from_yaml(file_path: str) -> ADR:
        """Import ADR from YAML file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        metadata_dict = data['metadata']
        content_dict = data['content']

        metadata = ADRMetadata(
            id=UUID(metadata_dict['id']),
            title=metadata_dict['title'],
            status=ADRStatus(metadata_dict['status']),
            created_at=metadata_dict['created_at'],
            updated_at=metadata_dict['updated_at'],
            author=metadata_dict.get('author'),
            tags=metadata_dict.get('tags', []),
            related_adrs=[UUID(adr_id) for adr_id in metadata_dict.get('related_adrs', [])],
        )

        content = ADRContent(
            context_and_problem=content_dict['context_and_problem'],
            decision_drivers=content_dict.get('decision_drivers'),
            considered_options=content_dict.get('considered_options', []),
            decision_outcome=content_dict['decision_outcome'],
            consequences=content_dict['consequences'],
            confirmation=content_dict.get('confirmation'),
            pros_and_cons=content_dict.get('pros_and_cons'),
            more_information=content_dict.get('more_information'),
        )

        adr = ADR(metadata=metadata, content=content)
        logger.info("ADR imported from YAML", path=file_path, title=adr.metadata.title)
        return adr

    @staticmethod
    def _parse_markdown_content(markdown_content: str) -> ADRContent:
        """Parse markdown content into ADRContent object."""
        lines = markdown_content.split('\n')
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
            if line.startswith('## Context and Problem'):
                current_section = 'context_and_problem'
            elif line.startswith('## Decision Drivers'):
                current_section = 'decision_drivers'
                decision_drivers = []
            elif line.startswith('## Considered Options'):
                current_section = 'considered_options'
                considered_options = []
            elif line.startswith('## Decision Outcome'):
                current_section = 'decision_outcome'
            elif line.startswith('## Consequences'):
                current_section = 'consequences'
            elif line.startswith('## Confirmation'):
                current_section = 'confirmation'
            elif line.startswith('## Pros and Cons'):
                current_section = 'pros_and_cons'
            elif line.startswith('## More Information'):
                current_section = 'more_information'
            elif line.startswith('- ') and current_section in ['decision_drivers', 'considered_options']:
                if current_section == 'decision_drivers' and decision_drivers is not None:
                    decision_drivers.append(line[2:])
                elif current_section == 'considered_options':
                    considered_options.append(line[2:])
            elif line and not line.startswith('#') and current_section:
                if current_section == 'context_and_problem':
                    context_and_problem += line + ' '
                elif current_section == 'decision_outcome':
                    decision_outcome += line + ' '
                elif current_section == 'consequences':
                    consequences += line + ' '
                elif current_section == 'confirmation':
                    confirmation = (confirmation or '') + line + ' '
                elif current_section == 'pros_and_cons':
                    pros_and_cons = (pros_and_cons or '') + line + ' '
                elif current_section == 'more_information':
                    more_information = (more_information or '') + line + ' '

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
        lines = content.split('\n')
        metadata = {}
        content_lines = []
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                metadata['title'] = line[2:]
            elif line.startswith('**Status:**'):
                status_str = line[11:].strip()
                metadata['status'] = status_str
            elif line.startswith('**Created:**'):
                metadata['created_at'] = line[12:].strip()
            elif line.startswith('**Updated:**'):
                metadata['updated_at'] = line[12:].strip()
            elif line.startswith('**Author:**'):
                metadata['author'] = line[11:].strip()
            elif line.startswith('**Tags:**'):
                tags_str = line[9:].strip()
                metadata['tags'] = [tag.strip() for tag in tags_str.split(',')] if tags_str else []
            elif line.startswith('**Related ADRs:**'):
                related_str = line[16:].strip()
                if related_str:
                    try:
                        metadata['related_adrs'] = [UUID(adr_id.strip()) for adr_id in related_str.split(',')]
                    except ValueError:
                        # If UUID parsing fails, skip related ADRs
                        metadata['related_adrs'] = []
                else:
                    metadata['related_adrs'] = []
            elif line.startswith('## '):
                current_section = line[3:].lower()
                content_lines.append(line)
            else:
                content_lines.append(line)

        # Create metadata object
        metadata_obj = ADRMetadata(
            id=UUID(metadata.get('id', str(UUID()))),
            title=metadata.get('title', 'Untitled ADR'),
            status=ADRStatus(metadata.get('status', 'proposed')),
            created_at=metadata.get('created_at'),
            updated_at=metadata.get('updated_at'),
            author=metadata.get('author'),
            tags=metadata.get('tags', []),
            related_adrs=metadata.get('related_adrs', []),
        )

        # Parse content from the remaining lines
        content_str = '\n'.join(content_lines)
        content_obj = ADRImportExport._parse_markdown_content(content_str)

        return ADR(metadata=metadata_obj, content=content_obj)

    @staticmethod
    def batch_export(adrs: List[ADR], output_dir: str, format: str = 'markdown') -> None:
        """Export multiple ADRs to a directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for adr in adrs:
            filename = f"{adr.metadata.id}.{format}"
            filepath = output_path / filename

            if format == 'markdown':
                ADRImportExport.export_to_markdown(adr, str(filepath))
            elif format == 'json':
                ADRImportExport.export_to_json(adr, str(filepath))
            elif format == 'yaml':
                ADRImportExport.export_to_yaml(adr, str(filepath))
            else:
                raise ValueError(f"Unsupported format: {format}")

        logger.info("Batch export completed", count=len(adrs), format=format, directory=output_dir)

    @staticmethod
    def batch_import(input_dir: str, format: str = 'auto') -> List[ADR]:
        """Import multiple ADRs from a directory."""
        input_path = Path(input_dir)
        adrs = []

        for file_path in input_path.glob('*'):
            if file_path.is_file():
                try:
                    if format == 'auto':
                        if file_path.suffix == '.md':
                            adr = ADRImportExport.import_from_markdown(str(file_path))
                        elif file_path.suffix == '.json':
                            adr = ADRImportExport.import_from_json(str(file_path))
                        elif file_path.suffix in ['.yaml', '.yml']:
                            adr = ADRImportExport.import_from_yaml(str(file_path))
                        else:
                            continue
                    elif format == 'markdown':
                        adr = ADRImportExport.import_from_markdown(str(file_path))
                    elif format == 'json':
                        adr = ADRImportExport.import_from_json(str(file_path))
                    elif format == 'yaml':
                        adr = ADRImportExport.import_from_yaml(str(file_path))
                    else:
                        raise ValueError(f"Unsupported format: {format}")

                    adrs.append(adr)
                except Exception as e:
                    logger.warning("Failed to import ADR", path=str(file_path), error=str(e))
                    continue

        logger.info("Batch import completed", count=len(adrs), directory=input_dir)
        return adrs
