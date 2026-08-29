import json
import re


def _safe(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


SCHEMAS = {
    "technician": {
        "required": ["agent", "conviction", "bullish_signals", "bearish_signals", "reasoning", "evidence_used"],
        "types": {
            "agent": str,
            "conviction": (int, float),
            "bullish_signals": list,
            "bearish_signals": list,
            "reasoning": str,
            "evidence_used": list,
        },
    },
    "fundamentalist": {
        "required": ["agent", "conviction", "bullish_points", "bearish_points", "reasoning", "evidence_used", "data_gaps"],
        "types": {
            "agent": str,
            "conviction": (int, float),
            "bullish_points": list,
            "bearish_points": list,
            "reasoning": str,
            "evidence_used": list,
            "data_gaps": list,
        },
    },
    "newsdesk": {
        "required": ["agent", "sentiment", "conviction", "catalysts", "risks", "reasoning", "evidence_used"],
        "types": {
            "agent": str,
            "sentiment": str,
            "conviction": (int, float),
            "catalysts": list,
            "risks": list,
            "reasoning": str,
            "evidence_used": list,
        },
    },
    "bull": {
        "required": ["agent", "conviction", "arguments", "supporting_evidence", "risks_acknowledged"],
        "types": {
            "agent": str,
            "conviction": (int, float),
            "arguments": list,
            "supporting_evidence": list,
            "risks_acknowledged": list,
        },
    },
    "bear": {
        "required": ["agent", "conviction", "arguments", "supporting_evidence", "bullish_risks_acknowledged"],
        "types": {
            "agent": str,
            "conviction": (int, float),
            "arguments": list,
            "supporting_evidence": list,
            "bullish_risks_acknowledged": list,
        },
    },
    "judge": {
        "required": ["agent", "winner", "assessment", "key_catalyst", "key_risk", "confidence", "recommended_verdict", "evidence_used"],
        "types": {
            "agent": str,
            "winner": str,
            "assessment": str,
            "key_catalyst": str,
            "key_risk": str,
            "confidence": (int, float),
            "recommended_verdict": str,
            "evidence_used": list,
        },
    },
}


def validate_schema(agent_name, data):
    """Validate agent output against its schema. Returns (is_valid, errors)."""
    schema = SCHEMAS.get(agent_name)
    if not schema:
        return True, []

    errors = []
    for field in schema["required"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    for field, expected_type in schema.get("types", {}).items():
        if field in data and not isinstance(data[field], expected_type):
            errors.append(f"Field '{field}' must be {expected_type}, got {type(data[field]).__name__}")

    if "conviction" in data:
        c = data["conviction"]
        if isinstance(c, (int, float)) and not (0 <= c <= 100):
            errors.append(f"Conviction must be 0-100, got {c}")

    if "confidence" in data:
        c = data["confidence"]
        if isinstance(c, (int, float)) and not (1 <= c <= 10):
            errors.append(f"Confidence must be 1-10, got {c}")

    if "sentiment" in data and data.get("sentiment") not in ("positive", "neutral", "negative", "no data"):
        errors.append(f"Invalid sentiment: {data.get('sentiment')}")

    if "recommended_verdict" in data and data.get("recommended_verdict") not in ("BUY", "WATCH", "AVOID"):
        errors.append(f"Invalid recommended_verdict: {data.get('recommended_verdict')}")

    if "winner" in data and data.get("winner") not in ("bull", "bear", "tie", "Bull", "Bear", "Tie"):
        errors.append(f"Invalid winner: {data.get('winner')}")

    return len(errors) == 0, errors


def build_evidence_text(evidence):
    """Build a concise evidence text for LLM prompts."""
    sections = []
    for key in ("price", "range_52w", "technicals", "analyst", "news"):
        data = evidence.get(key, {})
        if isinstance(data, dict):
            filtered = {k: v for k, v in data.items() if v is not None and k != "recent"}
            if filtered:
                sections.append(f"{key}: {json.dumps(filtered, indent=2)}")
            news = data.get("recent", [])
            if news:
                headlines = [{"title": h.get("title", ""), "publisher": h.get("publisher", "")} for h in news[:5]]
                sections.append(f"news.headlines: {json.dumps(headlines, indent=2)}")
    gaps = evidence.get("data_gaps", [])
    if gaps:
        sections.append(f"data_gaps: {json.dumps(gaps)}")
    return "\n\n".join(sections)


def parse_llm_json(raw_response):
    """Parse LLM response, extracting JSON from potential markdown wrapping."""
    if not raw_response:
        return None
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
