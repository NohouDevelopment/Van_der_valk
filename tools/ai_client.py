"""
Gedeelde AI client — communiceert via OpenRouter (OpenAI-compatible API).

Drie model-tiers per use case:
  - CHEAP:   Seed-2.0-Mini   → simpele taken, OCR, JSON structurering ($0.10/M)
  - REASON:  Mercury 2       → complexe analyse en redenering ($0.25/M)
  - SEARCH:  Gemini 3.1 Flash Lite :online → taken die live internet-search nodig hebben ($0.25/M + search fee)

Configuratie via .env:
  OPENROUTER_API_KEY=sk-or-...
  MODEL_CHEAP=bytedance-seed/seed-2.0-mini
  MODEL_REASON=inception/mercury-2
  MODEL_SEARCH=google/gemini-3.1-flash-lite-preview:online
"""

import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL_CHEAP = os.getenv("MODEL_CHEAP", "bytedance-seed/seed-2.0-mini")
MODEL_REASON = os.getenv("MODEL_REASON", "inception/mercury-2")
MODEL_SEARCH = os.getenv("MODEL_SEARCH", "perplexity/sonar")

if not OPENROUTER_API_KEY:
    print("Fout: OPENROUTER_API_KEY niet gevonden in .env")
    print("  Ga naar https://openrouter.ai/keys om een key aan te maken")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)


def _call(model: str, messages: list, temperature: float = 0.1) -> str:
    """Interne helper: stuur request naar OpenRouter."""
    import time
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if getattr(e, "status_code", None) == 429:
            time.sleep(5)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        raise


def _parse_json(raw: str) -> dict | list:
    """Extraheer JSON uit een AI respons (met optionele code blocks)."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw)


# --- Cheap model (Seed-2.0-Mini) — simpele taken, OCR, JSON ---

def ai_generate(prompt: str, temperature: float = 0.1) -> str:
    """Simpele tekst-generatie via het goedkope model."""
    return _call(MODEL_CHEAP, [{"role": "user", "content": prompt}], temperature)


def ai_generate_json(prompt: str, temperature: float = 0.1) -> dict | list:
    """Simpele JSON-generatie via het goedkope model."""
    raw = ai_generate(prompt, temperature)
    return _parse_json(raw)


def ai_generate_vision(prompt: str, image_path: str, temperature: float = 0.1) -> str:
    """Vision (afbeelding + tekst) via het goedkope model (Seed-2.0-Mini heeft vision)."""
    ext = Path(image_path).suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    return _call(MODEL_CHEAP, [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
            {"type": "text", "text": prompt}
        ]
    }], temperature)


# --- Reasoning model (Mercury 2) — complexe analyse ---

def ai_reason(prompt: str, temperature: float = 0.2) -> str:
    """Complexe redenering via Mercury 2."""
    return _call(MODEL_REASON, [{"role": "user", "content": prompt}], temperature)


def ai_reason_json(prompt: str, temperature: float = 0.2) -> dict | list:
    """Complexe redenering met JSON output via Mercury 2."""
    raw = ai_reason(prompt, temperature)
    return _parse_json(raw)


# --- Search model (Perplexity Sonar) — live internet research ---

def ai_search(prompt: str, temperature: float = 0.1) -> str:
    """Tekst-generatie met live search via Perplexity Sonar."""
    return _call(MODEL_SEARCH, [{"role": "user", "content": prompt}], temperature)


def ai_search_json(prompt: str, temperature: float = 0.1) -> dict | list:
    """JSON-generatie met live search via Perplexity Sonar."""
    raw = ai_search(prompt, temperature)
    return _parse_json(raw)
