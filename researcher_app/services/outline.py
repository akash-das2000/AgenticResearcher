# services/outline.py

import json
import re
from .api_handler import call_llm

def _response_to_text(resp) -> str:
    """
    Normalize different LLM SDK responses (Gemini/OpenAI) to a plain string.
    Safe even if resp is already a string.
    """
    if resp is None:
        return ""

    # If already a string
    if isinstance(resp, str):
        return resp

    # Try common dict shape (OpenAI)
    try:
        if isinstance(resp, dict):
            if "choices" in resp and resp["choices"]:
                msg = resp["choices"][0].get("message", {})
                content = msg.get("content")
                if isinstance(content, str):
                    return content
            if "content" in resp and isinstance(resp["content"], str):
                return resp["content"]
            return json.dumps(resp)
    except Exception:
        pass

    # Last resort: str()
    try:
        return str(resp)
    except Exception:
        return ""

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


def _parse_llm_response(resp) -> dict:
    """
    Accept raw LLM response (object or string), coerce to text, strip fences, parse JSON.
    Expected JSON: {"sections":[{"title":"...","bullets":[...]}, ...]}
    """
    response_text = _response_to_text(resp)

    # Clean markdown code fences like ```json ... ```
    cleaned = re.sub(r"```json|```", "", response_text).strip()

    # Try to isolate a JSON object if the model wrapped it in prose
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    candidate = cleaned[start:end + 1] if (start != -1 and end != -1 and end > start) else cleaned

    try:
        data = json.loads(candidate)
    except Exception:
        # Fallback: make a minimal outline from plain text
        bullets = [line.strip() for line in cleaned.splitlines() if line.strip()]
        data = {"sections": [{"title": "Outline", "bullets": bullets}]}

    if "sections" not in data or not isinstance(data["sections"], list):
        data = {"sections": []}

    return data

