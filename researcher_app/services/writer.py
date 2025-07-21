# services/writer.py

import re
import json
from .api_handler import call_llm

def draft_section(section, full_context, preferred="openai"):
    """
    Drafts a single blog section.

    Args:
        section (dict): {"title": "...", "description": "..."}
        full_context (str): Cleaned full text from PDF for context.
        preferred (str): "openai" or "gemini" (default OpenAI)

    Returns:
        str: Drafted section body (Markdown/HTML with MathJax)
    """
    prompt = f"""
You are a technical blog writing assistant.

Write a detailed, professional blog section based on the following details.

Section Title: {section['title']}
Section Description: {section['description']}

Here is the full extracted context for reference:
\"\"\"{full_context}\"\"\"

Requirements:
- Write in Markdown format
- Include technical depth and MathJax equations where needed
- Maintain a professional tone

Return ONLY the drafted section body (no JSON or extra text).
"""
    response = call_llm(prompt, preferred=preferred)
    return _clean_llm_output(response)


def refine_section(section_title, current_body, user_feedback, preferred="openai"):
    """
    Refines an existing drafted section based on user feedback.

    Args:
        section_title (str): Title of the section.
        current_body (str): Current drafted content.
        user_feedback (str): User's edit instructions.
        preferred (str): "openai" or "gemini" (default OpenAI)

    Returns:
        str: Refined section body.
    """
    prompt = f"""
You are an AI writing assistant refining a technical blog section.

Here is the section title: {section_title}
Here is the current draft:
\"\"\"{current_body}\"\"\"

The user provided these edit instructions:
\"\"\"{user_feedback}\"\"\"

Apply the requested changes and return the updated section body in Markdown format.
"""
    response = call_llm(prompt, preferred=preferred)
    return _clean_llm_output(response)


def generate_meta(outline, full_context, preferred="openai"):
    """
    Generates blog metadata (title, author, description) given the outline and full context.

    Args:
        outline (BlogOutline): Django model instance with `outline_json`.
        full_context (str): Extracted PDF text for reference.
        preferred (str): "openai" or "gemini"

    Returns:
        dict: {"title": "...", "author": "...", "description": "..."}
    """
    prompt = f"""
You are a technical blog writing assistant.

Generate the metadata for a blog post based on the following outline and context.

Blog Outline (JSON):
{json.dumps(outline.outline_json, indent=2)}

Full extracted context for reference:
\"\"\"{full_context}\"\"\"

Requirements:
1. "title"   : A concise, descriptive title.
2. "author"  : A suitable author name.
3. "description": A brief summary (1–2 sentences).

Return ONLY a JSON object with these keys and no additional commentary.
"""
    response = call_llm(prompt, preferred=preferred)
    cleaned = _clean_json_output(response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract the JSON substring
        snippet = cleaned[cleaned.find("{"): cleaned.rfind("}")+1]
        return json.loads(snippet)


def refine_meta(outline, user_feedback, full_context, preferred="openai"):
    """
    Refines existing metadata based on user feedback.

    Args:
        outline (BlogOutline): Django model instance with `outline_json`.
        user_feedback (str): The user's refinement instructions.
        full_context (str): Extracted PDF text for reference.
        preferred (str): "openai" or "gemini"

    Returns:
        dict: {"title": "...", "author": "...", "description": "..."}
    """
    prompt = f"""
You are a technical blog writing assistant refining blog metadata.

Blog Outline (JSON):
{json.dumps(outline.outline_json, indent=2)}

Full extracted context:
\"\"\"{full_context}\"\"\"

The user provided feedback on the metadata:
\"\"\"{user_feedback}\"\"\"

Using the feedback, produce updated metadata with keys:
"title", "author", "description".

Return ONLY a JSON object with these keys and no extra text.
"""
    response = call_llm(prompt, preferred=preferred)
    cleaned = _clean_json_output(response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        snippet = cleaned[cleaned.find("{"): cleaned.rfind("}")+1]
        return json.loads(snippet)


def _clean_llm_output(response_text):
    """
    Cleans LLM response by removing markdown fences and extra text.
    """
    return re.sub(r"```(?:markdown)?|```", "", response_text).strip()


def _clean_json_output(response_text):
    """
    Strips code fences around JSON and returns raw JSON text.
    """
    # Remove ```json fences if present
    return re.sub(r"```json|```", "", response_text).strip()
