"""
Gedeelde AI client — communiceert via OpenRouter (OpenAI-compatible API).

Vier model-tiers per use case:
  - CHEAP:          Seed-2.0-Mini   → simpele taken, OCR, JSON structurering ($0.10/M)
  - REASON:         Mercury 2       → complexe analyse en redenering ($0.25/M)
  - SEARCH:         Gemini 3.1 Flash Lite :online → live internet-search ($0.25/M + search fee)
  - DEEP_RESEARCH:  Perplexity Sonar Deep Research → uitgebreide web research (trend scans)

Configuratie via .env:
  OPENROUTER_API_KEY=sk-or-...
  MODEL_CHEAP=bytedance-seed/seed-2.0-mini
  MODEL_REASON=inception/mercury-2
  MODEL_SEARCH=google/gemini-3.1-flash-lite-preview:online
  MODEL_DEEP_RESEARCH=perplexity/sonar-deep-research
  AI_MAX_RETRIES=3
  AI_RETRY_BASE_SECONDS=2
  AI_LOG_RAW=0
  AI_CACHE_ENABLED=0
"""

import os
import json
import time
import logging
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL_CHEAP          = os.getenv("MODEL_CHEAP",          "bytedance-seed/seed-2.0-mini")
MODEL_REASON         = os.getenv("MODEL_REASON",         "inception/mercury-2")
MODEL_SEARCH         = os.getenv("MODEL_SEARCH",         "perplexity/sonar")
MODEL_DEEP_RESEARCH  = os.getenv("MODEL_DEEP_RESEARCH",  "perplexity/sonar-deep-research")

AI_MAX_RETRIES       = int(os.getenv("AI_MAX_RETRIES", "3"))
AI_RETRY_BASE_SECONDS = int(os.getenv("AI_RETRY_BASE_SECONDS", "2"))
AI_LOG_RAW           = os.getenv("AI_LOG_RAW", "0") == "1"

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY niet gevonden in .env — AI calls zullen falen")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)


class AIParseError(Exception):
    """Raised when AI response cannot be parsed as valid JSON."""
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response[:2000] if raw_response else ""


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


def _call(model: str, messages: list, temperature: float = 0.1, timeout: int = 120) -> str:
    """Interne helper: stuur request naar OpenRouter met exponential backoff."""
    last_error = None

    for attempt in range(AI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
            raw = response.choices[0].message.content.strip()
            if AI_LOG_RAW:
                logger.info("AI raw response (model=%s, len=%d): %s", model, len(raw), raw[:2000])
            return raw
        except Exception as e:
            last_error = e
            status_code = getattr(e, "status_code", None)

            if status_code in _RETRYABLE_STATUS_CODES and attempt < AI_MAX_RETRIES:
                delay = AI_RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "AI call fout (status=%s, poging %d/%d), retry in %ds: %s",
                    status_code, attempt + 1, AI_MAX_RETRIES, delay, str(e)[:200]
                )
                time.sleep(delay)
                continue

            logger.warning("AI call mislukt (status=%s, poging %d/%d): %s",
                          status_code, attempt + 1, AI_MAX_RETRIES, str(e)[:200])
            raise

    raise last_error


def _parse_json(raw: str) -> dict | list:
    """Extraheer JSON uit een AI respons (met optionele code blocks)."""
    cleaned = raw

    # Strip markdown code blocks
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    # Probeer directe parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: zoek eerste { of [
    for i, ch in enumerate(cleaned):
        if ch in ('{', '['):
            bracket = '}' if ch == '{' else ']'
            # Zoek het bijbehorende sluithaakje van achteren
            for j in range(len(cleaned) - 1, i, -1):
                if cleaned[j] == bracket:
                    try:
                        return json.loads(cleaned[i:j+1])
                    except json.JSONDecodeError:
                        break
            break

    raise AIParseError(
        "Kon geen geldige JSON extraheren uit AI response",
        raw_response=raw
    )


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


# --- Universele ai_call — gebruikt door prompt_loader migraties ---

_TIER_MAP = {
    "cheap":         MODEL_CHEAP,
    "reason":        MODEL_REASON,
    "search":        MODEL_SEARCH,
    "deep_research": MODEL_DEEP_RESEARCH,
}


def ai_call(prompt: str, model: str, temperature: float = 0.1,
            json_mode: bool = False, vision_path: str | None = None,
            timeout: int = 120) -> str | dict:
    """
    Directe AI-aanroep met expliciet model-ID of tier-naam (cheap/reason/search).

    Args:
        prompt:      De prompt-tekst.
        model:       Tier-naam ("cheap"/"reason"/"search") of volledig OpenRouter model-ID.
        temperature: Sampling temperature (default 0.1).
        json_mode:   Als True, parseer response als JSON en geef dict/list terug.
        vision_path: Pad naar afbeelding (optioneel, voor vision calls).

    Returns:
        str als json_mode=False, anders dict of list.
    """
    resolved = _TIER_MAP.get(model, model)

    if vision_path:
        ext = Path(vision_path).suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".webp": "image/webp", ".gif": "image/gif"}
        mime_type = mime_map.get(ext, "image/jpeg")
        with open(vision_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }]
        raw = _call(resolved, messages, temperature, timeout=timeout)
    else:
        raw = _call(resolved, [{"role": "user", "content": prompt}], temperature, timeout=timeout)

    if json_mode:
        return _parse_json(raw)
    return raw
