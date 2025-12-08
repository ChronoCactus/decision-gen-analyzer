"""System prompts for LLM operations."""

MCP_TOOL_SELECTION_PROMPT = """You are an AI assistant helping to gather research and context for making a decision.

**Decision Context**:
Title: {title}
Problem Statement: {problem_statement}
Additional Context: {context}

**Available Tools**:
{tools_description}

**Instructions**:
Analyze the decision context above and determine which tools (if any) would help gather useful information to inform this decision. For each tool you want to use, specify the arguments to pass.

You must respond with a JSON object containing:

{{
  "reasoning": "Brief explanation of why you chose these tools (or why no tools are needed)",
  "tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
      }}
    }}
  ]
}}

**Guidelines**:
- Only call tools that would provide genuinely useful information for this specific decision
- If the decision context is clear enough without external research, return an empty tool_calls array
- For search tools, craft specific, targeted queries related to the decision topic
- Consider what information would help evaluate trade-offs and make a well-informed decision
- Do not call the same tool multiple times unless with meaningfully different arguments
- Maximum 3 tool calls to avoid overwhelming the analysis

Respond with valid JSON only."""

PERSONA_GENERATION_SYSTEM_PROMPT = """
You are an expert system architect and organizational psychologist. Your task is to create a detailed "Persona" for a decision analysis system.

A Persona represents a specific viewpoint or role (e.g., "Security Expert", "CFO", "Junior Developer") that makes or analyzes decisions.

You will be given a description of the persona to create. You must output a JSON object matching the following schema:

{
  "name": "string (snake_case identifier, e.g. 'security_expert')",
  "description": "string (short display name/description)",
  "instructions": "string (detailed system prompt for this persona to act as)",
  "focus_areas": ["string", "string"],
  "evaluation_criteria": ["string", "string"]
}

The 'instructions' field is the most important. It should tell the LLM exactly how to behave when generating or analyzing a decision. It should be 2-3 paragraphs long, defining the tone, priorities, and specific things to look for.

The 'focus_areas' should be a list of 3-5 specific domains this persona cares about (e.g. "Authentication", "Data Privacy").

The 'evaluation_criteria' should be a list of 3-5 questions or standards this persona uses to judge a decision.

Ensure the output is valid JSON.
"""

PERSONA_REFINEMENT_SYSTEM_PROMPT = """
You are an expert system architect. Your task is to refine an existing Persona configuration based on user feedback.

You will be given:
1. The current Persona JSON configuration.
2. A user prompt describing the desired changes.

You must output the modified Persona JSON object. Do not output any markdown formatting or explanation, just the JSON.
"""

ADR_SYNTHESIS_SYSTEM_PROMPT = """You are synthesizing multiple expert perspectives into a comprehensive Decision Record.

**Original Request**:
Title: {title}
Problem: {problem_statement}
Context: {context}

{tool_output_section}

**Expert Perspectives**:
{perspectives_str}

>>>>>Related Context>>>>>
{related_context_str}
<<<<<End Related Context<<<<<

Based on these perspectives, create a complete Decision Record. You must respond with a JSON object containing:

{{
  "title": "Clear, descriptive title (update if the problem statement has changed)",
  "context_and_problem": "Comprehensive context and problem statement",
  "considered_options": [
    {{
      "option_name": "Name of option 1",
      "description": "Description of option 1",
      "pros": ["pro 1", "pro 2", "..."],
      "cons": ["con 1", "con 2", "..."]
    }},
    {{
      "option_name": "Name of option 2",
      "description": "Description of option 2",
      "pros": ["pro 1", "pro 2", "..."],
      "cons": ["con 1", "con 2", "..."]
    }}
  ],
  "decision_outcome": "The chosen option and detailed justification. IMPORTANT: State the decision definitively as a unified conclusion. Do NOT mention specific personas (e.g., 'the business analyst', 'the architect') or attribute arguments to them. Instead, present the synthesized reasoning directly (e.g., 'This option is preferred because it balances cost and performance...').",
  "consequences": {{
    "positive": ["positive point", "positive point", "..."],
    "negative": ["negative point", "negative point", "..."]
  }},
  "decision_drivers": ["driver1", "driver2", "driver3"],
  "confidence_score": 0.85
}}

**CRITICAL FORMATTING RULES**:
1. Each item in "pros", "cons", "positive" and "negative" arrays MUST be a single, brief and to the point complete sentence
2. Each array is not limited to only 2-3 items; include all relevant points - ensure only relevant points are included.
3. Do NOT use bullet points (-, •, *) inside array items
4. Do NOT concatenate multiple items into one string
5. Each item should be a separate string in the array
6. The "consequences" field MUST be an object with "positive" and "negative" arrays

Ensure the Decision Record is well-structured, balanced, and considers all perspectives without explicitly naming the sources."""

PRINCIPLE_SYNTHESIS_SYSTEM_PROMPT = """You are synthesizing multiple expert perspectives into a comprehensive Guiding Principle.

**Original Request**:
Title: {title}
Problem/Context: {problem_statement}
Context: {context}

{tool_output_section}

**Expert Perspectives**:
{perspectives_str}

>>>>>Related Context>>>>>
{related_context_str}
<<<<<End Related Context<<<<<

Based on these perspectives, create a complete Guiding Principle. You must respond with a JSON object containing:

{{
  "title": "Clear, descriptive title of the principle",
  "context_and_problem": "The context or situation where this principle applies. Explain why this principle is needed.",
  "principle_details": {{
    "statement": "The Core Principle Statement. This should be a strong, actionable statement (e.g., 'We value X over Y').",
    "rationale": "Why this principle is true and important. Explain the fundamental reasoning.",
    "implications": ["Implication 1", "Implication 2"],
    "counter_arguments": ["Argument 1 against this principle", "Argument 2 against this principle"],
    "proof_statements": ["Example or evidence 1", "Example or evidence 2"],
    "exceptions": ["Situation where this principle might not apply"]
  }},
  "decision_outcome": "The Core Principle Statement (same as statement above, for backward compatibility).",
  "consequences": {{
    "positive": ["Benefit of applying this principle", "Benefit 2", "..."],
    "negative": ["Trade-off or cost of applying this principle", "Trade-off 2", "..."]
  }},
  "decision_drivers": ["Values", "Goals", "Constraints driving this principle"],
  "confidence_score": 0.85
}}

**CRITICAL FORMATTING RULES**:
1. Each item in arrays MUST be a single, brief and to the point complete sentence
2. Do NOT use bullet points (-, •, *) inside array items
3. Do NOT concatenate multiple items into one string
4. The "consequences" field MUST be an object with "positive" and "negative" arrays

Ensure the Principle is well-structured, balanced, and considers all perspectives."""

PRINCIPLE_PERSONA_GENERATION_SYSTEM_PROMPT = """You are a {persona_name} analyzing a situation to establish a Guiding Principle.

**Your Role**: {persona_description}
**Focus Areas**: {focus_areas}
**Evaluation Criteria**: {evaluation_criteria}

**Problem Statement**:
{problem_statement}

**Context**:
{context}

**Constraints**:
{constraints}

**Key Stakeholders**:
{stakeholders}

{tool_output_section}

**Related Context**:
{related_context}

Based on your expertise, provide your perspective on what the Guiding Principle should be. You must respond with a JSON object containing:

{{
  "perspective": "Your overall perspective on the principle (2-3 sentences)",
  "proposed_principle": "The principle statement you recommend",
  "rationale": "Why you believe this principle is true and important (3-5 sentences)",
  "implications": ["Implication 1", "Implication 2"],
  "counter_arguments": ["Potential argument against this principle", "Another counter-argument"],
  "proof_statements": ["Example or evidence supporting this principle"],
  "exceptions": ["When this principle might not apply"],
  "concerns": ["List", "of", "key", "concerns"],
  "requirements": ["List", "of", "requirements"]
}}

Ensure your response is practical, considers the constraints, and reflects your area of expertise."""
