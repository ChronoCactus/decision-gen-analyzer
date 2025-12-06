"""
MCP Tool Orchestrator

Handles AI-driven tool selection and execution for ADR generation.
The AI decides which tools to call and with what arguments based on the decision context.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.llama_client import LlamaCppClient
from src.logger import get_logger
from src.mcp_client import (
    MCPClientManager,
    MCPToolResult,
    get_mcp_client_manager,
)
from src.mcp_config_storage import MCPServerConfig, get_mcp_storage
from src.prompts import MCP_TOOL_SELECTION_PROMPT

logger = get_logger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call decided by the AI."""

    tool_name: str
    arguments: Dict[str, Any]
    server_id: Optional[str] = None  # Populated after matching to server


@dataclass
class ToolSelectionResult:
    """Result of AI tool selection."""

    reasoning: str
    tool_calls: List[ToolCall]
    raw_response: str = ""


@dataclass
class MCPReferenceInfo:
    """Reference information for an MCP tool result, for inclusion in ADR references."""

    id: str  # Stored result ID
    title: str  # Display title (e.g., "Web Search")
    summary: str  # Brief description of what was searched/returned
    type: str = "mcp"  # Always "mcp" for MCP references
    server_name: str = ""  # MCP server name for display (e.g., "MCP: Websearch")

    def to_dict(self) -> Dict[str, str]:
        """Convert to dict for referenced_adrs field."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "type": self.type,
            "server_name": self.server_name,
        }


@dataclass
class MCPOrchestrationResult:
    """Complete result of MCP orchestration including tool outputs."""

    tool_selection: Optional[ToolSelectionResult] = None
    tool_results: List[MCPToolResult] = field(default_factory=list)
    formatted_context: str = ""
    error: Optional[str] = None
    references: List[MCPReferenceInfo] = field(default_factory=list)  # For ADR refs


class MCPOrchestrator:
    """Orchestrates AI-driven MCP tool selection and execution."""

    def __init__(
        self,
        client_manager: Optional[MCPClientManager] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            client_manager: MCP client manager instance (default: singleton)
        """
        self.client_manager = client_manager or get_mcp_client_manager()
        self.storage = get_mcp_storage()

    def _format_tools_description(self, servers: List[MCPServerConfig]) -> str:
        """Format available tools into a description for the LLM.

        Args:
            servers: List of enabled MCP servers with their tools

        Returns:
            Formatted string describing all available tools
        """
        if not servers:
            return "No tools available."

        tool_descriptions = []

        for server in servers:
            for tool in server.tools:
                # Build argument description from stored info or defaults
                args_desc = ""
                if tool.default_arguments:
                    args_desc = (
                        f"\n    Default arguments: {json.dumps(tool.default_arguments)}"
                    )

                tool_descriptions.append(
                    f"""
**Tool: {tool.tool_name}**
- Server: {server.name}
- Description: {tool.description or 'No description available'}
- Required arguments: Varies by tool (see description){args_desc}
"""
                )

        return "\n".join(tool_descriptions)

    def _format_tools_with_schemas(
        self, tools_with_schemas: List[Dict[str, Any]]
    ) -> str:
        """Format tools with their full schemas for the LLM.

        Args:
            tools_with_schemas: List of tool info including input_schema

        Returns:
            Formatted string describing tools with argument schemas
        """
        if not tools_with_schemas:
            return "No tools available."

        tool_descriptions = []

        for tool_info in tools_with_schemas:
            tool_name = tool_info.get("tool_name", tool_info.get("name", "unknown"))
            description = tool_info.get("description", "No description available")
            server_name = tool_info.get("server_name", "")
            server_id = tool_info.get("server_id", "")
            input_schema = tool_info.get("input_schema", {})

            # Format the input schema nicely
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            args_desc = []
            for arg_name, arg_info in properties.items():
                arg_type = arg_info.get("type", "any")
                arg_desc = arg_info.get("description", "")
                is_required = arg_name in required
                req_marker = " (required)" if is_required else " (optional)"

                args_desc.append(
                    f"    - {arg_name} ({arg_type}){req_marker}: {arg_desc}"
                )

            args_str = "\n".join(args_desc) if args_desc else "    No arguments"

            tool_descriptions.append(
                f"""
**Tool: {tool_name}** (server: {server_name}, id: {server_id})
Description: {description}
Arguments:
{args_str}
"""
            )

        return "\n".join(tool_descriptions)

    async def _get_available_tools_with_schemas(
        self,
    ) -> List[Dict[str, Any]]:
        """Get all available tools from enabled servers with their schemas.

        Returns:
            List of tools with server info and input schemas
        """
        servers = await self.storage.list_enabled()
        all_tools = []

        for server in servers:
            # Try to get tool schemas by discovering (or use cached)
            try:
                discovered = await self.client_manager.discover_tools(server.id)

                # Map discovered schemas to stored tools
                schema_map = {t["name"]: t.get("input_schema", {}) for t in discovered}

                for tool in server.tools:
                    all_tools.append(
                        {
                            "server_id": server.id,
                            "server_name": server.name,
                            "tool_name": tool.tool_name,
                            "display_name": tool.display_name,
                            "description": tool.description,
                            "input_schema": schema_map.get(tool.tool_name, {}),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to get tool schemas from {server.name}: {e}")
                # Fall back to stored tools without schemas
                for tool in server.tools:
                    all_tools.append(
                        {
                            "server_id": server.id,
                            "server_name": server.name,
                            "tool_name": tool.tool_name,
                            "display_name": tool.display_name,
                            "description": tool.description,
                            "input_schema": {},
                        }
                    )

        return all_tools

    async def select_tools(
        self,
        title: str,
        problem_statement: str,
        context: str,
        llm_client: LlamaCppClient,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ToolSelectionResult:
        """Use the LLM to decide which tools to call.

        Args:
            title: Decision title
            problem_statement: Problem statement
            context: Additional context
            llm_client: LLM client to use for selection
            available_tools: Optional pre-fetched tools list

        Returns:
            ToolSelectionResult with AI's reasoning and tool calls
        """
        # Get available tools if not provided
        if available_tools is None:
            available_tools = await self._get_available_tools_with_schemas()

        if not available_tools:
            return ToolSelectionResult(
                reasoning="No MCP tools are available.",
                tool_calls=[],
            )

        # Format tools for the prompt
        tools_description = self._format_tools_with_schemas(available_tools)

        # Build the prompt
        prompt = MCP_TOOL_SELECTION_PROMPT.format(
            title=title,
            problem_statement=problem_statement,
            context=context or "No additional context provided.",
            tools_description=tools_description,
        )

        logger.info(
            "Requesting AI tool selection", available_tools=len(available_tools)
        )

        # Call the LLM
        try:
            response = await llm_client.generate(prompt)

            # Parse the response
            result = self._parse_tool_selection_response(response, available_tools)
            result.raw_response = response
            return result

        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            return ToolSelectionResult(
                reasoning=f"Tool selection failed: {str(e)}",
                tool_calls=[],
                raw_response="",
            )

    def _parse_tool_selection_response(
        self,
        response: str,
        available_tools: List[Dict[str, Any]],
    ) -> ToolSelectionResult:
        """Parse the LLM's tool selection response.

        Args:
            response: Raw LLM response
            available_tools: List of available tools for validation

        Returns:
            Parsed ToolSelectionResult
        """
        try:
            # Extract JSON from response
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1

            if start_idx == -1 or end_idx <= start_idx:
                logger.warning("No JSON found in tool selection response")
                return ToolSelectionResult(
                    reasoning="Failed to parse response - no JSON found",
                    tool_calls=[],
                )

            json_str = response[start_idx:end_idx]
            data = json.loads(json_str)

            reasoning = data.get("reasoning", "No reasoning provided")
            tool_calls_data = data.get("tool_calls", [])

            # Build tool name to server mapping
            tool_server_map = {t["tool_name"]: t["server_id"] for t in available_tools}

            # Parse and validate tool calls
            tool_calls = []
            for tc in tool_calls_data:
                tool_name = tc.get("tool_name", "")
                arguments = tc.get("arguments", {})

                if not tool_name:
                    logger.warning("Tool call missing tool_name, skipping")
                    continue

                # Check if tool exists
                if tool_name not in tool_server_map:
                    logger.warning(f"Unknown tool '{tool_name}' requested, skipping")
                    continue

                tool_calls.append(
                    ToolCall(
                        tool_name=tool_name,
                        arguments=arguments,
                        server_id=tool_server_map[tool_name],
                    )
                )

            logger.info(
                "Tool selection parsed",
                reasoning=reasoning[:100],
                tool_count=len(tool_calls),
            )

            return ToolSelectionResult(
                reasoning=reasoning,
                tool_calls=tool_calls,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool selection JSON: {e}")
            return ToolSelectionResult(
                reasoning=f"Failed to parse response: {str(e)}",
                tool_calls=[],
            )

    async def execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
        progress_callback: Optional[callable] = None,
    ) -> List[MCPToolResult]:
        """Execute the tool calls decided by the AI.

        Args:
            tool_calls: List of tool calls to execute
            progress_callback: Optional callback for progress updates

        Returns:
            List of tool results
        """
        if not tool_calls:
            return []

        results = []

        for tc in tool_calls:
            if progress_callback:
                progress_callback(f"Calling MCP tool: {tc.tool_name}")

            logger.info(
                "Executing AI-selected tool",
                tool=tc.tool_name,
                server_id=tc.server_id,
                arguments=tc.arguments,
            )

            result = await self.client_manager.call_tool(
                server_id=tc.server_id,
                tool_name=tc.tool_name,
                arguments=tc.arguments,
            )
            results.append(result)

            if result.success:
                logger.info(f"Tool {tc.tool_name} completed successfully")
            else:
                logger.warning(f"Tool {tc.tool_name} failed: {result.error}")

        return results

    def format_tool_results_as_context(
        self,
        results: List[MCPToolResult],
    ) -> str:
        """Format tool results as context for subsequent prompts.

        Args:
            results: List of tool results

        Returns:
            Formatted context string for including in prompts
        """
        if not results:
            return ""

        successful_results = [r for r in results if r.success]
        if not successful_results:
            return ""

        parts = ["\n**Research Results from MCP Tools:**\n"]

        for result in successful_results:
            parts.append(result.to_context_string())
            parts.append("")  # Blank line between results

        return "\n".join(parts)

    async def orchestrate(
        self,
        title: str,
        problem_statement: str,
        context: str,
        llm_client: LlamaCppClient,
        progress_callback: Optional[callable] = None,
        adr_id: Optional[str] = None,
    ) -> MCPOrchestrationResult:
        """Full orchestration: select tools, execute them, format results.

        Args:
            title: Decision title
            problem_statement: Problem statement
            context: Additional context
            llm_client: LLM client to use
            progress_callback: Optional callback for progress updates
            adr_id: Optional ADR ID to associate results with

        Returns:
            MCPOrchestrationResult with all results
        """
        try:
            # Step 1: Get available tools
            if progress_callback:
                progress_callback("Discovering available MCP tools...")

            available_tools = await self._get_available_tools_with_schemas()

            if not available_tools:
                return MCPOrchestrationResult(
                    tool_selection=ToolSelectionResult(
                        reasoning="No MCP tools configured or enabled.",
                        tool_calls=[],
                    ),
                    tool_results=[],
                    formatted_context="",
                )

            # Step 2: Ask AI to select tools
            if progress_callback:
                progress_callback("AI selecting relevant tools...")

            selection = await self.select_tools(
                title=title,
                problem_statement=problem_statement,
                context=context,
                llm_client=llm_client,
                available_tools=available_tools,
            )

            if not selection.tool_calls:
                logger.info("AI decided no tools needed", reasoning=selection.reasoning)
                return MCPOrchestrationResult(
                    tool_selection=selection,
                    tool_results=[],
                    formatted_context="",
                )

            # Step 3: Execute selected tools
            if progress_callback:
                progress_callback(
                    f"Executing {len(selection.tool_calls)} selected tools..."
                )

            results = await self.execute_tool_calls(
                selection.tool_calls,
                progress_callback=progress_callback,
            )

            # Step 4: Save results and create references
            if progress_callback:
                progress_callback("Saving tool results...")

            references = await self._save_results_and_create_refs(
                results=results,
                tool_calls=selection.tool_calls,
                adr_id=adr_id,
            )

            # Step 5: Format results
            formatted_context = self.format_tool_results_as_context(results)

            return MCPOrchestrationResult(
                tool_selection=selection,
                tool_results=results,
                formatted_context=formatted_context,
                references=references,
            )

        except Exception as e:
            logger.error(f"MCP orchestration failed: {e}")
            return MCPOrchestrationResult(
                error=str(e),
            )

    async def _save_results_and_create_refs(
        self,
        results: List[MCPToolResult],
        tool_calls: List[ToolCall],
        adr_id: Optional[str] = None,
    ) -> List[MCPReferenceInfo]:
        """Save tool results to disk and create reference info for ADR.

        Args:
            results: List of tool execution results
            tool_calls: List of tool calls (for argument info)
            adr_id: Optional ADR ID to associate with

        Returns:
            List of reference info for including in ADR
        """
        from src.mcp_result_storage import get_mcp_result_storage

        storage = get_mcp_result_storage()
        references = []

        # Create a mapping of tool_name to arguments from tool_calls
        args_map = {tc.tool_name: tc.arguments for tc in tool_calls}

        for result in results:
            if not result.success:
                # Skip failed results
                continue

            try:
                # Save the result
                stored = await storage.save(
                    server_id=result.server_id,
                    server_name=result.server_name,
                    tool_name=result.tool_name,
                    arguments=args_map.get(result.tool_name, {}),
                    result=result.result,
                    success=result.success,
                    error=result.error,
                    adr_id=adr_id,
                )

                # Create reference info
                # Build summary from arguments (e.g., the search query)
                args = args_map.get(result.tool_name, {})
                summary = self._build_reference_summary(result.tool_name, args)

                ref = MCPReferenceInfo(
                    id=stored.id,
                    title=result.tool_name,
                    summary=summary,
                    type="mcp",
                    server_name=result.server_name,
                )
                references.append(ref)

                logger.info(
                    f"Created MCP reference for {result.tool_name}",
                    ref_id=stored.id,
                )

            except Exception as e:
                logger.error(f"Failed to save result for {result.tool_name}: {e}")

        return references

    def _build_reference_summary(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> str:
        """Build a human-readable summary for the reference.

        Args:
            tool_name: Name of the tool
            arguments: Arguments passed to the tool

        Returns:
            Summary string
        """
        # Try to extract meaningful info from common argument patterns
        query = (
            arguments.get("query")
            or arguments.get("search_query")
            or arguments.get("q")
        )
        if query:
            # Truncate long queries
            if len(query) > 80:
                query = query[:77] + "..."
            return f'Query: "{query}"'

        url = arguments.get("url") or arguments.get("uri")
        if url:
            return f"URL: {url}"

        # Fallback to JSON representation of args
        if arguments:
            import json

            args_str = json.dumps(arguments)
            if len(args_str) > 80:
                args_str = args_str[:77] + "..."
            return f"Args: {args_str}"

        return f"Tool: {tool_name}"


# Singleton instance
_mcp_orchestrator: Optional[MCPOrchestrator] = None


def get_mcp_orchestrator() -> MCPOrchestrator:
    """Get the singleton MCP orchestrator instance."""
    global _mcp_orchestrator
    if _mcp_orchestrator is None:
        _mcp_orchestrator = MCPOrchestrator()
    return _mcp_orchestrator
