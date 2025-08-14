# services/api_handler.py

import os
import openai
from google import genai
from django.conf import settings

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
            if not GEMINI_API_KEY:
                raise ValueError("Missing GEMINI_API_KEY")
        
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=model_gemini,
                contents=prompt
            )
        
            # Always return a STRING
            if hasattr(resp, "text") and isinstance(resp.text, str) and resp.text.strip():
                return resp.text
        
            # fallback: collect candidates/parts text if needed
            texts = []
            try:
                for c in getattr(resp, "candidates", []) or []:
                    content = getattr(c, "content", None)
                    parts = getattr(content, "parts", None) if content else None
                    if parts:
                        for p in parts:
                            t = getattr(p, "text", None)
                            if isinstance(t, str) and t.strip():
                                texts.append(t)
            except Exception:
                pass
        
            return "\n".join(texts) if texts else ""

        # if preferred == "gemini":
        #     if not client:
        #         raise ValueError("Gemini client not initialized.")
        #     print(f"🌟 Using Gemini API ({model_gemini})...")
        #     response = client.models.generate_content(
        #         model=model_gemini,
        #         contents=prompt
        #     )
        #     return response.text
        
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

