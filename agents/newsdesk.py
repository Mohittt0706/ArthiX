from agents.base import _safe, _clamp, build_evidence_text, validate_schema
from engine.llm import call_llm_structured

_POSITIVE_KEYWORDS = [
    "surge", "rally", "gain", "profit", "upgrade", "buy", "bullish",
    "record high", "outperform", "beat", "strong", "growth", "boom",
    "breakout", "soar", "jump", "rise", "climb", "recovery", "positive",
    "upbeat", "optimistic", "bull", "uptick", "momentum",
]

_NEGATIVE_KEYWORDS = [
    "crash", "plunge", "drop", "loss", "downgrade", "sell", "bearish",
    "record low", "underperform", "miss", "weak", "decline", "slump",
    "breakdown", "tumble", "fall", "sink", "dump", "crisis", "negative",
    "downturn", "pessimistic", "bear", "downtick", "correction",
]


_SYSTEM_PROMPT = """You are an expert financial news analyst for Indian stock markets.

You receive a normalized evidence bundle with these fields:
- news: total, positive, negative, neutral, recent[{title, publisher}]

Your task: Analyze the news sentiment and identify catalysts and risks.

CRITICAL RULES:
- Every news-based claim MUST reference an actual headline from the evidence.
- Do NOT invent events, headlines, or news that is not in the evidence.
- Assess materiality: which headlines are market-moving vs routine?
- Identify forward-looking catalysts and potential risks.
- sentiment: "positive", "neutral", or "negative"
- conviction: 0-100 (0=extremely negative, 50=neutral, 100=extremely positive)
- evidence_used: list the exact evidence fields or headline indices you referenced.

Return ONLY valid JSON:
{
  "agent": "newsdesk",
  "sentiment": "positive"|"neutral"|"negative",
  "conviction": <0-100>,
  "catalysts": ["<catalyst1>", ...],
  "risks": ["<risk1>", ...],
  "reasoning": "<2-4 sentences explaining the news picture>",
  "evidence_used": ["field1", "headline_index2", ...]
}"""


def _deterministic(evidence):
    news = evidence.get("news", {})
    total = news.get("total", 0)
    recent = news.get("recent", [])

    pos = _safe(news.get("positive"))
    neg = _safe(news.get("negative"))
    neu = _safe(news.get("neutral"))

    evidence_used = ["news.total", "news.positive", "news.negative", "news.neutral"]

    if total == 0 and not recent:
        sentiment = "no data"
        conviction = 50
        reasoning = "No recent news available for analysis."
        return {
            "agent": "newsdesk",
            "sentiment": sentiment,
            "conviction": conviction,
            "catalysts": [],
            "risks": [],
            "reasoning": reasoning,
            "evidence_used": evidence_used,
            "data_gaps": ["news.recent"],
        }

    if pos == 0 and neg == 0 and neu == 0 and recent:
        pos, neg, neu = 0, 0, 0
        for item in recent:
            title = item.get("title", "")
            t = title.lower()
            title_pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in t)
            title_neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in t)
            if title_pos > title_neg:
                pos += 1
            elif title_neg > title_pos:
                neg += 1
            else:
                neu += 1
        evidence_used.append("news.recent (re-classified from headlines)")

    if pos > neg * 2:
        sentiment = "positive"
    elif neg > pos * 2:
        sentiment = "negative"
    elif pos > neg:
        sentiment = "positive"
    elif neg > pos:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    total_count = pos + neg + neu
    if total_count > 0:
        if sentiment == "positive":
            conviction = _clamp(round(50 + (pos / total_count) * 50), 50, 100)
        elif sentiment == "negative":
            conviction = _clamp(round(50 - (neg / total_count) * 50), 0, 50)
        else:
            conviction = 50
    else:
        conviction = 50

    catalysts = []
    risks = []
    for i, item in enumerate(recent):
        title = item.get("title", "")
        evidence_used.append(f"news.recent[{i}]")
        title_lower = title.lower()
        if any(kw in title_lower for kw in ("upgrade", "buy", "profit", "growth", "surge", "rally")):
            catalysts.append(title)
        if any(kw in title_lower for kw in ("downgrade", "sell", "loss", "crash", "decline", "miss")):
            risks.append(title)

    if not catalysts and pos > 0:
        catalysts.append("Generally positive news flow")
    if not risks and neg > 0:
        risks.append("Some negative headlines present")

    parts = []
    parts.append(f"News sentiment: {sentiment} ({pos} positive, {neg} negative, {neu} neutral from {total} items)")
    if catalysts:
        parts.append(f"Key catalysts: {'; '.join(catalysts[:2])}")
    if risks:
        parts.append(f"Key risks: {'; '.join(risks[:2])}")
    reasoning = ". ".join(parts) + "."

    return {
        "agent": "newsdesk",
        "sentiment": sentiment,
        "conviction": conviction,
        "catalysts": catalysts,
        "risks": risks,
        "reasoning": reasoning,
        "evidence_used": evidence_used,
        "data_gaps": [],
    }


def run(evidence):
    evidence_text = build_evidence_text(evidence)
    prompt = f"{_SYSTEM_PROMPT}\n\nEVIDENCE:\n{evidence_text}"

    llm_result, error = call_llm_structured(prompt, "newsdesk", timeout=30, retries=1)
    if llm_result and not error:
        llm_result["agent"] = "newsdesk"
        return {
            "agent": "Newsdesk",
            "status": "complete",
            "output": llm_result,
            "llm_powered": True,
        }

    det = _deterministic(evidence)
    return {
        "agent": "Newsdesk",
        "status": "complete",
        "output": det,
        "llm_powered": False,
    }
