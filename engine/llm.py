import os
import json
import subprocess
import shutil
import time


_claude_cli_available = None


def _detect_claude_cli():
    global _claude_cli_available
    if _claude_cli_available is None:
        _claude_cli_available = shutil.which("claude") is not None
    return _claude_cli_available


def _call_claude_cli(prompt, timeout=30):
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _call_anthropic_api(prompt, api_key, timeout=30):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.content:
            return response.content[0].text
        return None
    except ImportError:
        return None
    except Exception as e:
        print(f"Anthropic API error: {type(e).__name__}: {e}")
        return None


def _call_openai_api(prompt, api_key, timeout=30):
    try:
        import openai
        client = openai.OpenAI(api_key=api_key, timeout=timeout)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        if response.choices:
            return response.choices[0].message.content
        return None
    except ImportError:
        return None
    except Exception as e:
        print(f"OpenAI API error: {type(e).__name__}: {e}")
        return None


def call_llm(prompt, timeout=30, retries=1):
    """Call LLM with provider cascade, timeout, and retry.

    Returns raw response string or None.
    """
    from config import config

    provider = config.LLM_PROVIDER.lower()
    if provider in ("none", "deterministic"):
        return None

    for attempt in range(1 + retries):
        raw_response = None

        if provider in ("auto", "claude_cli") and _detect_claude_cli():
            raw_response = _call_claude_cli(prompt, timeout=timeout)

        if not raw_response and provider in ("auto", "anthropic") and config.ANTHROPIC_API_KEY:
            raw_response = _call_anthropic_api(prompt, config.ANTHROPIC_API_KEY, timeout=timeout)

        if not raw_response and provider in ("auto", "openai") and config.OPENAI_API_KEY:
            raw_response = _call_openai_api(prompt, config.OPENAI_API_KEY, timeout=timeout)

        if raw_response:
            return raw_response

        if attempt < retries:
            time.sleep(1)

    return None


def call_llm_structured(prompt, schema_name, timeout=30, retries=1):
    """Call LLM and validate response against a schema.

    Returns (parsed_dict, None) on success or (None, error_string) on failure.
    """
    from agents.base import parse_llm_json, validate_schema

    raw = call_llm(prompt, timeout=timeout, retries=retries)
    if not raw:
        return None, "No LLM response"

    parsed = parse_llm_json(raw)
    if not parsed:
        return None, "Failed to parse JSON from LLM response"

    is_valid, errors = validate_schema(schema_name, parsed)
    if not is_valid:
        return None, f"Schema validation failed: {'; '.join(errors)}"

    return parsed, None


def analyze_with_llm(evidence):
    """Legacy monolithic LLM analysis. Kept for backward compatibility."""
    prompt = _build_analysis_prompt(evidence)
    raw = call_llm(prompt, timeout=30, retries=1)
    if not raw:
        return None
    from agents.base import parse_llm_json
    return parse_llm_json(raw)


def _build_analysis_prompt(evidence):
    from agents.base import build_evidence_text
    evidence_text = build_evidence_text(evidence)
    return f"""You are a panel of expert stock market analysts analyzing an Indian stock.

STOCK EVIDENCE:
{evidence_text}

Analyze this stock and return a JSON object with this EXACT structure:
{{
  "bull": {{
    "score": <0-100>,
    "reason": "<concise 1-2 sentence bull case>"
  }},
  "bear": {{
    "score": <0-100>,
    "reason": "<concise 1-2 sentence bear case>"
  }},
  "fundamentals": {{
    "reason": "<concise fundamental analysis>"
  }},
  "technicals": {{
    "reason": "<concise technical analysis>"
  }},
  "news": {{
    "reason": "<concise news analysis>"
  }},
  "judge": {{
    "winner": "Bull" or "Bear" or "Tie",
    "verdict": "BUY" or "WATCH" or "AVOID",
    "confidence": <1-10>,
    "rationale": "<2-3 sentence rationale>",
    "key_catalyst": "<single most important factor>"
  }}
}}

RULES:
- Use ONLY numbers from the evidence bundle. Do NOT invent any figures.
- If data is unavailable, say "data unavailable".
- Keep all rationales concise (1-3 sentences max).
- Return ONLY valid JSON, no markdown formatting.
"""


def is_available():
    from config import config
    provider = config.LLM_PROVIDER.lower()
    if provider in ("none", "deterministic"):
        return False
    if provider in ("auto", "claude_cli") and _detect_claude_cli():
        return True
    if provider in ("auto", "anthropic") and config.ANTHROPIC_API_KEY:
        return True
    if provider in ("auto", "openai") and config.OPENAI_API_KEY:
        return True
    return False
