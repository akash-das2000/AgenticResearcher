# services/api_handler.py

import os
import openai
from google import genai
from django.conf import settings

# ✅ Load API Keys from Django settings
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", None)
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

# ✅ Initialize OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    raise ValueError("❌ OpenAI API key not found in settings.")

# ✅ Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    raise ValueError("❌ Gemini API key not found in settings.")

# 📜 Unified LLM call function
def call_llm(prompt, preferred="gemini", model_openai="gpt-4o", model_gemini="gemini-2.5-pro"):
    """
    Calls preferred API (Gemini or OpenAI). Falls back if error occurs.

    Args:
        prompt (str): Prompt to send
        preferred (str): "gemini" or "openai"
        model_openai (str): OpenAI model name (default gpt-4o)
        model_gemini (str): Gemini model name (default gemini-2.5-pro)

    Returns:
        str: LLM response content
    """
    try:
        if preferred == "gemini":
            print(f"🌟 Using Gemini API ({model_gemini})...")
            response = genai.generate_text(
                model=model_gemini,
                prompt=prompt,
                temperature=0.7,
                max_output_tokens=2048
            )
            return response.result
        elif preferred == "openai":
            print(f"🌟 Using OpenAI API ({model_openai})...")
            response = openai.ChatCompletion.create(
                model=model_openai,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            return response['choices'][0]['message']['content']
        else:
            raise ValueError("Preferred API must be 'gemini' or 'openai'")
    except Exception as e:
        print(f"⚠️ {preferred} API failed: {e}")
        # 🔄 Fallback to the other API
        fallback = "openai" if preferred == "gemini" else "gemini"
        print(f"🔄 Falling back to {fallback} API...")
        return call_llm(prompt, preferred=fallback, model_openai=model_openai, model_gemini=model_gemini)
