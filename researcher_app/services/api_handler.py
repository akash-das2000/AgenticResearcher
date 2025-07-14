# services/api_handler.py

import os
import openai
from google import genai

# 🚨 Load API Keys
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", None)
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

# ✅ Initialize OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("✅ OpenAI API key loaded.")
else:
    print("❌ OpenAI API key missing!")

# ✅ Initialize Gemini
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini API key loaded.")
else:
    client = None
    print("❌ Gemini API key missing!")

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
            if not client:
                raise ValueError("Gemini client not initialized.")
            print(f"🌟 Using Gemini API ({model_gemini})...")
            response = client.models.generate_content(
                model=model_gemini,
                contents=prompt
            )
            return response.text
        elif preferred == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key missing.")
            print(f"🌟 Using OpenAI API ({model_openai})...")
            response = openai.chat.completions.create(
                model=model_openai,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            return response.choices[0].message.content
        else:
            raise ValueError("Preferred API must be 'gemini' or 'openai'")
    except Exception as e:
        print(f"⚠️ {preferred} API failed: {e}")
        fallback = "openai" if preferred == "gemini" else "gemini"
        print(f"🔄 Falling back to {fallback} API...")
        return call_llm(prompt, preferred=fallback, model_openai=model_openai, model_gemini=model_gemini)
