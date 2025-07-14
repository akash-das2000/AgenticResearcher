# services/outline.py

import json
import re
from .api_handler import call_llm

def generate_outline(full_text, preferred="gemini"):
    """
    Generates a professional blog outline from extracted text.

    Args:
        full_text (str): Cleaned text extracted from a PDF.
        preferred (str): "gemini" or "openai" (default Gemini).

    Returns:
        dict: Outline JSON with sections and descriptions.
    """
    prompt = f"""
You are a technical blog writing assistant.

Given the following text extracted from a PDF, generate a professional blog outline.
The outline should include 5–10 sections with concise titles and 1–2 sentence descriptions.
Add subheadings if appropriate. Return the result as JSON:
{{
  "sections": [
    {{"title": "...", "description": "..."}}
  ]
}}

TEXT:
{full_text}
"""
    response = call_llm(prompt, preferred=preferred)
    return _parse_llm_response(response)


def refine_outline(outline_json, user_changes, preferred="gemini"):
    """
    Applies user-requested changes to an existing outline using an LLM.

    Args:
        outline_json (dict): Current outline JSON.
        user_changes (str): User freeform edit instructions.
        preferred (str): "gemini" or "openai" (default Gemini).

    Returns:
        dict: Updated outline JSON.
    """
    edit_prompt = f"""
You are an AI assistant refining a blog outline.

Here is the current outline:
{json.dumps(outline_json, indent=2)}

The user provided these edit instructions:
\"\"\"{user_changes}\"\"\"

Apply these changes to the outline and return updated JSON:
{{
  "sections": [
    {{"title": "...", "description": "..."}}
  ]
}}
"""
    updated_response = call_llm(edit_prompt, preferred=preferred)
    return _parse_llm_response(updated_response)


def _parse_llm_response(response_text):
    """
    Cleans and parses LLM response into JSON.

    Args:
        response_text (str): Raw LLM response.

    Returns:
        dict: Parsed JSON.
    """
    # Clean markdown fences like ```json ... ```
    cleaned = re.sub(r"```json|```", "", response_text).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}\n\nRaw response:\n{response_text}")
