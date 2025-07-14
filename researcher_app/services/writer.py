# services/writer.py

import re
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


def _clean_llm_output(response_text):
    """
    Cleans LLM response by removing markdown fences and extra text.

    Args:
        response_text (str): Raw LLM response.

    Returns:
        str: Cleaned section body.
    """
    cleaned = re.sub(r"```markdown|```", "", response_text).strip()
    return cleaned
