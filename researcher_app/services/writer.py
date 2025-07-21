# services/writer.py

import re
import json
from .api_handler import call_llm

def draft_section(section, full_context, preferred="openai"):
    # … your existing code unchanged …
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
    # … your existing code unchanged …
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


def generate_description(outline, full_context, preferred="openai"):
    """
    Generates a concise blog description (1–2 sentences).
    """
    prompt = f"""
You are a technical blog writing assistant.

Given the blog outline (JSON):
{json.dumps(outline.outline_json, indent=2)}

and the full extracted context:
\"\"\"{full_context}\"\"\"

Write a concise description (1–2 sentences) summarizing the blog.

Return ONLY the description text, no JSON or extra commentary.
"""
    response = call_llm(prompt, preferred=preferred)
    return _clean_llm_output(response)


def refine_description(outline, user_feedback, full_context, preferred="openai"):
    """
    Refines an existing description based on user feedback.
    """
    prompt = f"""
You are an AI writing assistant refining a blog description.

Here is the blog outline (JSON):
{json.dumps(outline.outline_json, indent=2)}

Full context:
\"\"\"{full_context}\"\"\"

Current description:
\"\"\"{outline.description}\"\"\"

User feedback:
\"\"\"{user_feedback}\"\"\"

Apply the user's feedback and return ONLY the updated description text.
"""
    response = call_llm(prompt, preferred=preferred)
    return _clean_llm_output(response)


def _clean_llm_output(response_text):
    """
    Strips markdown fences, triples quotes, etc.
    """
    cleaned = re.sub(r"```(?:json|markdown)?|```", "", response_text).strip()
    return cleaned
