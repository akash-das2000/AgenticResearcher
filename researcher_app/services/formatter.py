# services/formatter.py

import os
import markdown
from markdown.extensions.toc import TocExtension
from weasyprint import HTML
import re
from django.conf import settings

# ✅ Output directory
SAVE_DIR = os.path.join(settings.MEDIA_ROOT, "final_blogs")
os.makedirs(SAVE_DIR, exist_ok=True)


def assemble_html(sections, blog_title="Agentic Blog", author="Your AI Agent"):
    """
    Assembles a full HTML blog from drafted sections.

    Args:
        sections (list): List of {"title": str, "body": str}
        blog_title (str): Title of the blog.
        author (str): Author name.

    Returns:
        str: Complete HTML string.
    """
    # Build Markdown from sections
    md_content = f"# {blog_title}\n\n**Author:** {author}\n\n"
    for sec in sections:
        body = sec['body'].strip()

        # 🔥 Remove duplicate title at start of body
        if body.lower().startswith(sec['title'].lower()):
            body = body[len(sec['title']):].lstrip()

        # 🔥 Remove first Markdown heading if it matches section title
        body = re.sub(r"^#+\s+" + re.escape(sec['title']) + r"\s*\n", "", body, flags=re.IGNORECASE)

        md_content += f"## {sec['title']}\n\n{body}\n\n"

    # Convert Markdown to HTML with TOC
    html_content = markdown.markdown(
        md_content,
        extensions=['fenced_code', 'tables', TocExtension(title='Table of Contents')],
        output_format='html5'  # Prevent escaping LaTeX
    )

    # 🔥 Unescape LaTeX backslashes for MathJax
    html_content = html_content.replace('\\\\', '\\')

    # Embed MathJax config and minimal CSS
    full_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{blog_title}</title>
    <script>
    MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
      }},
      svg: {{ fontCache: 'global' }}
    }};
    </script>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        body {{
            font-family: Georgia, serif;
            margin: 2rem;
            line-height: 1.6;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1rem auto;
        }}
        .toc {{
            border: 1px solid #ccc;
            padding: 1rem;
            margin-bottom: 2rem;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""
    return full_html


def save_html_and_pdf(html_content, filename="final_blog"):
    """
    Saves HTML and PDF versions of the blog.

    Args:
        html_content (str): Full HTML content.
        filename (str): Base filename for output.

    Returns:
        dict: Paths to saved HTML and PDF files.
    """
    html_path = os.path.join(SAVE_DIR, f"{filename}.html")
    pdf_path = os.path.join(SAVE_DIR, f"{filename}.pdf")

    # Save HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Save PDF using WeasyPrint
    HTML(string=html_content).write_pdf(pdf_path)

    return {
        "html_path": html_path,
        "pdf_path": pdf_path
    }
