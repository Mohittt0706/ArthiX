import os
import json
import subprocess
import shutil


def _detect_claude_cli():
    return shutil.which("claude") is not None


def _call_claude_cli(prompt, timeout=60):
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


def _call_anthropic_api(prompt, api_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"Anthropic API error: {e}")
        return None


def _call_openai_api(prompt, api_key):
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def _build_analysis_prompt(evidence):
    return f"""You are a panel of expert stock market analysts analyzing an Indian stock.

STOCK EVIDENCE BUNDLE:
{json.dumps(evidence, indent=2)}

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
- BUY only if bull case is clearly stronger. WATCH for mixed signals. AVOID if bear dominates.
- Return ONLY valid JSON, no markdown formatting.
"""


def analyze_with_llm(evidence):
    from config import config

    prompt = _build_analysis_prompt(evidence)
    provider = config.LLM_PROVIDER.lower()
    raw_response = None

    if provider in ("auto", "claude_cli") and _detect_claude_cli():
        raw_response = _call_claude_cli(prompt)

    if not raw_response and provider in ("auto", "anthropic") and config.ANTHROPIC_API_KEY:
        raw_response = _call_anthropic_api(prompt, config.ANTHROPIC_API_KEY)

    if not raw_response and provider in ("auto", "openai") and config.OPENAI_API_KEY:
        raw_response = _call_openai_api(prompt, config.OPENAI_API_KEY)

    if not raw_response:
        return None

    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        result = json.loads(cleaned)
        return result
    except json.JSONDecodeError:
        print(f"Failed to parse LLM response as JSON")
        return None


def is_available():
    from config import config
    if config.LLM_PROVIDER.lower() in ("none", "deterministic"):
        return False
    if _detect_claude_cli():
        return True
    if config.ANTHROPIC_API_KEY:
        return True
    if config.OPENAI_API_KEY:
        return True
    return False
