"""AI-powered ADR analysis and evaluation utilities."""

from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import asyncio

from src.models import (
    ADR,
    ADRStatus,
    ADRAnalysisResult,
    ADRWithAnalysis,
    AnalysisSections,
)
from logger import get_logger
from llama_client import LlamaCppClient
from lightrag_client import LightRAGClient
from persona_manager import get_persona_manager

logger = get_logger(__name__)


class ADRAnalysisService:
    """AI-powered ADR analysis service."""

    def __init__(
        self,
        llama_client: LlamaCppClient,
        lightrag_client: LightRAGClient,
        analysis_timeout: int = 120,
        max_retries: int = 2
    ):
        self.llama_client = llama_client
        self.lightrag_client = lightrag_client
        self.analysis_timeout = analysis_timeout
        self.max_retries = max_retries

    async def analyze_adr(
        self, adr: ADR, persona: str, include_context: bool = True
    ) -> ADRAnalysisResult:
        """Analyze an ADR using AI with a specific persona."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                # Retrieve contextual information
                context = ""
                if include_context:
                    context = await self._get_contextual_information(adr)

                # Build analysis prompt
                prompt = self._build_analysis_prompt(adr, persona, context)

                # Get AI analysis with timeout
                async with asyncio.timeout(self.analysis_timeout):
                    async with self.llama_client:
                        analysis_result = await self.llama_client.generate(prompt, format=None)

                # Debug: Log the raw response
                logger.info("Raw LLM response received", response_length=len(analysis_result), response_preview=analysis_result[:500] if analysis_result else "Empty response")

                # Parse the JSON response
                try:
                    import json
                    parsed_response = json.loads(analysis_result)
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse JSON response", error=str(e), response=analysis_result)
                    # Fallback to old parsing if JSON fails
                    parsed_response = self._parse_text_response(analysis_result, persona)

                # Structure the analysis result
                structured_analysis = ADRAnalysisResult(
                    persona=persona,
                    timestamp=datetime.now(UTC).isoformat(),
                    sections=AnalysisSections(
                        strengths=parsed_response.get("strengths", ""),
                        weaknesses=parsed_response.get("weaknesses", ""),
                        risks=parsed_response.get("risks", ""),
                        recommendations=parsed_response.get("recommendations", ""),
                        overall_assessment=parsed_response.get(
                            "overall_assessment", ""
                        ),
                    ),
                    score=parsed_response.get("score"),
                    raw_response=analysis_result,
                )

                logger.info(
                    "ADR analysis completed",
                    adr_id=str(adr.metadata.id),
                    persona=persona,
                    title=adr.metadata.title,
                    attempt=attempt + 1,
                )

                return structured_analysis

            except asyncio.TimeoutError:
                last_exception = RuntimeError(f"Analysis timed out after {self.analysis_timeout} seconds")
                logger.warning(
                    "Analysis timeout on attempt",
                    attempt=attempt + 1,
                    persona=persona,
                    adr_id=str(adr.metadata.id),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except Exception as e:
                last_exception = e
                logger.warning(
                    "Analysis failed on attempt",
                    attempt=attempt + 1,
                    persona=persona,
                    adr_id=str(adr.metadata.id),
                    error=str(e),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All attempts failed
        logger.error(
            "ADR analysis failed after all attempts",
            adr_id=str(adr.metadata.id),
            persona=persona,
            total_attempts=self.max_retries + 1,
            final_error=str(last_exception),
        )
        raise last_exception or RuntimeError("Analysis failed after all retries")

    async def analyze_adr_with_multiple_personas(
        self, adr: ADR, personas: List[str] = None, include_context: bool = True
    ) -> ADRWithAnalysis:
        """Analyze ADR with multiple personas for comprehensive evaluation."""
        if personas is None:
            # Get default personas from persona manager
            from src.persona_manager import PersonaManager

            persona_manager = PersonaManager()
            personas = persona_manager.list_persona_values()

        results = {}
        for persona in personas:
            analysis = await self.analyze_adr(adr, persona, include_context)
            results[persona] = analysis

        adr_with_analysis = ADRWithAnalysis(
            adr=adr,
            analysis_results=results
        )

        logger.info(
            "Multi-persona analysis completed",
            adr_id=str(adr.metadata.id),
            personas=personas,
            title=adr.metadata.title,
            average_score=adr_with_analysis.average_score,
            consensus_recommendation=adr_with_analysis.consensus_recommendation,
        )

        return adr_with_analysis

    async def _get_contextual_information(self, adr: ADR) -> str:
        """Retrieve contextual information from LightRAG with enhanced relevance scoring."""
        try:
            # Generate comprehensive search terms
            search_terms = self._generate_search_terms(adr)

            # Collect and score relevant documents
            context_candidates = []
            seen_content = set()  # Avoid duplicates

            for term in search_terms[:5]:  # Increased limit for better coverage
                try:
                    results = await self.lightrag_client.retrieve_documents(term, limit=5)
                    for result in results:
                        if result.get('content') and result['content'] not in seen_content:
                            relevance_score = self._calculate_relevance_score(result['content'], adr)
                            if relevance_score > 0.3:  # Only include relevant content
                                context_candidates.append({
                                    'content': result['content'],
                                    'score': relevance_score,
                                    'source': term
                                })
                                seen_content.add(result['content'])
                except Exception as e:
                    logger.warning("Failed to retrieve context for term", term=term, error=str(e))

            # Sort by relevance and format top results
            context_candidates.sort(key=lambda x: x['score'], reverse=True)
            top_contexts = context_candidates[:3]  # Limit to most relevant

            if not top_contexts:
                return "No additional context available."

            # Format context with relevance indicators
            context_parts = []
            for i, candidate in enumerate(top_contexts, 1):
                relevance_indicator = "highly relevant" if candidate['score'] > 0.7 else "somewhat relevant"
                content_preview = candidate['content'][:400] + "..." if len(candidate['content']) > 400 else candidate['content']
                context_parts.append(f"Context {i} ({relevance_indicator}, from: {candidate['source']}):\n{content_preview}")

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.error("Failed to retrieve contextual information", error=str(e))
            return "Context retrieval failed."

    def _generate_search_terms(self, adr: ADR) -> List[str]:
        """Generate comprehensive search terms from ADR content."""
        terms = []

        # Core terms
        terms.append(adr.metadata.title)

        # Content-based terms
        if adr.content.context_and_problem:
            # Extract key phrases from context
            context_words = adr.content.context_and_problem.lower().split()
            # Look for noun phrases and important terms
            for i in range(len(context_words) - 1):
                if len(context_words[i]) > 3 and len(context_words[i + 1]) > 3:
                    terms.append(f"{context_words[i]} {context_words[i + 1]}")

        # Decision drivers
        if adr.content.decision_drivers:
            terms.extend([driver.lower() for driver in adr.content.decision_drivers if len(driver) > 3])

        # Considered options
        if adr.content.considered_options:
            for option in adr.content.considered_options:
                if len(option) > 3:
                    terms.append(option.lower())

        # Tags
        if adr.metadata.tags:
            terms.extend([tag.lower() for tag in adr.metadata.tags])

        # Decision outcome keywords
        if adr.content.decision_outcome:
            outcome_words = adr.content.decision_outcome.lower().split()
            terms.extend([word for word in outcome_words if len(word) > 4])  # Longer words are more specific

        # Remove duplicates and filter
        unique_terms = list(set(terms))
        # Filter out very common words and keep meaningful terms
        filtered_terms = [term for term in unique_terms if len(term) > 3 and not term in ['that', 'with', 'this', 'from', 'they', 'have', 'will']]

        return filtered_terms[:10]  # Limit to most relevant terms

    def _calculate_relevance_score(self, content: str, adr: ADR) -> float:
        """Calculate relevance score between content and ADR."""
        content_lower = content.lower()
        score = 0.0

        # Title match (high weight)
        if adr.metadata.title.lower() in content_lower:
            score += 0.4

        # Tag matches
        if adr.metadata.tags:
            tag_matches = sum(1 for tag in adr.metadata.tags if tag.lower() in content_lower)
            score += tag_matches * 0.1

        # Decision driver matches
        if adr.content.decision_drivers:
            driver_matches = sum(1 for driver in adr.content.decision_drivers
                               if driver.lower() in content_lower)
            score += driver_matches * 0.15

        # Considered options matches
        if adr.content.considered_options:
            option_matches = sum(1 for option in adr.content.considered_options
                               if option.lower() in content_lower)
            score += option_matches * 0.1

        # Context/problem similarity (word overlap)
        if adr.content.context_and_problem:
            context_words = set(adr.content.context_and_problem.lower().split())
            content_words = set(content_lower.split())
            overlap = len(context_words.intersection(content_words))
            total_words = len(context_words.union(content_words))
            if total_words > 0:
                similarity = overlap / total_words
                score += similarity * 0.25

        return min(score, 1.0)  # Cap at 1.0

    async def _get_contextual_information(self, adr: ADR) -> str:
        """Retrieve contextual information from LightRAG."""
        try:
            # Search for related ADRs and content
            search_terms = [
                adr.metadata.title,
                adr.content.context_and_problem[:100],  # First 100 chars of context
            ]

            if adr.metadata.tags:
                search_terms.extend(adr.metadata.tags)

            context_parts = []
            for term in search_terms[:3]:  # Limit to avoid too many searches
                try:
                    results = await self.lightrag_client.retrieve_documents(term, limit=3)
                    for result in results:
                        if result.get('content'):
                            context_parts.append(f"Related content: {result['content'][:500]}...")
                except Exception as e:
                    logger.warning("Failed to retrieve context for term", term=term, error=str(e))

            return "\n\n".join(context_parts) if context_parts else "No additional context available."

        except Exception as e:
            logger.error("Failed to retrieve contextual information", error=str(e))
            return "Context retrieval failed."

    def _build_analysis_prompt(self, adr: ADR, persona: str, context: str) -> str:
        """Build analysis prompt for the specified persona."""
        persona_instructions = self._get_persona_instructions(persona)

        prompt = f"""You are an expert {persona_instructions['role']} analyzing an Architecture Decision Record (ADR).

{persona_instructions['instructions']}

ADR TO ANALYZE:
Title: {adr.metadata.title}
Status: {adr.metadata.status.value}
Author: {adr.metadata.author or 'Not specified'}
Tags: {', '.join(adr.metadata.tags) if adr.metadata.tags else 'None'}

CONTENT:
Context and Problem: {adr.content.context_and_problem}

Decision Drivers: {', '.join(adr.content.decision_drivers) if adr.content.decision_drivers else 'Not specified'}

Considered Options: {', '.join(adr.content.considered_options) if adr.content.considered_options else 'Not specified'}

Decision Outcome: {adr.content.decision_outcome}

Consequences: {adr.content.consequences}

{f'Confirmation: {adr.content.confirmation}' if adr.content.confirmation else ''}

{f'Pros and Cons: {adr.content.pros_and_cons}' if adr.content.pros_and_cons else ''}

{f'More Information: {adr.content.more_information}' if adr.content.more_information else ''}

ADDITIONAL CONTEXT:
{context}

Please analyze this ADR and respond with a JSON object in the following format:
{{
  "strengths": "Key strengths of this ADR",
  "weaknesses": "Key weaknesses or concerns", 
  "risks": "Potential risks or issues",
  "recommendations": "Suggestions for improvements or changes",
  "overall_assessment": "ACCEPT/REJECT/MODIFY with justification",
  "score": 8
}}

IMPORTANT: Your response must be valid JSON only. Do not include any text before or after the JSON object. The score must be a number from 1-10."""

        return prompt

    def _get_persona_instructions(self, persona: str) -> Dict[str, str]:
        """Get instructions for a specific analysis persona."""
        persona_manager = get_persona_manager()
        return persona_manager.get_persona_instructions(persona)

    def _parse_text_response(self, response: str, persona: str) -> Dict[str, Any]:
        """Parse the AI analysis response into structured data."""
        # Handle markdown-formatted sections like **STRENGTHS**
        sections = {}
        current_section = None
        current_content = []

        lines = response.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check for markdown section headers like **STRENGTHS**
            if line.startswith('**') and line.endswith('**'):
                section_name = line[2:-2].upper()
                # Map common section names
                if section_name in ['STRENGTHS', 'WEAKNESSES', 'RISKS', 'RECOMMENDATIONS', 'OVERALL ASSESSMENT']:
                    # Save previous section
                    if current_section:
                        sections[current_section.lower().replace(' ', '_')] = '\n'.join(current_content).strip()
                    current_section = section_name
                    current_content = []
                    i += 1
                    # Skip any empty lines after header
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    continue

            # Check for SCORE line (handle various formats)
            elif '**SCORE**:' in line.upper() or 'SCORE:' in line.upper() or line.upper().startswith('SCORE'):
                if current_section:
                    sections[current_section.lower().replace(' ', '_')] = '\n'.join(current_content).strip()
                # Extract score - handle markdown bold and various formats
                score_text = line.replace('**SCORE**:', '').replace('**SCORE**', '').replace('SCORE:', '').replace('SCORE', '').strip()
                # Remove markdown bold from the score value
                score_text = score_text.replace('**', '').strip()
                sections['score'] = score_text
                current_section = None
                current_content = []
                i += 1
                continue

            # Add content to current section
            elif current_section:
                current_content.append(line)

            i += 1

        # Add the last section
        if current_section:
            sections[current_section.lower().replace(' ', '_')] = '\n'.join(current_content).strip()

        # Extract and parse score
        score = None
        if 'score' in sections:
            score_text = sections['score'].strip()
            try:
                import re
                # Look for numbers in the score text
                score_match = re.search(r'(\d+)', score_text)
                if score_match:
                    score = int(score_match.group(1))
                    # Validate score is in reasonable range
                    if not (1 <= score <= 10):
                        score = None
            except (ValueError, AttributeError):
                pass

        return {
            "persona": persona,
            "timestamp": datetime.now(UTC).isoformat(),
            "sections": sections,
            "score": score,
            "raw_response": response,
        }
